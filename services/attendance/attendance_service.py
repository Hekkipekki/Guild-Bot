import time

from data.attendance_store import (
    load_attendance,
    save_attendance,
    get_or_create_attendance_record,
)


VALID_ATTENDANCE_STATUSES = {
    "attending",
    "benched",
    "late",
    "tentative",
    "absent",
    "not_selected",
    "no_sign",
}


def _copy_player_entry(entry: dict) -> dict:
    return {
        "display_name": entry.get("display_name", ""),
        "name": entry.get("name", ""),
        "class": entry.get("class", ""),
        "spec": entry.get("spec", ""),
        "role": entry.get("role", ""),
        "note": entry.get("note", ""),
    }


def _normalize_player_map(players: list[tuple[str, dict]]) -> dict[str, dict]:
    normalized: dict[str, dict] = {}

    for user_id, entry in players:
        normalized[str(user_id)] = dict(entry)

    return normalized


def _derive_auto_snapshot_players(comp_data: dict) -> dict[str, dict]:
    """
    Build automatic attendance state from comp snapshot.

    Priority:
    1. group_1 + group_2 -> attending
    2. bench_players -> benched
    3. late_players -> late
    4. tentative_players -> tentative
    5. absence_players -> absent
    6. signed but not selected/bench/etc -> not_selected
    """
    players: dict[str, dict] = {}

    group_1 = _normalize_player_map(comp_data.get("group_1", []))
    group_2 = _normalize_player_map(comp_data.get("group_2", []))
    bench_players = _normalize_player_map(comp_data.get("bench_players", []))
    late_players = _normalize_player_map(comp_data.get("late_players", []))
    tentative_players = _normalize_player_map(comp_data.get("tentative_players", []))
    absence_players = _normalize_player_map(comp_data.get("absence_players", []))
    signed_players = _normalize_player_map(comp_data.get("signed_players", []))

    def apply_bucket(source: dict[str, dict], attendance_status: str, signup_status: str) -> None:
        for user_id, entry in source.items():
            players[user_id] = {
                **_copy_player_entry(entry),
                "user_id": user_id,
                "signup_status": signup_status,
                "auto_status": attendance_status,
                "attendance_status": attendance_status,
                "status_source": "auto",
                "manual_override": False,
            }

    apply_bucket(group_1, "attending", "sign")
    apply_bucket(group_2, "attending", "sign")
    apply_bucket(bench_players, "benched", "bench")
    apply_bucket(late_players, "late", "late")
    apply_bucket(tentative_players, "tentative", "tentative")
    apply_bucket(absence_players, "absent", "absence")

    for user_id, entry in signed_players.items():
        if user_id in players:
            continue

        players[user_id] = {
            **_copy_player_entry(entry),
            "user_id": user_id,
            "signup_status": "sign",
            "auto_status": "not_selected",
            "attendance_status": "not_selected",
            "status_source": "auto",
            "manual_override": False,
        }

    return players


def _merge_with_existing_players(
    existing_players: dict[str, dict],
    auto_players: dict[str, dict],
) -> dict[str, dict]:
    """
    Rebuild auto snapshot while preserving manual overrides.
    """
    merged: dict[str, dict] = {}

    for user_id, auto_entry in auto_players.items():
        existing = existing_players.get(user_id, {})
        manual_override = bool(existing.get("manual_override"))

        if manual_override:
            merged[user_id] = {
                **auto_entry,
                "attendance_status": existing.get(
                    "attendance_status",
                    auto_entry["attendance_status"],
                ),
                "status_source": "manual",
                "manual_override": True,
                "edited_by": existing.get("edited_by"),
                "edited_at": existing.get("edited_at"),
            }
        else:
            merged[user_id] = {
                **auto_entry,
                "status_source": "auto",
                "manual_override": False,
                "edited_by": existing.get("edited_by"),
                "edited_at": existing.get("edited_at"),
            }

    # Preserve manual-only extra players not present in auto snapshot
    for user_id, existing in existing_players.items():
        if user_id in merged:
            continue

        if existing.get("manual_override"):
            merged[user_id] = existing

    return merged


def _append_history(
    record: dict,
    action: str,
    by_user_id: int | str | None = None,
    extra: dict | None = None,
) -> None:
    entry = {
        "timestamp": int(time.time()),
        "action": action,
        "by_user_id": str(by_user_id) if by_user_id is not None else None,
    }
    if extra:
        entry.update(extra)

    history = record.setdefault("history", [])
    history.append(entry)


