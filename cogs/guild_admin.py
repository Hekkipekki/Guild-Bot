import discord
from discord import app_commands
from discord.ext import commands

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

        await interaction.response.send_message(
            "⛔ You must be a server administrator to use this command.",
            ephemeral=True,
        )
        return True

    async def _get_guild_or_fail(
        self,
        interaction: discord.Interaction,
    ) -> discord.Guild | None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
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

        await interaction.response.send_message(
            embed=build_guild_config_embed(guild),
            view=GuildSetupView(),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(GuildAdminCommands(bot))