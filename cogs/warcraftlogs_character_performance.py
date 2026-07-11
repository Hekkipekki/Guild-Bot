from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

import config
from services.warcraftlogs.api_client import (
    WarcraftLogsAuthenticationError,
    WarcraftLogsClient,
    WarcraftLogsConfigurationError,
    WarcraftLogsRequestError,
)
from services.warcraftlogs.character_performance_service import (
    WarcraftLogsCharacterPerformanceService,
)
from services.warcraftlogs.credentials import get_warcraftlogs_credentials
from services.warcraftlogs.debug_service import build_debug_json_bytes
from services.warcraftlogs.settings_service import get_warcraftlogs_settings
from views.warcraftlogs_character_view import (
    WarcraftLogsCharacterView,
    build_character_card_embed,
)


class WarcraftLogsCharacterPerformanceCommands(commands.Cog):
    """Historical character ranking cards attached to the existing /logs group."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.character_service = WarcraftLogsCharacterPerformanceService(self.client)
        self.player_command = app_commands.Command(
            name="player",
            description="Show a character's Normal/Heroic damage and healing top parses.",
            callback=self.player,
        )
        self.debug_character_command = app_commands.Command(
            name="debug-character",
            description="DEV only: export raw character ranking payloads.",
            callback=self.debug_character,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("player")
            logs_group.remove_command("debug-character")
        await self.client.close()

    async def player(
        self,
        interaction: discord.Interaction,
        character: str,
        server: str,
        refresh: bool = False,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        settings = get_warcraftlogs_settings(guild.id)
        if not settings.is_configured:
            await interaction.response.send_message(
                "⚠ Warcraft Logs is not configured for this server. "
                "An administrator can run `/logs setup`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            result = await self.character_service.get_character_performance(
                character,
                _normalize_realm_input(server),
                settings.region,
                force_refresh=refresh,
            )
        except WarcraftLogsConfigurationError:
            await interaction.followup.send(
                "⚠ Warcraft Logs API credentials are missing from the bot configuration.",
                ephemeral=True,
            )
            return
        except WarcraftLogsAuthenticationError:
            await interaction.followup.send(
                "⚠ Warcraft Logs authentication failed. Check the configured Client ID and Client Secret.",
                ephemeral=True,
            )
            return
        except (WarcraftLogsRequestError, ValueError) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not return that character card: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs character error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        view = WarcraftLogsCharacterView(result, owner_id=interaction.user.id)
        await interaction.followup.send(
            embed=build_character_card_embed(result, "heroic", "damage"),
            view=view,
            ephemeral=True,
        )

    async def debug_character(
        self,
        interaction: discord.Interaction,
        character: str,
        server: str,
    ) -> None:
        if not bool(config.DEV_MODE):
            await interaction.response.send_message(
                "⛔ Warcraft Logs debug exports are disabled outside DEV_MODE.",
                ephemeral=True,
            )
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return
        if not getattr(interaction.user.guild_permissions, "administrator", False):
            await interaction.response.send_message(
                "⛔ You must be a server administrator to export debug data.",
                ephemeral=True,
            )
            return

        settings = get_warcraftlogs_settings(guild.id)
        if not settings.is_configured:
            await interaction.response.send_message(
                "⚠ Warcraft Logs is not configured for this server.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            result = await self.character_service.get_character_performance(
                character,
                _normalize_realm_input(server),
                settings.region,
                force_refresh=True,
            )
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs character debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        debug_bytes = build_debug_json_bytes(
            operation="character_top_parses",
            request={
                "discord_guild_id": guild.id,
                "character": character,
                "server": server,
                "normalized_server": _normalize_realm_input(server),
                "region": settings.region,
                "raid_size": 10,
                "difficulties": [3, 4],
                "metrics": ["dps", "hps"],
            },
            response={
                "normal_damage": result.normal_damage,
                "heroic_damage": result.heroic_damage,
                "normal_healing": result.normal_healing,
                "heroic_healing": result.heroic_healing,
                "raw_character": result.raw_response,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-character-{result.character_name.casefold()}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE Warcraft Logs character export. Credential-like fields were redacted.",
            file=file,
            ephemeral=True,
        )


def _normalize_realm_input(value: str) -> str:
    # Warcraft Logs realm slugs remove apostrophes: Shek'zeer -> shekzeer.
    return str(value or "").strip().replace("'", "").replace("’", "")


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError(
            "The Warcraft Logs command group must be loaded before character performance."
        )

    cog = WarcraftLogsCharacterPerformanceCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.player_command)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_character_command)
