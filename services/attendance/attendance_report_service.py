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
    return (
        (player.get("name") or "").strip()
        or (player.get("display_name") or "").strip()
        or f"User {player.get('user_id', 'Unknown')}"
    )


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
            row["name"] = _get_player_name(player)
            row["raid_statuses"][raid_id] = status

            present_add, missed_add = _status_counts_for_attendance(status)
            row["present_count"] += present_add
            row["missed_count"] += missed_add

    players = list(players_by_user.values())

    for row in players:
        denom = row["present_count"] + row["missed_count"]
        row["attendance_pct"] = round((row["present_count"] / denom) * 100) if denom > 0 else 0

    players.sort(
        key=lambda row: (
            -row["attendance_pct"],
            -row["present_count"],
            row["name"].lower(),
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