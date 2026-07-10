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
from services.warcraftlogs.report_summary_service import (
    WarcraftLogsEncounterSummary,
    WarcraftLogsReportSummary,
    WarcraftLogsReportSummaryService,
)
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings


class WarcraftLogsReportSummaryCommands(commands.Cog):
    """Report-level Warcraft Logs commands attached to the existing /logs group."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.summary_service = WarcraftLogsReportSummaryService(self.client)
        self.report_command = app_commands.Command(
            name="report",
            description="Show a summary for the latest or a selected Warcraft Logs report.",
            callback=self.report,
        )
        self.debug_report_command = app_commands.Command(
            name="debug-report",
            description="DEV only: export a raw Warcraft Logs report summary response.",
            callback=self.debug_report,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("report")
            logs_group.remove_command("debug-report")
        await self.client.close()

    async def report(
        self,
        interaction: discord.Interaction,
        code: str | None = None,
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
                "⚠ Warcraft Logs is not configured for this server. "
                "An administrator can run `/logs setup`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            selected_code = str(code or "").strip()
            if not selected_code:
                reports = await self.reports_service.get_recent_reports(
                    settings.guild_id,
                    limit=1,
                    force_refresh=refresh,
                )
                if not reports.reports:
                    await interaction.followup.send(
                        "⚠ Warcraft Logs returned no recent reports for this guild.",
                        ephemeral=True,
                    )
                    return
                selected_code = reports.reports[0].code

            result = await self.summary_service.get_report_summary(
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
                f"⚠ Warcraft Logs could not return the report summary: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs report error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=_build_report_summary_embed(result))

    async def debug_report(
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
                "⚠ This command can only be used in a server.",
                ephemeral=True,
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
                "⚠ Warcraft Logs is not configured for this server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            selected_code = str(code or "").strip()
            if not selected_code:
                reports = await self.reports_service.get_recent_reports(
                    settings.guild_id,
                    limit=1,
                    force_refresh=True,
                )
                if not reports.reports:
                    await interaction.followup.send(
                        "⚠ Warcraft Logs returned no recent reports for this guild.",
                        ephemeral=True,
                    )
                    return
                selected_code = reports.reports[0].code

            result = await self.summary_service.get_report_summary(
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
                f"⚠ Warcraft Logs report debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs report debug error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        debug_bytes = build_debug_json_bytes(
            operation="report_summary",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "report_code": selected_code,
            },
            response={
                "fetched_at": result.fetched_at,
                "normalized_fights": result.fights,
                "normalized_encounters": result.encounters,
                "raw_report": result.raw_response,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-report-{selected_code}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE Warcraft Logs report export. Credential-like fields were redacted.",
            file=file,
            ephemeral=True,
        )


def _build_report_summary_embed(result: WarcraftLogsReportSummary) -> discord.Embed:
    started = datetime.fromtimestamp(result.start_time / 1000, tz=timezone.utc)
    description = [f"<t:{int(started.timestamp())}:f>"]
    if result.zone_name:
        description.append(result.zone_name)
    description.append(f"[Open report]({result.url})")

    embed = discord.Embed(
        title=result.title[:256],
        description="\n".join(description),
        color=discord.Color.orange(),
    )

    overview = [
        f"**Boss pulls:** {len(result.boss_fights)}",
        f"**Kills:** {result.total_kills}",
        f"**Wipes:** {result.total_wipes}",
    ]
    if result.duration_ms is not None:
        overview.append(f"**Full report window:** {_format_duration(result.duration_ms)}")
    if result.owner_name:
        overview.append(f"**Uploaded by:** {result.owner_name}")
    embed.add_field(name="Overview", value="\n".join(overview), inline=False)

    if result.encounters:
        encounter_lines = [
            _format_encounter(encounter)
            for encounter in result.encounters[:15]
        ]
        embed.add_field(
            name="Bosses",
            value="\n".join(encounter_lines)[:1024],
            inline=False,
        )
        if len(result.encounters) > 15:
            embed.add_field(
                name="More",
                value=f"{len(result.encounters) - 15} additional encounters were omitted.",
                inline=False,
            )
    else:
        embed.add_field(
            name="Bosses",
            value="No boss fights were returned for this report.",
            inline=False,
        )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=f"Report {result.code} • Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return embed


def _format_encounter(encounter: WarcraftLogsEncounterSummary) -> str:
    details = [f"{encounter.kills} kill" + ("s" if encounter.kills != 1 else "")]
    details.append(f"{encounter.wipes} wipe" + ("s" if encounter.wipes != 1 else ""))
    if encounter.fastest_kill_ms is not None:
        details.append(f"best {_format_duration(encounter.fastest_kill_ms)}")
    if encounter.best_wipe_percentage is not None:
        details.append(f"best wipe {_format_boss_percentage(encounter.best_wipe_percentage)}")
    return f"**{encounter.label.display_label}** — {' • '.join(details)}"


def _format_duration(duration_ms: float) -> str:
    total_seconds = max(int(duration_ms // 1000), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _format_boss_percentage(value: float) -> str:
    # Warcraft Logs fight payloads commonly expose bossPercentage in hundredths.
    normalized = value / 100 if value > 100 else value
    return f"{normalized:.1f}%"


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError(
            "The Warcraft Logs command group must be loaded before report summaries."
        )

    cog = WarcraftLogsReportSummaryCommands(bot)
    await bot.add_cog(cog)
    logs_group.add_command(cog.report_command)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_report_command)
