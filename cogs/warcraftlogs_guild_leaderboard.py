from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

import config
from data.character_store import load_characters
from services.guild.guild_settings_service import get_expected_players
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
from services.warcraftlogs.guild_recent_leaderboard_service import (
    REPORT_WINDOW_DAYS,
    WarcraftLogsGuildRecentLeaderboardService,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceService,
)
from services.warcraftlogs.report_leaderboard_service import (
    WarcraftLogsReportLeaderboardService,
)
from services.warcraftlogs.report_summary_service import WarcraftLogsReportSummaryService
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings
from views.warcraftlogs_guild_leaderboard_view import (
    WarcraftLogsGuildLeaderboardView,
    build_guild_recent_embed,
)


class WarcraftLogsGuildLeaderboardCommands(commands.Cog):
    """Interactive recent-report leaderboard under the existing /logs group."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.summary_service = WarcraftLogsReportSummaryService(self.client)
        self.performance_service = WarcraftLogsPlayerPerformanceService(self.client)
        self.recent_service = WarcraftLogsGuildRecentLeaderboardService(
            self.reports_service,
            self.summary_service,
            self.performance_service,
        )
        self.character_service = WarcraftLogsCharacterPerformanceService(self.client)
        self.dtps_service = WarcraftLogsReportLeaderboardService(self.client)
        self.command = app_commands.Command(
            name="leaderboard",
            description="Show three-week performance, reports, top parses and avoidable DTPS.",
            callback=self.leaderboard,
        )
        self.debug_command = app_commands.Command(
            name="debug-guild-leaderboard",
            description="DEV only: export aggregated recent-report rankings.",
            callback=self.debug_guild_leaderboard,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("leaderboard")
            logs_group.remove_command("debug-guild-leaderboard")
        await self.client.close()

    async def leaderboard(
        self,
        interaction: discord.Interaction,
        refresh: bool = False,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return
        settings = get_warcraftlogs_settings(guild.id)
        if not settings.is_configured:
            await interaction.response.send_message(
                "⚠ Warcraft Logs is not configured. An administrator can run `/logs setup`.",
                ephemeral=True,
            )
            return

        raid_team_characters = _registered_raid_team_characters(guild.id)
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            leaderboard_result = await self.recent_service.get_leaderboard(
                settings.guild_id,
                difficulty=4,
                allowed_character_names=raid_team_characters,
                force_refresh=refresh,
            )
            if not leaderboard_result.latest_report_code:
                raise WarcraftLogsRequestError(
                    "No Heroic 10-player kill reports were found in the latest three-week window."
                )
            latest_report = await self.performance_service.get_report_player_performance(
                leaderboard_result.latest_report_code,
                force_refresh=refresh,
            )
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not build the leaderboard: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected leaderboard error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        view = WarcraftLogsGuildLeaderboardView(
            owner_id=interaction.user.id,
            guild_id=settings.guild_id,
            region=settings.region,
            latest_report=latest_report,
            leaderboard_result=leaderboard_result,
            recent_service=self.recent_service,
            performance_service=self.performance_service,
            character_service=self.character_service,
            dtps_service=self.dtps_service,
            guild_emojis=tuple(guild.emojis),
            allowed_character_names=raid_team_characters,
        )
        await interaction.followup.send(
            embed=build_guild_recent_embed(leaderboard_result),
            view=view,
            ephemeral=True,
        )

    async def debug_guild_leaderboard(
        self,
        interaction: discord.Interaction,
        difficulty: int = 4,
    ) -> None:
        if not bool(config.DEV_MODE):
            await interaction.response.send_message(
                "⛔ Guild leaderboard debug is disabled outside DEV_MODE.",
                ephemeral=True,
            )
            return
        guild = interaction.guild
        if guild is None or not getattr(
            interaction.user.guild_permissions,
            "administrator",
            False,
        ):
            await interaction.response.send_message(
                "⛔ This DEV export requires a server administrator.",
                ephemeral=True,
            )
            return
        settings = get_warcraftlogs_settings(guild.id)
        if not settings.is_configured:
            await interaction.response.send_message(
                "⚠ Warcraft Logs is not configured.",
                ephemeral=True,
            )
            return

        raid_team_characters = _registered_raid_team_characters(guild.id)
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            result = await self.recent_service.get_leaderboard(
                settings.guild_id,
                difficulty=difficulty,
                allowed_character_names=raid_team_characters,
                force_refresh=True,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Guild leaderboard debug failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        payload = build_debug_json_bytes(
            operation="guild_recent_report_rankings",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "difficulty": difficulty,
                "window_days": REPORT_WINDOW_DAYS,
                "raid_team_filter_enabled": raid_team_characters is not None,
                "registered_character_names": sorted(raid_team_characters or ()),
            },
            response={
                "damage_players": result.damage_players,
                "healing_players": result.healing_players,
                "reports": result.reports,
                "latest_report_code": result.latest_report_code,
            },
        )
        await interaction.followup.send(
            "🧪 DEV_MODE recent-report leaderboard export.",
            file=discord.File(
                io.BytesIO(payload),
                filename=f"warcraftlogs-guild-leaderboard-{settings.guild_id}-{difficulty}.json",
            ),
            ephemeral=True,
        )


def _registered_raid_team_characters(discord_guild_id: int) -> set[str] | None:
    """Return character names owned by configured raid-team Discord users.

    `None` means no raid team has been configured, so the leaderboard remains
    backwards-compatible and includes every logged player. An empty set means a
    raid team exists but none of its members has registered a character yet.
    """

    raid_team_user_ids = get_expected_players(discord_guild_id)
    if not raid_team_user_ids:
        return None

    characters_by_user = load_characters(discord_guild_id)
    names: set[str] = set()
    for user_id in raid_team_user_ids:
        for character in characters_by_user.get(str(user_id), []):
            name = str(character.get("name") or "").strip()
            if name:
                names.add(name)
    return names


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError("The Warcraft Logs command group must load before leaderboard.")
    cog = WarcraftLogsGuildLeaderboardCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.command)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_command)
