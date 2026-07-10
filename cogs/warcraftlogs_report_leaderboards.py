from __future__ import annotations

import io
from datetime import datetime, timezone

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
from services.warcraftlogs.report_leaderboard_service import (
    ReportLeaderboardResult,
    WarcraftLogsReportLeaderboardService,
)
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings


LEADERBOARD_METRICS = [
    app_commands.Choice(name="DPS", value="dps"),
    app_commands.Choice(name="Avoidable DTPS", value="dtps"),
]


class WarcraftLogsReportLeaderboardCommands(commands.Cog):
    """Report-level DPS and avoidable-DTPS leaderboards."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.leaderboard_service = WarcraftLogsReportLeaderboardService(self.client)
        self.leaderboard_command = app_commands.Command(
            name="leaderboard",
            description="Show report DPS or avoidable damage-taken rankings.",
            callback=self.leaderboard,
        )
        self.debug_leaderboard_command = app_commands.Command(
            name="debug-leaderboard",
            description="DEV only: export report leaderboard event data.",
            callback=self.debug_leaderboard,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("leaderboard")
            logs_group.remove_command("debug-leaderboard")
        await self.client.close()

    @app_commands.describe(
        metric="DPS is higher-is-better; avoidable DTPS is lower-is-better.",
        code="Optional Warcraft Logs report code; defaults to the latest guild report.",
        refresh="Bypass report and leaderboard caches.",
    )
    @app_commands.choices(metric=LEADERBOARD_METRICS)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        metric: app_commands.Choice[str],
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
            result = await self.leaderboard_service.get_leaderboard(
                selected_code,
                metric.value,
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
                "⚠ Warcraft Logs authentication failed. Check the Client ID and Secret.",
                ephemeral=True,
            )
            return
        except (WarcraftLogsRequestError, ValueError) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not build that leaderboard: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected leaderboard error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=build_report_leaderboard_embed(result))

    @app_commands.describe(
        code="Optional Warcraft Logs report code; defaults to the latest guild report.",
    )
    async def debug_leaderboard(
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
            result = await self.leaderboard_service.get_leaderboard(
                selected_code,
                "dtps",
                force_refresh=True,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Leaderboard debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        debug_bytes = build_debug_json_bytes(
            operation="report_avoidable_dtps",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "report_code": selected_code,
            },
            response={
                "covered_bosses": result.covered_bosses,
                "excluded_bosses": result.excluded_bosses,
                "covered_duration_ms": result.covered_duration_ms,
                "dtps_entries": result.dtps_entries,
                "unmatched_abilities": result.unmatched_abilities,
                "raw_event_pages": result.raw_event_pages,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-dtps-{selected_code}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE avoidable-DTPS export. Credential-like fields were redacted.",
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


def build_report_leaderboard_embed(result: ReportLeaderboardResult) -> discord.Embed:
    if result.metric == "dps":
        title = f"{result.report_title} — DPS Leaderboard"
        description = f"[Open report]({result.url})\nHigher is better."
    else:
        title = f"{result.report_title} — Avoidable DTPS"
        description = (
            f"[Open report]({result.url})\n"
            "Only explicitly configured avoidable mechanics count. Lower is better."
        )

    embed = discord.Embed(
        title=title[:256],
        description=description,
        color=discord.Color.orange(),
    )

    if result.metric == "dps":
        lines = []
        for position, entry in enumerate(result.dps_entries[:20], start=1):
            spec = f" ({entry.spec_name})" if entry.spec_name else ""
            lines.append(
                f"**{position}. {entry.name}**{spec} — "
                f"{entry.dps:,.0f} DPS • {entry.ranked_fights} ranked fights"
            )
        embed.add_field(
            name="Damage Dealers",
            value="\n".join(lines)[:1024] if lines else "No DPS rows were available.",
            inline=False,
        )
    else:
        lines = []
        for position, entry in enumerate(result.dtps_entries[:20], start=1):
            lines.append(
                f"**{position}. {entry.name}** — {entry.dtps:,.1f} DTPS • "
                f"{entry.total_avoidable_damage:,.0f} damage • {entry.hit_count} hits"
            )
        embed.add_field(
            name="Avoidable damage ranking",
            value="\n".join(lines)[:1024] if lines else "No configured avoidable damage was found.",
            inline=False,
        )
        included = ", ".join(result.covered_bosses) or "None"
        embed.add_field(name="Included bosses", value=included[:1024], inline=False)
        if result.excluded_bosses:
            embed.add_field(
                name="Not yet covered",
                value=", ".join(result.excluded_bosses)[:1024],
                inline=False,
            )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=f"Report {result.report_code} • Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return embed


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError("The Warcraft Logs command group must load before leaderboards.")

    cog = WarcraftLogsReportLeaderboardCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.leaderboard_command)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_leaderboard_command)
