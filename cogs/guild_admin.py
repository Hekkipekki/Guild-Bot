import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from data.guild_data import ensure_guild_files

from utils.discord_utils import send_ephemeral_error, delete_interaction_after
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    SLASH_PANEL_AUTO_DELETE_SECONDS,
)
from views.guild_admin.guild_admin_helpers import build_guild_config_embed
from views.guild_admin.guild_admin_view import GuildSetupView


def _is_guild_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    return getattr(user.guild_permissions, "administrator", False)


class GuildAdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _deny_if_not_admin(self, interaction: discord.Interaction) -> bool:
        if _is_guild_admin(interaction):
            return False

        await send_ephemeral_error(
            interaction,
            "⛔ You must be a server administrator to use this command.",
            delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
        )
        return True

    async def _get_guild_or_fail(
        self,
        interaction: discord.Interaction,
    ) -> discord.Guild | None:
        guild = interaction.guild
        if guild is None:
            await send_ephemeral_error(
                interaction,
                "⚠ This command can only be used in a server.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return None
        return guild

    @app_commands.command(name="setup", description="Open the server setup panel.")
    async def setup_panel(self, interaction: discord.Interaction):
        if await self._deny_if_not_admin(interaction):
            return

        guild = await self._get_guild_or_fail(interaction)
        if guild is None:
            return

        ensure_guild_files(guild.id)

        await interaction.response.send_message(
            embed=build_guild_config_embed(guild),
            view=GuildSetupView(),
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SLASH_PANEL_AUTO_DELETE_SECONDS)
        )


async def setup(bot):
    await bot.add_cog(GuildAdminCommands(bot))