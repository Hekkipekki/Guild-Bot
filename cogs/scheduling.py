from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from services.scheduling.scheduling_panel_service import ensure_scheduling_panel_for_guild
from services.scheduling.scheduling_service import (
    create_scheduling_panel,
    set_panel_message_id,
    build_scheduling_content,
)

from views.scheduling.scheduling_message_view import SchedulingMessageView


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")
# Run after both Swedish and UTC midnight so date.today()-based scheduling data
# has rolled over on PebbleHost regardless of daylight-saving time.
SCHEDULING_REFRESH_TIME = time(hour=3, minute=5, tzinfo=SWEDEN_TZ)


class SchedulingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_scheduling_refresh.start()

    def cog_unload(self):
        self.daily_scheduling_refresh.cancel()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def scheduling(self, ctx: commands.Context):
        if ctx.guild is None:
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        panel_id = create_scheduling_panel(
            ctx.guild.id,
            ctx.channel.id,
        )

        msg = await ctx.send(
            content=build_scheduling_content(ctx.guild.id, panel_id),
            view=SchedulingMessageView(panel_id),
        )

        set_panel_message_id(ctx.guild.id, panel_id, msg.id)

    @tasks.loop(time=SCHEDULING_REFRESH_TIME)
    async def daily_scheduling_refresh(self):
        for guild in self.bot.guilds:
            try:
                ok, message = await ensure_scheduling_panel_for_guild(self.bot, guild)
                if ok:
                    print(f"[Scheduling] {guild.name}: daily rollover refresh complete.")
                elif message != "No Scheduling channel configured.":
                    print(f"[Scheduling] {guild.name}: daily rollover refresh skipped - {message}")
            except Exception as exc:
                print(f"[Scheduling] {guild.name}: daily rollover refresh failed - {exc}")

    @daily_scheduling_refresh.before_loop
    async def before_daily_scheduling_refresh(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(SchedulingCommands(bot))
