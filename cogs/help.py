import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.discord_utils import delete_interaction_after
from utils.ui_timing import SLASH_PANEL_AUTO_DELETE_SECONDS
from views.help.help_view import build_help_home_embed, HelpView


class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Open the bot help panel.")
    async def help_panel(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=build_help_home_embed(),
            view=HelpView(),
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SLASH_PANEL_AUTO_DELETE_SECONDS)
        )


async def setup(bot):
    await bot.add_cog(HelpCommands(bot))