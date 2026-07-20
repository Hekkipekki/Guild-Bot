from __future__ import annotations

from datetime import date

from data.scheduling_store import get_panel, load_scheduling, save_scheduling


def remove_user_absences(
    guild_id: int | str,
    panel_id: str,
    *,
    user_id: int | str,
    future_only: bool = True,
) -> int:
    """Remove a user's saved scheduling absences.

    By default, only today's and future absences are removed. Past records are left
    untouched until the normal scheduling cleanup removes them.
    """

    data = load_scheduling(guild_id)
    panel = get_panel(data, str(panel_id))
    if not panel:
        return 0

    absences = panel.setdefault("absences", {})
    wanted_user_id = str(user_id)
    today_iso = date.today().isoformat()
    removed = 0

    for date_iso in list(absences.keys()):
        if future_only and date_iso < today_iso:
            continue

        players = absences.get(date_iso)
        if not isinstance(players, dict):
            continue

        if players.pop(wanted_user_id, None) is not None:
            removed += 1

        if not players:
            absences.pop(date_iso, None)

    if removed:
        save_scheduling(guild_id, data)

    return removed
