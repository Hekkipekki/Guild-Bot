from __future__ import annotations

import discord

from data.attendance_store import load_attendance, save_attendance
from data.signup_store import (
    find_message_signup,
    load_signups,
    remove_signup_by_message_id,
)


NOTIFY_STATUSES = {"sign", "bench", "late", "tentative"}


def _get_notify_user_ids(signup: dict) -> list[str]:
    users = signup.get("users", {})

    return [
        str(user_id)
        for user_id, entry in users.items()
        if entry.get("status") in NOTIFY_STATUSES and str(user_id).isdigit()
    ]


async def _fetch_signup_channel(bot, signup: dict):
    guild_id = signup.get("guild_id")
    channel_id = signup.get("channel_id")

    if not guild_id or not channel_id:
        return None

    try:
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            guild = await bot.fetch_guild(int(guild_id))

        channel = guild.get_channel(int(channel_id))
        if channel is None:
            channel = await guild.fetch_channel(int(channel_id))

        return channel

    except Exception:
        return None


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
) -> tuple[bool, str]:
    raid_key = str(raid_id)

    data = load_signups()
    signup = find_message_signup(data, raid_key)

    if not signup:
        return False, "Raid signup not found."

    channel = await _fetch_signup_channel(bot, signup)
    if channel is None:
        return False, "Could not find the signup channel."

    title = signup.get("title") or "Raid"
    user_ids = _get_notify_user_ids(signup)
    mentions = " ".join(f"<@{user_id}>" for user_id in user_ids)

    cancel_text = cancel_message.strip() or "Raid has been cancelled."

    await channel.send(
        (
            f"## ❌ Raid Cancelled — {title}\n"
            f"{mentions}\n\n"
            f"{cancel_text}"
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

    return True, "Raid cancelled and removed."