from __future__ import annotations

from collections import defaultdict
from typing import Any

from data.attendance_store import load_attendance
from services.attendance.attendance_rules import (
    is_missed_attendance_status,
    is_present_attendance_status,
    normalize_attendance_status,
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_player_name(player: dict) -> str:
    """
    Best available user-facing name for attendance reports.

    Priority:
    1. Stored Discord display name
    2. Character name
    3. Discord user id fallback
    """
    display_name = (player.get("display_name") or "").strip()
    if display_name:
        return display_name

    character_name = (player.get("name") or "").strip()
    if character_name:
        return character_name

    user_id = str(player.get("user_id") or "").strip()
    if user_id:
        return f"Discord {user_id}"

    return "Unknown"


def _get_status_priority(status: str | None) -> int:
    """
    Higher = better

    Priority requested:
    Attended > Benched > Late > Tentative > Absent > Unassigned
    """
    order = {
        "attending": 5,
        "benched": 4,
        "late": 3,
        "tentative": 2,
        "absent": 1,
        "not_selected": 0,
        "no_sign": 0,
        "unknown": 0,
    }
    return order.get(normalize_attendance_status(status), 0)


def _status_counts_for_attendance(status: str | None) -> tuple[int, int]:
    """
    Returns:
    (present_count, missed_count)
    """
    normalized = normalize_attendance_status(status)

    if is_present_attendance_status(normalized):
        return 1, 0
    if is_missed_attendance_status(normalized):
        return 0, 1
    return 0, 0


def _build_raid_summary(record: dict) -> dict:
    return {
        "raid_id": str(record.get("raid_id")),
        "guild_id": _safe_int(record.get("guild_id"), 0),
        "channel_id": _safe_int(record.get("channel_id"), 0),
        "title": record.get("title", "") or "Raid",
        "start_ts": _safe_int(record.get("start_ts"), 0),
        "finalized": bool(record.get("finalized")),
    }


def get_guild_attendance_records(
    guild_id: int | str,
    *,
    finalized_only: bool = True,
) -> list[dict]:
    data = load_attendance()
    guild_id_int = _safe_int(guild_id)

    records = []
    for record in data.values():
        if _safe_int(record.get("guild_id"), 0) != guild_id_int:
            continue

        if finalized_only and not record.get("finalized"):
            continue

        records.append(record)

    records.sort(
        key=lambda r: (
            _safe_int(r.get("start_ts"), 0),
            str(r.get("raid_id", "")),
        )
    )
    return records


def build_attendance_matrix(
    guild_id: int | str,
    *,
    finalized_only: bool = True,
    limit_raids: int | None = None,
) -> dict:
    """
    Returns a render-friendly matrix structure:

    {
        "guild_id": ...,
        "raids": [...],
        "players": [
            {
                "user_id": "...",
                "name": "...",
                "attendance_pct": 90,
                "present_count": 9,
                "missed_count": 1,
                "raid_statuses": {
                    "raid_id_1": "attending",
                    "raid_id_2": "benched",
                    ...
                }
            }
        ]
    }
    """
    records = get_guild_attendance_records(guild_id, finalized_only=finalized_only)

    if limit_raids is not None and limit_raids > 0:
        records = records[-limit_raids:]

    raids = [_build_raid_summary(record) for record in records]

    players_by_user: dict[str, dict] = defaultdict(
        lambda: {
            "user_id": "",
            "name": "",
            "raid_statuses": {},
            "present_count": 0,
            "missed_count": 0,
            "attendance_pct": 0,
        }
    )

    for record in records:
        raid_id = str(record.get("raid_id"))

        for user_id, player in record.get("players", {}).items():
            user_id = str(user_id)
            status = normalize_attendance_status(player.get("attendance_status"))

            row = players_by_user[user_id]
            row["user_id"] = user_id

            # Prefer stored Discord display name if it appears later.
            candidate_name = _get_player_name(player)
            current_name = (row["name"] or "").strip()
            current_is_fallback = (
                not current_name
                or current_name == "Unknown"
                or current_name.startswith("Discord ")
            )
            candidate_is_display_name = bool((player.get("display_name") or "").strip())

            if current_is_fallback or candidate_is_display_name:
                row["name"] = candidate_name

            # Merge multiple characters for the same Discord user by keeping
            # the best attendance status for each raid.
            existing_status = row["raid_statuses"].get(raid_id)
            if existing_status is None:
                row["raid_statuses"][raid_id] = status
            elif _get_status_priority(status) > _get_status_priority(existing_status):
                row["raid_statuses"][raid_id] = status

    players = list(players_by_user.values())

    # Recalculate counts from the merged final per-raid statuses.
    for row in players:
        row["present_count"] = 0
        row["missed_count"] = 0

        for status in row["raid_statuses"].values():
            present_add, missed_add = _status_counts_for_attendance(status)
            row["present_count"] += present_add
            row["missed_count"] += missed_add

        denom = row["present_count"] + row["missed_count"]
        row["attendance_pct"] = (
            round((row["present_count"] / denom) * 100) if denom > 0 else 0
        )

    players.sort(
        key=lambda row: (
            -row["attendance_pct"],
            -row["present_count"],
            row["name"].lower(),
            row["user_id"],
        )
    )

    return {
        "guild_id": _safe_int(guild_id),
        "raids": raids,
        "players": players,
        "finalized_only": finalized_only,
    }


def get_attendance_overview_stats(matrix: dict) -> dict:
    players = matrix.get("players", [])
    raids = matrix.get("raids", [])

    return {
        "raid_count": len(raids),
        "player_count": len(players),
        "average_attendance_pct": round(
            sum(p.get("attendance_pct", 0) for p in players) / len(players)
        ) if players else 0,
    }