import time
import discord
from discord.ext import commands, tasks

from data.signup_store import load_signups, save_signups
from services.reminder.reminder_service import (
    ensure_missing_signup_reminder_state,
    ensure_signed_player_reminder_state,
    get_signup_title,
    get_missing_players,
    get_signed_players,
    find_missing_signup_threshold_to_send,
    find_signed_player_threshold_to_send,
    build_missing_signup_reminder_message,
    build_signed_player_reminder_message,
)


async def _fetch_channel(bot, channel_id: int):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except Exception:
        return None


async def _fetch_message(channel, message_id: int | None):
    if not message_id:
        return None

    try:
        return await channel.fetch_message(int(message_id))
    except Exception:
        return None


async def _delete_message_if_exists(channel, message_id: int | None) -> bool:
    msg = await _fetch_message(channel, message_id)
    if msg is None:
        return False

    try:
        await msg.delete()
        return True
    except Exception:
        return False


async def _replace_message(
    channel,
    old_message_id: int | None,
    content: str,
) -> int | None:
    """
    Delete the old reminder message if it exists, then send a fresh one.
    Returns the new message ID, or None on failure.
    """
    if old_message_id:
        await _delete_message_if_exists(channel, old_message_id)

    try:
        msg = await channel.send(content)
        return msg.id
    except Exception:
        return None


class ReminderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        data = load_signups()
        now = int(time.time())
        changed = False

        for raid_id, signup in data.items():
            start_ts = signup.get("start_ts")
            channel_id = signup.get("channel_id")
            guild_id = signup.get("guild_id")

            if not start_ts or not channel_id or not guild_id:
                continue

            seconds_left = start_ts - now
            if seconds_left <= 0:
                continue

            minutes_left = seconds_left // 60

            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                continue

            channel = guild.get_channel(int(channel_id))

            if channel is None:
                try:
                    channel = await guild.fetch_channel(int(channel_id))
                except Exception:
                    continue

            missing_reminders_sent = ensure_missing_signup_reminder_state(signup)
            signed_reminders_sent = ensure_signed_player_reminder_state(signup)
            title = get_signup_title(signup)

            missing_reminder_message_id = signup.get("missing_reminder_message_id")
            signed_reminder_message_id = signup.get("signed_reminder_message_id")
            comp_message_id = signup.get("comp_message_id")

            # -------------------------
            # 1) Missing signup reminders
            # -------------------------
            missing_players = get_missing_players(signup)
            if missing_players:
                threshold_info = find_missing_signup_threshold_to_send(
                    minutes_left,
                    missing_reminders_sent,
                )

                if threshold_info:
                    threshold_str, label = threshold_info

                    content = build_missing_signup_reminder_message(
                        title=title,
                        label=label,
                        start_ts=start_ts,
                        user_ids=missing_players,
                    )

                    active_message_id = await _replace_message(
                        channel,
                        missing_reminder_message_id,
                        content,
                    )

                    if active_message_id:
                        signup["missing_reminder_message_id"] = active_message_id
                        missing_reminders_sent[threshold_str] = True
                        changed = True

            # -------------------------
            # 2) Signed player reminder
            # Only send if a comp has been posted
            # -------------------------
            signed_players = get_signed_players(signup)
            if signed_players and comp_message_id:
                threshold_info = find_signed_player_threshold_to_send(
                    minutes_left,
                    signed_reminders_sent,
                )

                if threshold_info:
                    threshold_str, label = threshold_info

                    # remove missing reminder first to keep channel clean
                    if missing_reminder_message_id:
                        await _delete_message_if_exists(channel, missing_reminder_message_id)
                        signup["missing_reminder_message_id"] = None
                        changed = True

                    content = build_signed_player_reminder_message(
                        title=title,
                        label=label,
                        start_ts=start_ts,
                        user_ids=signed_players,
                    )

                    active_message_id = await _replace_message(
                        channel,
                        signed_reminder_message_id,
                        content,
                    )

                    if active_message_id:
                        signup["signed_reminder_message_id"] = active_message_id
                        signed_reminders_sent[threshold_str] = True
                        changed = True

        if changed:
            save_signups(data)

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ReminderCog(bot))