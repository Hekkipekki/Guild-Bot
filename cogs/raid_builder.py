import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.discord_utils import send_ephemeral_error, delete_interaction_after
from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    SLASH_PANEL_AUTO_DELETE_SECONDS,
)
from views.raid_builder import RaidStartView


class RaidBuilderCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="raid", description="Open the raid creation panel.")
    async def raid(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await send_ephemeral_error(
                interaction,
                "⛔ You do not have access to create raids.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        guild = interaction.guild
        channel = interaction.channel

        if guild is None or channel is None:
            await send_ephemeral_error(
                interaction,
                "⚠ This command can only be used in a server.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        await interaction.response.send_message(
            "Raid setup",
            view=RaidStartView(guild.id, channel.id),
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SLASH_PANEL_AUTO_DELETE_SECONDS)
        )


async def setup(bot):
    await bot.add_cog(RaidBuilderCommands(bot))