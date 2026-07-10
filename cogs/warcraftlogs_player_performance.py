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
from services.warcraftlogs.credentials import get_warcraftlogs_credentials
from services.warcraftlogs.debug_service import build_debug_json_bytes
from services.warcraftlogs.player_performance_service import WarcraftLogsPlayerPerformanceService
from services.warcraftlogs.player_ranking_graphic import render_player_ranking_graphic
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings
from views.warcraftlogs_player_view import (
    WarcraftLogsPlayerView,
    build_player_leaderboard_embed,
)


class WarcraftLogsPlayerPerformanceCommands(commands.Cog):
    """Player-performance commands attached to the existing /logs group."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.performance_service = WarcraftLogsPlayerPerformanceService(self.client)
        self.players_command = app_commands.Command(
            name="players",
            description="Browse player performance from the latest or a selected report.",
            callback=self.players,
        )
        self.debug_performance_command = app_commands.Command(
            name="debug-performance",
            description="DEV only: export raw report player rankings.",
            callback=self.debug_performance,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("players")
            logs_group.remove_command("debug-performance")
        await self.client.close()

    async def players(
        self,
        interaction: discord.Interaction,
        code: str | None = None,
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

        await interaction.response.defer(thinking=True)
        try:
            selected_code = await self._resolve_report_code(
                settings.guild_id,
                code,
                refresh=refresh,
            )
            if selected_code is None:
                await interaction.followup.send(
                    "⚠ Warcraft Logs returned no recent reports for this guild.",
                    ephemeral=True,
                )
                return
            result = await self.performance_service.get_report_player_performance(
                selected_code,
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
                f"⚠ Warcraft Logs could not return player performance: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs performance error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        graphic_filename = f"warcraftlogs-rankings-{result.report_code}.png"
        try:
            graphic_bytes = render_player_ranking_graphic(result)
            file = discord.File(io.BytesIO(graphic_bytes), filename=graphic_filename)
        except Exception as exc:
            print(f"[WarcraftLogs] Failed to render ranking graphic: {type(exc).__name__}: {exc}")
            graphic_filename = None
            file = None

        view = WarcraftLogsPlayerView(
            result,
            owner_id=interaction.user.id,
            graphic_filename=graphic_filename,
        )
        await interaction.followup.send(
            embed=build_player_leaderboard_embed(
                result,
                graphic_filename=graphic_filename,
            ),
            file=file,
            view=view,
        )

    async def debug_performance(
        self,
        interaction: discord.Interaction,
        code: str | None = None,
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
            selected_code = await self._resolve_report_code(
                settings.guild_id,
                code,
                refresh=True,
            )
            if selected_code is None:
                await interaction.followup.send(
                    "⚠ Warcraft Logs returned no recent reports for this guild.",
                    ephemeral=True,
                )
                return
            result = await self.performance_service.get_report_player_performance(
                selected_code,
                force_refresh=True,
            )
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs performance debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs performance debug error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        debug_bytes = build_debug_json_bytes(
            operation="report_player_performance",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "report_code": selected_code,
            },
            response={
                "fetched_at": result.fetched_at,
                "normalized_rows": result.players,
                "player_summaries": result.player_summaries,
                "raw_rankings": result.raw_rankings,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-performance-{selected_code}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE Warcraft Logs performance export. Credential-like fields were redacted.",
            file=file,
            ephemeral=True,
        )

    async def _resolve_report_code(
        self,
        guild_id: int,
        code: str | None,
        *,
        refresh: bool,
    ) -> str | None:
        selected_code = str(code or "").strip()
        if selected_code:
            return selected_code
        reports = await self.reports_service.get_recent_reports(
            guild_id,
            limit=1,
            force_refresh=refresh,
        )
        return reports.reports[0].code if reports.reports else None


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError(
            "The Warcraft Logs command group must be loaded before player performance."
        )

    cog = WarcraftLogsPlayerPerformanceCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.players_command)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_performance_command)