def sync_attendance_from_comp(
    *,
    raid_id: int | str,
    guild_id: int | str | None,
    channel_id: int | str | None,
    comp_message_id: int | str | None,
    comp_data: dict,
    actor_user_id: int | str | None = None,
) -> dict:
    data = load_attendance()
    record = get_or_create_attendance_record(data, raid_id)

    record["guild_id"] = int(guild_id) if guild_id is not None else None
    record["channel_id"] = int(channel_id) if channel_id is not None else None
    record["title"] = comp_data.get("title", "")
    record["description"] = comp_data.get("description", "")
    record["leader"] = comp_data.get("leader", "")
    record["start_ts"] = comp_data.get("start_ts")
    record["comp_message_id"] = int(comp_message_id) if comp_message_id is not None else None
    record["snapshot_source"] = "comp_post"
    record["snapshot_version"] = int(record.get("snapshot_version", 0)) + 1

    existing_players = record.get("players", {})
    auto_players = _derive_auto_snapshot_players(comp_data)
    merged_players = _merge_with_existing_players(existing_players, auto_players)

    first_create = not bool(existing_players)
    record["players"] = merged_players

    # New desired behavior:
    # attendance becomes official immediately when comp is posted
    record["finalized"] = True
    if not record.get("finalized_at"):
        record["finalized_at"] = int(time.time())
    if not record.get("finalized_by"):
        record["finalized_by"] = "auto_comp_post"

    if first_create:
        _append_history(
            record,
            "attendance_snapshot_created",
            by_user_id=actor_user_id,
            extra={"snapshot_version": record["snapshot_version"]},
        )
        _append_history(
            record,
            "attendance_auto_finalized",
            by_user_id=actor_user_id,
        )
    else:
        _append_history(
            record,
            "attendance_snapshot_synced",
            by_user_id=actor_user_id,
            extra={"snapshot_version": record["snapshot_version"]},
        )

    save_attendance(data)
    return record


def get_attendance_record(raid_id: int | str) -> dict | None:
    data = load_attendance()
    return data.get(str(raid_id))


def summarize_attendance_record(record: dict | None) -> dict[str, int]:
    summary = {
        "attending": 0,
        "benched": 0,
        "late": 0,
        "tentative": 0,
        "absent": 0,
        "not_selected": 0,
        "no_sign": 0,
    }

    if not record:
        return summary

    for player in record.get("players", {}).values():
        status = player.get("attendance_status")
        if status in summary:
            summary[status] += 1

    return summary


def _ensure_player_exists_for_manual_edit(
    *,
    record: dict,
    user_id: int | str,
) -> dict:
    players = record.setdefault("players", {})
    key = str(user_id)

    if key not in players:
        players[key] = {
            "display_name": f"User {key}",
            "name": "",
            "class": "",
            "spec": "",
            "role": "",
            "note": "",
            "user_id": key,
            "signup_status": "no_sign",
            "auto_status": "no_sign",
            "attendance_status": "no_sign",
            "status_source": "manual",
            "manual_override": True,
            "edited_by": None,
            "edited_at": None,
        }

    return players[key]


def set_manual_attendance_status(
    *,
    raid_id: int | str,
    user_id: int | str,
    attendance_status: str,
    edited_by_user_id: int | str | None,
) -> tuple[bool, str]:
    if attendance_status not in VALID_ATTENDANCE_STATUSES:
        return False, "Invalid attendance status."

    data = load_attendance()
    record = data.get(str(raid_id))
    if not record:
        return False, "Attendance record not found."

    player = _ensure_player_exists_for_manual_edit(
        record=record,
        user_id=user_id,
    )

    player["attendance_status"] = attendance_status
    player["manual_override"] = True
    player["status_source"] = "manual"
    player["edited_by"] = str(edited_by_user_id) if edited_by_user_id is not None else None
    player["edited_at"] = int(time.time())

    # keep official/finalized state true even after edits
    record["finalized"] = True

    _append_history(
        record,
        "attendance_player_updated",
        by_user_id=edited_by_user_id,
        extra={
            "target_user_id": str(user_id),
            "attendance_status": attendance_status,
        },
    )

    save_attendance(data)
    return True, "Attendance updated."


def reset_player_to_auto_status(
    *,
    raid_id: int | str,
    user_id: int | str,
    edited_by_user_id: int | str | None,
) -> tuple[bool, str]:
    data = load_attendance()
    record = data.get(str(raid_id))
    if not record:
        return False, "Attendance record not found."

    players = record.get("players", {})
    player = players.get(str(user_id))
    if not player:
        return False, "Player not found in attendance record."

    player["attendance_status"] = player.get("auto_status", "not_selected")
    player["manual_override"] = False
    player["status_source"] = "auto"
    player["edited_by"] = str(edited_by_user_id) if edited_by_user_id is not None else None
    player["edited_at"] = int(time.time())

    record["finalized"] = True

    _append_history(
        record,
        "attendance_player_reset_to_auto",
        by_user_id=edited_by_user_id,
        extra={"target_user_id": str(user_id)},
    )

    save_attendance(data)
    return True, "Attendance reset to automatic value."