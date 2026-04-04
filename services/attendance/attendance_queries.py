from __future__ import annotations

from typing import Any, Callable


def get_reference_guild_id(
    attendance_record_getter: Callable[[str], dict[str, Any] | None],
    current_raid_id: str,
    signup_record_getter: Callable[[str], dict[str, Any] | None] | None = None,
) -> int | None:
    """
    Resolve the guild id for the attendance panel.

    Preferred source:
    1. attendance record for the current raid id
    2. signup record for the current raid id

    This allows the attendance edit panel to be opened from a current/live raid
    even if that specific raid has not created an attendance snapshot yet.
    """
    record = attendance_record_getter(current_raid_id)
    if record:
        guild_id = record.get("guild_id")
        if guild_id is not None:
            return int(guild_id)

    if signup_record_getter is not None:
        signup = signup_record_getter(current_raid_id)
        if signup:
            guild_id = signup.get("guild_id")
            if guild_id is not None:
                return int(guild_id)

    return None


def get_sorted_attendance_players(
    record: dict[str, Any] | None,
) -> list[tuple[str, dict[str, Any]]]:
    if not record:
        return []

    from services.attendance.attendance_rules import get_attendance_status_sort_index

    players = record.get("players", {})

    sortable: list[tuple[int, str, str, dict[str, Any]]] = []
    for user_id, player in players.items():
        display_name = (
            (player.get("name") or "").strip()
            or (player.get("display_name") or "").strip()
            or "Unknown"
        )

        sortable.append(
            (
                get_attendance_status_sort_index(player.get("attendance_status")),
                display_name.lower(),
                str(user_id),
                player,
            )
        )

    sortable.sort(key=lambda item: (item[0], item[1]))
    return [(user_id, player) for _, __, user_id, player in sortable]