from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from data.scheduling_store import load_scheduling, get_panel


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def _get_signup_raid_date(signup: dict) -> str | None:
    start_ts = signup.get("start_ts")

    if not isinstance(start_ts, int):
        return None

    return datetime.fromtimestamp(start_ts, tz=SWEDEN_TZ).date().isoformat()


def get_scheduled_absences_for_date(
    guild_id: int | str,
    date_iso: str,
) -> dict[str, dict]:
    data = load_scheduling(guild_id)
    panel = get_panel(data, str(guild_id))

    if not panel:
        return {}

    absences = panel.get("absences", {})
    players = absences.get(date_iso, {})

    return players if isinstance(players, dict) else {}


def _get_scheduled_absence_note(absence: dict) -> str:
    return (absence.get("reason") or "Scheduled absence").strip()


def _apply_absence_to_signup_entry(entry: dict, absence: dict) -> None:
    entry["status"] = "absence"
    entry["note"] = _get_scheduled_absence_note(absence)
    entry["timestamp"] = time.time()
    entry["source"] = "scheduling"

    if absence.get("name") and not entry.get("display_name"):
        entry["display_name"] = absence["name"]

    entry.setdefault("display_name", absence.get("name") or "")
    entry.setdefault("name", "")
    entry.setdefault("class", "")
    entry.setdefault("spec", "Unknown")
    entry.setdefault("role", "DPS")


def _build_signup_absence_entry(absence: dict) -> dict:
    entry: dict = {}
    _apply_absence_to_signup_entry(entry, absence)
    return entry


def apply_scheduled_absences_to_signup(signup: dict) -> int:
    guild_id = signup.get("guild_id")
    if guild_id in (None, "", 0):
        return 0

    raid_date = _get_signup_raid_date(signup)
    if not raid_date:
        return 0

    scheduled_absences = get_scheduled_absences_for_date(
        guild_id,
        raid_date,
    )

    if not scheduled_absences:
        return 0

    users = signup.setdefault("users", {})
    applied = 0

    for user_id, absence in scheduled_absences.items():
        user_id = str(user_id)

        if user_id in users:
            _apply_absence_to_signup_entry(users[user_id], absence)
        else:
            users[user_id] = _build_signup_absence_entry(absence)

        applied += 1

    return applied
