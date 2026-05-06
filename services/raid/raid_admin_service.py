from datetime import datetime
from zoneinfo import ZoneInfo

from data.signup_store import load_signups, save_signups


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def _get_signup(data: dict, raid_id: int | str) -> dict | None:
    return data.get(str(raid_id))


def update_raid_title(raid_id: int | str, new_title: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)
    if not signup:
        return False

    signup["title"] = new_title.strip()
    save_signups(data)
    return True


def update_raid_description(raid_id: int | str, new_description: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)
    if not signup:
        return False

    signup["description"] = new_description.strip()
    save_signups(data)
    return True


def update_raid_leader(raid_id: int | str, new_leader: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)
    if not signup:
        return False

    signup["leader"] = new_leader.strip()
    save_signups(data)
    return True


def update_raid_time_only(raid_id: int | str, new_time: str) -> tuple[bool, int | None, str | None]:
    data = load_signups()
    signup = _get_signup(data, raid_id)
    if not signup:
        return False, None, "Raid signup not found."

    start_ts = signup.get("start_ts")
    if not start_ts:
        return False, None, "Raid has no existing date/time to update."

    try:
        hour_str, minute_str = new_time.strip().split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError:
        return False, None, "Time must be in HH:MM format, for example 19:30."

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return False, None, "Invalid time. Hour must be 00-23 and minute 00-59."

    current_dt = datetime.fromtimestamp(start_ts, tz=SWEDEN_TZ)
    updated_dt = current_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    updated_ts = int(updated_dt.timestamp())

    signup["start_ts"] = updated_ts
    save_signups(data)
    return True, updated_ts, None


def update_raid_date_only(raid_id: int | str, new_date: str) -> tuple[bool, int | None, str | None]:
    data = load_signups()
    signup = _get_signup(data, raid_id)
    if not signup:
        return False, None, "Raid signup not found."

    start_ts = signup.get("start_ts")
    if not start_ts:
        return False, None, "Raid has no existing date/time to update."

    try:
        year_str, month_str, day_str = new_date.strip().split("-")
        year = int(year_str)
        month = int(month_str)
        day = int(day_str)
    except ValueError:
        return False, None, "Date must be in YYYY-MM-DD format, for example 2026-03-15."

    current_dt = datetime.fromtimestamp(start_ts, tz=SWEDEN_TZ)

    try:
        updated_dt = current_dt.replace(year=year, month=month, day=day, second=0, microsecond=0)
    except ValueError as e:
        return False, None, f"Invalid date: {e}"

    updated_ts = int(updated_dt.timestamp())

    signup["start_ts"] = updated_ts
    save_signups(data)
    return True, updated_ts, None