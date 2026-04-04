import time

import discord
from discord.ext import commands, tasks

from data.signup_store import load_signups, save_signups
from services.attendance.attendance_service import sync_attendance_from_comp
from services.raid.raid_lifecycle_service import (
    is_signup_due_for_lifecycle,
    is_recurring_signup,
    build_next_recurring_signup,
)
from services.signup.signup_message_service import send_signup_message


class _ChannelCtx:
    def __init__(self, channel):
        self.channel = channel

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


async def _delete_message_if_exists(channel, message_id: int | None) -> None:
    if not message_id:
        return

    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()

    except discord.NotFound:
        return

    except discord.Forbidden:
        return

    except discord.HTTPException:
        return


async def _delete_old_raid_messages(bot, raid_id: str, signup: dict) -> None:
    guild_id = signup.get("guild_id")
    channel_id = signup.get("channel_id")

    if not guild_id or not channel_id:
        return

    guild = bot.get_guild(int(guild_id))

    if guild is None:
        try:
            guild = await bot.fetch_guild(int(guild_id))
        except discord.HTTPException:
            return

    channel = guild.get_channel(int(channel_id))

    if channel is None:
        try:
            channel = await guild.fetch_channel(int(channel_id))
        except discord.HTTPException:
            return

    await _delete_message_if_exists(channel, int(raid_id))
    await _delete_message_if_exists(channel, signup.get("comp_message_id"))
    await _delete_message_if_exists(channel, signup.get("missing_reminder_message_id"))
    await _delete_message_if_exists(channel, signup.get("signed_reminder_message_id"))


def _sync_attendance_snapshot_if_possible(raid_id: str, signup: dict) -> None:
    """
    Safety net:
    If a comp exists, make sure attendance is synced one last time before
    lifecycle cleanup removes the live signup entry.
    """
    last_comp_data = signup.get("last_comp_data")
    comp_message_id = signup.get("comp_message_id")

    if not last_comp_data or not comp_message_id:
        return

    try:
        sync_attendance_from_comp(
            raid_id=raid_id,
            guild_id=signup.get("guild_id"),
            channel_id=signup.get("channel_id"),
            comp_message_id=comp_message_id,
            comp_data=last_comp_data,
            actor_user_id=None,
        )
    except Exception as e:
        print(f"[Attendance Sync] Failed before lifecycle cleanup for raid {raid_id}: {e}")


class RaidLifecycleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lifecycle_loop.start()

    def cog_unload(self):
        self.lifecycle_loop.cancel()

    @tasks.loop(minutes=1)
    async def lifecycle_loop(self):
        data = load_signups()
        now_ts = int(time.time())

        changed = False
        raid_ids_to_remove: list[str] = []

        for raid_id, signup in list(data.items()):

            if signup.get("lifecycle_processed"):
                continue

            if not is_signup_due_for_lifecycle(signup, now_ts):
                continue

            # Non-recurring raid cleanup
            if not is_recurring_signup(signup):
                _sync_attendance_snapshot_if_possible(str(raid_id), signup)

                await _delete_old_raid_messages(self.bot, str(raid_id), signup)

                raid_ids_to_remove.append(str(raid_id))
                continue

            guild_id = signup.get("guild_id")
            channel_id = signup.get("channel_id")

            if not guild_id or not channel_id:
                continue

            guild = self.bot.get_guild(int(guild_id))

            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(int(guild_id))
                except discord.HTTPException:
                    continue

            channel = guild.get_channel(int(channel_id))

            if channel is None:
                try:
                    channel = await guild.fetch_channel(int(channel_id))
                except discord.HTTPException:
                    continue

            next_signup = build_next_recurring_signup(signup, now_ts)

            new_message_id = await send_signup_message(_ChannelCtx(channel), next_signup)

            if not new_message_id:
                continue

            data[str(new_message_id)] = next_signup
            changed = True

            _sync_attendance_snapshot_if_possible(str(raid_id), signup)

            await _delete_old_raid_messages(self.bot, str(raid_id), signup)

            raid_ids_to_remove.append(str(raid_id))

        for raid_id in raid_ids_to_remove:
            if raid_id in data:
                del data[raid_id]
                changed = True

        if changed:
            save_signups(data)

    @lifecycle_loop.before_loop
    async def before_lifecycle_loop(self):
        await self.bot.wait_until_ready()
        print("Raid lifecycle system active.")


async def setup(bot):
    await bot.add_cog(RaidLifecycleCog(bot))