from __future__ import annotations

from data.signup_store import find_message_signup, load_signups, save_signups
from services.raid.raid_cancel_service import cancel_signup_raid


def _disable_cancelled_raid_reminders(raid_id: int | str) -> None:
    raid_key = str(raid_id)
    data = load_signups()
    signup = find_message_signup(data, raid_key)

    if not signup:
        return

    signup["status"] = "cancelled"
    signup["state"] = "cancelled"
    signup["is_cancelled"] = True
    signup["reminders_enabled"] = False

    data[raid_key] = signup
    save_signups(data)


async def cancel_signup_raid_with_guard(
    *,
    bot,
    raid_id: int | str,
    cancel_message: str,
) -> tuple[bool, str]:
    _disable_cancelled_raid_reminders(raid_id)

    return await cancel_signup_raid(
        bot=bot,
        raid_id=raid_id,
        cancel_message=cancel_message,
    )
