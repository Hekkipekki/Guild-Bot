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


INACTIVE_SIGNUP_STATUSES = {
    "cancelled",
    "canceled",
    "cancelled",
    "closed",
    "inactive",
    "paused",
    "pause",
    "archived",
    "deleted",
}


def _is_falsey_flag(value) -> bool:
    return value is False or str(value).lower() in {"false", "0", "no", "off"}


def _is_truthy_flag(value) -> bool:
    return value is True or str(value).lower() in {"true", "1", "yes", "on"}


def _is_signup_marked_inactive(signup: dict) -> bool:
    """
    Defensive guard for the different ways a raid can be made inactive.
    Existing data may use either explicit booleans or a status/state string.
    """
    if _is_falsey_flag(signup.get("is_active")):
        return True

    if _is_falsey_flag(signup.get("active")):
        return True

    if _is_falsey_flag(signup.get("reminders_enabled")):
        return True

    for key in ("is_cancelled", "is_canceled", "cancelled", "canceled"):
        if _is_truthy_flag(signup.get(key)):
            return True

    status = str(signup.get("status") or signup.get("state") or "").lower()
    return status in INACTIVE_SIGNUP_STATUSES


def _is_signup_paused(signup: dict, now_ts: int) -> bool:
    pause_until_ts = signup.get("recurring_pause_until_ts")

    if not isinstance(pause_until_ts, int):
        return False

    return now_ts < pause_until_ts


def _is_signup_eligible_for_reminders(signup: dict, now_ts: int) -> bool:
    if _is_signup_marked_inactive(signup):
        return False

    if _is_signup_paused(signup, now_ts):
        return False

    return True


async def _fetch_channel(bot, channel_id: int):
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except Exception:
        return None


async def _fetch_message(channel, message_id: int | str | None):
    if not message_id:
        return None

    try:
        return await channel.fetch_message(int(message_id))
    except Exception:
        return None


async def _delete_message_if_exists(channel, message_id: int | str | None) -> bool:
    msg = await _fetch_message(channel, message_id)
    if msg is None:
        return False

    try:
        await msg.delete()
        return True
    except Exception:
        return False


async def _delete_stored_reminders(channel, signup: dict) -> bool:
    changed = False

    for key in ("missing_reminder_message_id", "signed_reminder_message_id"):
        message_id = signup.get(key)

        if not message_id:
            continue

        await _delete_message_if_exists(channel, message_id)
        signup[key] = None
        changed = True

    return changed


async def _replace_message(
    channel,
    old_message_id: int | str | None,
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

            # Do not keep reminder messages alive for paused/cancelled/disabled raids.
            if not _is_signup_eligible_for_reminders(signup, now):
                if await _delete_stored_reminders(channel, signup):
                    changed = True
                continue

            # If the original signup message is gone, the raid is no longer "up".
            # Clear any lingering reminder messages and do not send new ones.
            if await _fetch_message(channel, raid_id) is None:
                if await _delete_stored_reminders(channel, signup):
                    changed = True
                continue

            missing_reminders_sent = ensure_missing_signup_reminder_state(signup)
            signed_reminders_sent = ensure_signed_player_reminder_state(signup)
            title = get_signup_title(signup)

            missing_reminder_message_id = signup.get("missing_reminder_message_id")
            signed_reminder_message_id = signup.get("signed_reminder_message_id")
            comp_message_id = signup.get("comp_message_id")

            # Live hotfix:
            # Once a comp has been posted / attendance has been created,
            # stop all signup reminder handling for this raid.
            if comp_message_id or signup.get("attendance_snapshot_created"):
                if await _delete_stored_reminders(channel, signup):
                    changed = True
                continue

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
            #
            # Disabled by the hotfix above, because live should not post
            # any reminders after comp has been posted.
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
