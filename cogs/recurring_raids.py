import time

from discord.ext import commands, tasks

from data.signup_store import load_signups, save_signups
from services.raid.raid_recurring_service import (
    should_create_next_recurring,
    build_next_recurring_signup,
    mark_next_recurring_created,
)
from services.signup.signup_message_service import send_signup_message


class _ChannelCtx:
    def __init__(self, channel):
        self.channel = channel

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


class RecurringRaidCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recurring_loop.start()

    def cog_unload(self):
        self.recurring_loop.cancel()

    @tasks.loop(minutes=1)
    async def recurring_loop(self):
        data = load_signups()
        now_ts = int(time.time())
        changed = False

        for raid_id, signup in list(data.items()):
            if not should_create_next_recurring(signup, now_ts):
                continue

            guild_id = signup.get("guild_id")
            channel_id = signup.get("channel_id")

            if not guild_id or not channel_id:
                continue

            guild = self.bot.get_guild(int(guild_id))
            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(int(guild_id))
                except Exception:
                    continue

            channel = guild.get_channel(int(channel_id))
            if channel is None:
                try:
                    channel = await guild.fetch_channel(int(channel_id))
                except Exception:
                    continue

            next_signup = build_next_recurring_signup(signup)

            ok = await send_signup_message(_ChannelCtx(channel), next_signup)
            if not ok:
                continue

            mark_next_recurring_created(signup)
            changed = True

        if changed:
            save_signups(data)

    @recurring_loop.before_loop
    async def before_recurring_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(RecurringRaidCog(bot))