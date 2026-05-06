from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.signup.signup_preset_service import build_signup_payload


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def is_valid_recurring_signup(signup: dict) -> bool:
    if not isinstance(signup, dict):
        return False

    if not signup.get("is_recurring", False):
        return False

    interval = signup.get("recurring_interval_days")
    if not isinstance(interval, int):
        return False

    if interval <= 0:
        return False

    start_ts = signup.get("start_ts")
    if not isinstance(start_ts, int):
        return False

    guild_id = signup.get("guild_id")
    channel_id = signup.get("channel_id")

    if not guild_id or not channel_id:
        return False

    return True


def has_next_recurring_already_been_created(signup: dict) -> bool:
    return bool(signup.get("recurring_created_next", False))


def should_create_next_recurring(signup: dict, now_ts: int) -> bool:
    if not is_valid_recurring_signup(signup):
        return False

    if has_next_recurring_already_been_created(signup):
        return False

    start_ts = signup.get("start_ts")
    return isinstance(start_ts, int) and start_ts <= now_ts


def mark_next_recurring_created(signup: dict) -> None:
    signup["recurring_created_next"] = True


def calculate_next_start_ts(start_ts: int, interval_days: int) -> int:
    current_dt = datetime.fromtimestamp(start_ts, tz=SWEDEN_TZ)
    next_dt = current_dt + timedelta(days=interval_days)
    return int(next_dt.timestamp())


def build_next_recurring_signup(previous_signup: dict) -> dict:
    guild_id = int(previous_signup["guild_id"])
    channel_id = int(previous_signup["channel_id"])
    interval_days = int(previous_signup["recurring_interval_days"])
    previous_start_ts = int(previous_signup["start_ts"])

    next_start_ts = calculate_next_start_ts(previous_start_ts, interval_days)

    signup = build_signup_payload(
        guild_id=guild_id,
        title=previous_signup.get("title", "New Raid Signup"),
        description=previous_signup.get("description", ""),
        leader=previous_signup.get("leader", ""),
        start_ts=next_start_ts,
        channel_id=channel_id,
    )

    signup["is_recurring"] = True
    signup["recurring_interval_days"] = interval_days
    signup["recurring_created_next"] = False

    return signup