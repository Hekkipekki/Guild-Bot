from __future__ import annotations

import time

import discord
from discord.ext import commands, tasks

from data.signup_store import load_signups, save_signups
from services.attendance.attendance_service import sync_attendance_from_comp
from services.raid.raid_lifecycle_service import (
    build_next_recurring_signup,
    is_recurring_signup,
    is_signup_due_for_lifecycle,
)
from services.scheduling.scheduling_signup_sync_service import apply_scheduled_absences_to_signup
from services.signup.signup_message_service import send_signup_message


class _ChannelCtx:
    def __init__(self, guild, channel):
        self.guild = guild
        self.channel = channel

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


async def _delete_message_if_exists(channel, message_id: int | str | None) -> bool:
    if not message_id:
        return False

    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        return True

    except discord.NotFound:
        return False

    except discord.Forbidden:
        print(f"[Lifecycle] Missing permission to delete message {message_id}")
        return False

    except discord.HTTPException as e:
        print(f"[Lifecycle] Failed to delete message {message_id}: {e}")
        return False

    except (TypeError, ValueError):
        return False


async def _resolve_signup_channel(bot, signup: dict):
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

    except discord.HTTPException as e:
        print(f"[Lifecycle] Could not resolve guild/channel: {e}")
        return None, None

    except (TypeError, ValueError) as e:
        print(f"[Lifecycle] Invalid guild/channel ID: {e}")
        return None, None


async def _delete_old_raid_messages(bot, raid_id: str, signup: dict) -> None:
    _, channel = await _resolve_signup_channel(bot, signup)

    if channel is None:
        print(f"[Lifecycle] Could not delete old raid messages for {raid_id}: channel not found")
        return

    await _delete_message_if_exists(channel, raid_id)
    await _delete_message_if_exists(channel, signup.get("comp_message_id"))
    await _delete_message_if_exists(channel, signup.get("missing_reminder_message_id"))
    await _delete_message_if_exists(channel, signup.get("signed_reminder_message_id"))


def _sync_attendance_snapshot_if_possible(raid_id: str, signup: dict) -> None:
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
        print(f"[Lifecycle] Attendance sync failed before cleanup for raid {raid_id}: {e}")


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
            raid_id = str(raid_id)

            if not isinstance(signup, dict):
                raid_ids_to_remove.append(raid_id)
                changed = True
                continue

            if not is_signup_due_for_lifecycle(signup, now_ts):
                continue

            print(f"[Lifecycle] Processing expired raid {raid_id}: {signup.get('title')}")

            _sync_attendance_snapshot_if_possible(raid_id, signup)

            if is_recurring_signup(signup):
                guild, channel = await _resolve_signup_channel(self.bot, signup)

                if guild is None or channel is None:
                    print(f"[Lifecycle] Could not create next recurring raid for {raid_id}: channel not found")
                    continue

                next_signup = build_next_recurring_signup(signup, now_ts)
                scheduled_absences = apply_scheduled_absences_to_signup(next_signup)

                if scheduled_absences:
                    print(
                        f"[Lifecycle] Applied {scheduled_absences} scheduled absence(s) "
                        f"to next recurring raid from old raid {raid_id}"
                    )

                new_message_id = await send_signup_message(
                    _ChannelCtx(guild, channel),
                    next_signup,
                )

                if not new_message_id:
                    print(f"[Lifecycle] Failed to create next recurring signup for {raid_id}")
                    continue

                data[str(new_message_id)] = next_signup
                changed = True

                print(
                    f"[Lifecycle] Created next recurring raid {new_message_id} "
                    f"from old raid {raid_id}"
                )

            await _delete_old_raid_messages(self.bot, raid_id, signup)
            raid_ids_to_remove.append(raid_id)

        for raid_id in raid_ids_to_remove:
            if raid_id in data:
                del data[raid_id]
                changed = True
                print(f"[Lifecycle] Removed old signup entry {raid_id} from signups.json")

        if changed:
            save_signups(data)

    @lifecycle_loop.before_loop
    async def before_lifecycle_loop(self):
        await self.bot.wait_until_ready()
        print("Raid lifecycle system active.")


async def setup(bot):
    await bot.add_cog(RaidLifecycleCog(bot))
