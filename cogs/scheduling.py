from __future__ import annotations

import discord
from discord.ext import commands

from services.scheduling.scheduling_service import (
    create_scheduling_panel,
    set_panel_message_id,
    build_scheduling_content,
)

from views.scheduling.scheduling_message_view import SchedulingMessageView


class SchedulingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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


async def setup(bot):
    await bot.add_cog(SchedulingCommands(bot))