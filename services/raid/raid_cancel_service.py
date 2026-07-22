from __future__ import annotations

import time

import discord

from data.attendance_store import load_attendance, save_attendance
from data.signup_store import (
    find_message_signup,
    load_signups,
    remove_signup_by_message_id,
    save_signups,
)
from services.raid.raid_lifecycle_service import (
    build_next_recurring_signup,
    is_recurring_signup,
)
from services.scheduling.scheduling_signup_sync_service import apply_scheduled_absences_to_signup


NOTIFY_STATUSES = {"sign", "bench", "late", "tentative"}


class _ChannelCtx:
    def __init__(self, guild, channel):
        self.guild = guild
        self.channel = channel

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


def _get_notify_user_ids(signup: dict) -> list[str]:
    users = signup.get("users", {})

    return [
        str(user_id)
        for user_id, entry in users.items()
        if entry.get("status") in NOTIFY_STATUSES and str(user_id).isdigit()
    ]


async def _fetch_signup_guild_and_channel(bot, signup: dict):
    guild_id = signup.get("guild_id")
    channel_id = signup.get("channel_id")

    if not guild_id or not channel_id:
        return None, None

    try:
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            guild = await bot.fetch_guild(int(guild_id))
        channel = guild.get_channel(int(channel_id))
        if channel is None:
            channel = await guild.fetch_channel(int(channel_id))

        return guild, channel

    except Exception:
        return None, None


async def _delete_message_if_exists(channel, message_id: int | str | None) -> bool:
    if not message_id:
        return False

    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        return True

    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException,
        TypeError,
        ValueError,
    ):
        return False


def _remove_attendance_record(raid_id: str) -> None:
    attendance = load_attendance()

    if raid_id not in attendance:
        return

    del attendance[raid_id]
    save_attendance(attendance)


async def cancel_signup_raid(
    *,
    bot,
    raid_id: int | str,
    cancel_message: str,
    plan_next_occurrence: bool = False,
) -> tuple[bool, str]:
    raid_key = str(raid_id)

    data = load_signups()
    signup = find_message_signup(data, raid_key)

    if not signup:
        return False, "Raid signup not found."

    guild, channel = await _fetch_signup_guild_and_channel(bot, signup)
    if guild is None or channel is None:
        return False, "Could not find the signup channel."

    if plan_next_occurrence and not is_recurring_signup(signup):
        return False, "This raid is not recurring, so there is no next occurrence to plan."

    next_message_id = None
    if plan_next_occurrence:
        # Import lazily to avoid this startup cycle:
        # SignupView -> raid control -> cancellation service -> signup message service -> SignupView.
        from services.signup.signup_message_service import send_signup_message

        next_signup = build_next_recurring_signup(signup, int(time.time()))
        apply_scheduled_absences_to_signup(next_signup)

        next_message_id = await send_signup_message(
            _ChannelCtx(guild, channel),
            next_signup,
        )
        if not next_message_id:
            return False, "Could not create the next recurring raid. The current raid was not cancelled."

        data[str(next_message_id)] = next_signup
        save_signups(data)

    title = signup.get("title") or "Raid"
    user_ids = _get_notify_user_ids(signup)
    mentions = " ".join(f"<@{user_id}>" for user_id in user_ids)

    cancel_text = cancel_message.strip() or "Raid has been cancelled."
    next_raid_text = (
        "\n\n✅ The next recurring raid has been planned."
        if next_message_id
        else ""
    )

    await channel.send(
        (
            f"## ❌ Raid Cancelled — {title}\n"
            f"{mentions}\n\n"
            f"{cancel_text}{next_raid_text}"
        ).strip(),
        allowed_mentions=discord.AllowedMentions(
            users=True,
            roles=False,
            everyone=False,
        ),
    )

    await _delete_message_if_exists(channel, signup.get("missing_reminder_message_id"))
    await _delete_message_if_exists(channel, signup.get("signed_reminder_message_id"))
    await _delete_message_if_exists(channel, signup.get("comp_message_id"))
    await _delete_message_if_exists(channel, raid_key)

    removed = remove_signup_by_message_id(raid_key)
    if not removed:
        return False, "Discord messages were handled, but the JSON signup entry could not be removed."

    _remove_attendance_record(raid_key)

    if next_message_id:
        return True, "Raid cancelled and next recurring raid planned."

    return True, "Raid cancelled and removed."
