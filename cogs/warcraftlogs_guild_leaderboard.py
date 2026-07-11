from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

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
from services.warcraftlogs.guild_recent_leaderboard_service import (
    WarcraftLogsGuildRecentLeaderboardService,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceService,
)
from services.warcraftlogs.report_leaderboard_service import (
    WarcraftLogsReportLeaderboardService,
)
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings
from views.warcraftlogs_guild_leaderboard_view import (
    WarcraftLogsGuildLeaderboardView,
    build_guild_recent_embed,
)


class WarcraftLogsGuildLeaderboardCommands(commands.Cog):
    """Interactive recent-raider leaderboard under the existing /logs group."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.performance_service = WarcraftLogsPlayerPerformanceService(self.client)
        self.recent_service = WarcraftLogsGuildRecentLeaderboardService(self.client)
        self.character_service = WarcraftLogsCharacterPerformanceService(self.client)
        self.dtps_service = WarcraftLogsReportLeaderboardService(self.client)
        self.command = app_commands.Command(
            name="leaderboard",
            description="Show recent-raider DPS/HPS rankings and avoidable DTPS.",
            callback=self.leaderboard,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("leaderboard")
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

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            leaderboard_result = await self.recent_service.get_leaderboard(
                settings.guild_id,
                difficulty=4,
                force_refresh=refresh,
            )
            reports = await self.reports_service.get_recent_reports(
                settings.guild_id,
                limit=1,
                force_refresh=refresh,
            )
            if not reports.reports:
                raise WarcraftLogsRequestError("Warcraft Logs returned no recent guild reports.")
            latest_report = await self.performance_service.get_report_player_performance(
                reports.reports[0].code,
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
            character_service=self.character_service,
            dtps_service=self.dtps_service,
            guild_emojis=tuple(guild.emojis),
        )
        await interaction.followup.send(
            embed=build_guild_recent_embed(leaderboard_result),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError("The Warcraft Logs command group must load before leaderboard.")
    cog = WarcraftLogsGuildLeaderboardCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.command)
