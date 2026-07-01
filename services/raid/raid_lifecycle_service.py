from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.signup.signup_preset_service import build_signup_payload


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")

RAID_RETENTION_AFTER_START_SECONDS = 60 #30 minutes


def is_signup_due_for_lifecycle(signup: dict, now_ts: int) -> bool:
    start_ts = signup.get("start_ts")

    if not isinstance(start_ts, int):
        return False

    return now_ts >= (start_ts + RAID_RETENTION_AFTER_START_SECONDS)


def is_recurring_signup(signup: dict) -> bool:
    if not bool(signup.get("is_recurring", False)):
        return False

    interval = signup.get("recurring_interval_days")

    return isinstance(interval, int) and interval > 0


def calculate_next_start_ts(
    start_ts: int,
    interval_days: int,
    now_ts: int,
    *,
    not_before_ts: int | None = None,
) -> int:
    """
    Returns the first recurring occurrence that is not already expired.

    Example:
    - original raid: Wednesday 19:30
    - interval: 7 days
    - bot was offline for 3 weeks

    This function skips missed occurrences and returns the first valid
    upcoming/current one in the recurring chain.

    If not_before_ts is provided, occurrences before that timestamp are
    skipped as well. This is used for temporary recurring raid pauses.
    """

    next_dt = datetime.fromtimestamp(start_ts, tz=SWEDEN_TZ)

    next_dt += timedelta(days=interval_days)

    while now_ts >= (int(next_dt.timestamp()) + RAID_RETENTION_AFTER_START_SECONDS):
        next_dt += timedelta(days=interval_days)

    if isinstance(not_before_ts, int):
        while int(next_dt.timestamp()) <= not_before_ts:
            next_dt += timedelta(days=interval_days)

    return int(next_dt.timestamp())


def build_next_recurring_signup(previous_signup: dict, now_ts: int) -> dict:

    guild_id = int(previous_signup["guild_id"])
    channel_id = int(previous_signup["channel_id"])

    previous_start_ts = int(previous_signup.get("start_ts", now_ts))
    interval_days = int(previous_signup["recurring_interval_days"])
    pause_until_ts = previous_signup.get("recurring_pause_until_ts")

    next_start_ts = calculate_next_start_ts(
        previous_start_ts,
        interval_days,
        now_ts,
        not_before_ts=pause_until_ts if isinstance(pause_until_ts, int) else None,
    )

    signup = build_signup_payload(
        guild_id=guild_id,
        title=previous_signup.get("title", "New Raid Signup"),
        description=previous_signup.get("description", ""),
        leader=previous_signup.get("leader", ""),
        start_ts=next_start_ts,
        channel_id=channel_id,
    )

    signup.update(
        {
            "is_recurring": True,
            "recurring_interval_days": interval_days,
        }
    )

    return signup
