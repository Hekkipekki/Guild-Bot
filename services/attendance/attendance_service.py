from __future__ import annotations

import time
from typing import Any

from data.attendance_store import (
    get_or_create_attendance_record,
    load_attendance,
    save_attendance,
)
from data.signup_store import find_message_signup, load_signups
from services.attendance.attendance_rules import (
    VALID_ATTENDANCE_STATUSES,
    build_manual_placeholder_player,
    derive_auto_snapshot_players,
    normalize_attendance_status,
)


def _append_history(
    record: dict[str, Any],
    action: str,
    *,
    by_user_id: int | str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    history = record.setdefault("history", [])
    payload = {
        "timestamp": int(time.time()),
        "action": action,
        "by_user_id": str(by_user_id) if by_user_id is not None else None,
    }
    if extra:
        payload.update(extra)
    history.append(payload)


def _get_signup_for_raid(raid_id: int | str) -> dict[str, Any] | None:
    data = load_signups()
    return find_message_signup(data, str(raid_id))


def _get_expected_players_for_raid(raid_id: int | str) -> list[str]:
    signup = _get_signup_for_raid(raid_id)
    if not signup:
        return []

    return [str(user_id) for user_id in signup.get("expected_players", [])]


def _build_auto_no_sign_player(user_id: int | str) -> dict[str, Any]:
    key = str(user_id)
    return {
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
        "status_source": "auto",
        "manual_override": False,
        "edited_by": None,
        "edited_at": None,
    }


def _add_expected_no_sign_players(
    *,
    auto_players: dict[str, dict[str, Any]],
    expected_players: list[str],
) -> dict[str, dict[str, Any]]:
    updated = dict(auto_players)

    for user_id in expected_players:
        key = str(user_id)
        if key in updated:
            continue

        updated[key] = _build_auto_no_sign_player(key)

    return updated


def _merge_snapshot_players(
    *,
    existing_players: dict[str, dict[str, Any]],
    auto_players: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    all_user_ids = set(auto_players.keys()) | set(existing_players.keys())

    for user_id in all_user_ids:
        existing = existing_players.get(user_id, {})
        auto = auto_players.get(user_id)

        if auto is not None:
            player = dict(auto)

            if existing.get("manual_override"):
                player["attendance_status"] = normalize_attendance_status(
                    existing.get("attendance_status"),
                    default=normalize_attendance_status(
                        auto.get("auto_status"),
                        default="not_selected",
                    ),
                )
                player["manual_override"] = True
                player["status_source"] = "manual"
                player["edited_by"] = existing.get("edited_by")
                player["edited_at"] = existing.get("edited_at")
            else:
                player["edited_by"] = existing.get("edited_by")
                player["edited_at"] = existing.get("edited_at")

            merged[user_id] = player
            continue

        if existing:
            player = dict(existing)
            player["user_id"] = str(user_id)
            player["auto_status"] = normalize_attendance_status(
                player.get("auto_status"),
                default="no_sign",
            )
            player["attendance_status"] = normalize_attendance_status(
                player.get("attendance_status"),
                default=player["auto_status"],
            )
            player["status_source"] = "manual" if player.get("manual_override") else "auto"
            merged[user_id] = player

    return merged


def sync_attendance_from_comp(
    *,
    raid_id: int | str,
    guild_id: int | str | None,
    channel_id: int | str | None,
    comp_message_id: int | str | None,
    comp_data: dict[str, Any],
    actor_user_id: int | str | None,
) -> dict[str, Any]:
    data = load_attendance()
    record = get_or_create_attendance_record(data, raid_id)

    expected_players = _get_expected_players_for_raid(raid_id)

    auto_players = derive_auto_snapshot_players(comp_data)
    auto_players = _add_expected_no_sign_players(
        auto_players=auto_players,
        expected_players=expected_players,
    )

    existing_players = record.get("players", {})

    record["raid_id"] = str(raid_id)
    record["guild_id"] = int(guild_id) if guild_id is not None else record.get("guild_id")
    record["channel_id"] = int(channel_id) if channel_id is not None else record.get("channel_id")
    record["title"] = comp_data.get("title", record.get("title", ""))
    record["description"] = comp_data.get("description", record.get("description", ""))
    record["leader"] = comp_data.get("leader", record.get("leader", ""))
    record["start_ts"] = comp_data.get("start_ts", record.get("start_ts"))
    record["comp_message_id"] = (
        int(comp_message_id) if comp_message_id is not None else record.get("comp_message_id")
    )

    record["expected_players"] = expected_players
    record["snapshot_source"] = "comp_post"
    record["snapshot_version"] = 3
    record["players"] = _merge_snapshot_players(
        existing_players=existing_players,
        auto_players=auto_players,
    )
    record["finalized"] = True
    record["finalized_at"] = int(time.time())
    record["finalized_by"] = (
        str(actor_user_id) if actor_user_id is not None else "auto_comp_post"
    )

    _append_history(
        record,
        "attendance_snapshot_created",
        by_user_id=actor_user_id,
        extra={"snapshot_version": 3},
    )
    _append_history(
        record,
        "attendance_auto_finalized",
        by_user_id=actor_user_id,
    )

    save_attendance(data)
    return record


def get_attendance_record(raid_id: int | str) -> dict[str, Any] | None:
    data = load_attendance()
    return data.get(str(raid_id))


def summarize_attendance_record(record: dict[str, Any] | None) -> dict[str, int]:
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
        status = normalize_attendance_status(player.get("attendance_status"), default="")
        if status in summary:
            summary[status] += 1

    return summary


def _ensure_player_exists_for_manual_edit(
    *,
    record: dict[str, Any],
    user_id: int | str,
) -> dict[str, Any]:
    players = record.setdefault("players", {})
    key = str(user_id)

    if key not in players:
        players[key] = build_manual_placeholder_player(key)

    return players[key]


def set_manual_attendance_status(
    *,
    raid_id: int | str,
    user_id: int | str,
    attendance_status: str,
    edited_by_user_id: int | str | None,
) -> tuple[bool, str]:
    normalized_status = normalize_attendance_status(attendance_status, default="")
    if normalized_status not in VALID_ATTENDANCE_STATUSES:
        return False, "Invalid attendance status."

    data = load_attendance()
    record = data.get(str(raid_id))
    if not record:
        return False, "Attendance record not found."

    player = _ensure_player_exists_for_manual_edit(
        record=record,
        user_id=user_id,
    )

    player["attendance_status"] = normalized_status
    player["manual_override"] = True
    player["status_source"] = "manual"
    player["edited_by"] = str(edited_by_user_id) if edited_by_user_id is not None else None
    player["edited_at"] = int(time.time())

    record["finalized"] = True

    _append_history(
        record,
        "attendance_player_updated",
        by_user_id=edited_by_user_id,
        extra={
            "target_user_id": str(user_id),
            "attendance_status": normalized_status,
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

    player["attendance_status"] = normalize_attendance_status(
        player.get("auto_status"),
        default="not_selected",
    )
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