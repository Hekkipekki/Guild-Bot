from __future__ import annotations

import io
import re
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
from services.warcraftlogs.character_performance_service import (
    WarcraftLogsCharacterPerformanceService,
)
from services.warcraftlogs.credentials import get_warcraftlogs_credentials
from services.warcraftlogs.debug_service import build_debug_json_bytes
from services.warcraftlogs.player_performance_service import WarcraftLogsPlayerPerformanceService
from services.warcraftlogs.recent_guild_rankings_service import (
    RecentGuildRankingsResult,
    WarcraftLogsRecentGuildRankingsService,
)
from services.warcraftlogs.report_leaderboard_service import (
    ReportLeaderboardResult,
    WarcraftLogsReportLeaderboardService,
)
from services.warcraftlogs.reports_service import WarcraftLogsReportsService
from services.warcraftlogs.settings_service import get_warcraftlogs_settings
from views.warcraftlogs_player_view import WarcraftLogsPlayerView


class WarcraftLogsReportLeaderboardCommands(commands.Cog):
    """Recent guild rankings and avoidable-DTPS report analytics."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.reports_service = WarcraftLogsReportsService(self.client)
        self.performance_service = WarcraftLogsPlayerPerformanceService(self.client)
        self.character_service = WarcraftLogsCharacterPerformanceService(self.client)
        self.recent_rankings_service = WarcraftLogsRecentGuildRankingsService(
            self.reports_service,
            self.performance_service,
        )
        self.report_leaderboard_service = WarcraftLogsReportLeaderboardService(self.client)
        self.rankings_group: app_commands.Group | None = None
        self.debug_leaderboard_command = app_commands.Command(
            name="debug-leaderboard",
            description="DEV only: export avoidable-DTPS event data.",
            callback=self.debug_leaderboard,
        )

    async def cog_unload(self) -> None:
        logs_group = self.bot.tree.get_command("logs")
        if isinstance(logs_group, app_commands.Group):
            logs_group.remove_command("rankings")
            logs_group.remove_command("debug-leaderboard")
        await self.client.close()

    async def dps_rankings(
        self,
        interaction: discord.Interaction,
        reports: int = 10,
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
                "⚠ Warcraft Logs is not configured. An administrator can run `/logs setup`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            result = await self.recent_rankings_service.get_recent_rankings(
                settings.guild_id,
                report_limit=max(1, min(reports, 20)),
                force_refresh=refresh,
            )
            if not result.latest_report_code:
                await interaction.followup.send(
                    "⚠ Warcraft Logs returned no recent guild reports.", ephemeral=True
                )
                return
            latest = await self.performance_service.get_report_player_performance(
                result.latest_report_code,
                force_refresh=refresh,
            )
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not build recent rankings: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected rankings error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        emojis = tuple(guild.emojis)
        view = WarcraftLogsPlayerView(
            latest,
            owner_id=interaction.user.id,
            character_service=self.character_service,
            region=settings.region,
            guild_emojis=emojis,
        )
        await interaction.followup.send(
            embed=build_recent_rankings_embed(result, emojis),
            view=view,
        )

    async def dtps_rankings(
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
                "⚠ Warcraft Logs is not configured. An administrator can run `/logs setup`.",
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
                    "⚠ Warcraft Logs returned no recent guild reports.", ephemeral=True
                )
                return
            result = await self.report_leaderboard_service.get_leaderboard(
                selected_code,
                "dtps",
                force_refresh=refresh,
            )
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not build avoidable DTPS: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected DTPS error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=build_dtps_embed(result))

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
        if guild is None or not getattr(
            interaction.user.guild_permissions, "administrator", False
        ):
            await interaction.response.send_message(
                "⛔ This DEV export requires a server administrator.", ephemeral=True
            )
            return
        settings = get_warcraftlogs_settings(guild.id)
        if not settings.is_configured:
            await interaction.response.send_message(
                "⚠ Warcraft Logs is not configured.", ephemeral=True
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
                raise ValueError("No recent report was found.")
            result = await self.report_leaderboard_service.get_leaderboard(
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
        await interaction.followup.send(
            "🧪 DEV_MODE avoidable-DTPS export. Credential-like fields were redacted.",
            file=discord.File(
                io.BytesIO(debug_bytes),
                filename=f"warcraftlogs-dtps-{selected_code}.json",
            ),
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


def build_recent_rankings_embed(
    result: RecentGuildRankingsResult,
    guild_emojis: tuple[discord.Emoji, ...],
) -> discord.Embed:
    embed = discord.Embed(
        title="Recent Guild Rankings",
        description=(
            f"Best parse across the latest **{len(result.report_codes)}** guild reports.\n"
            "Tanks and DPS use damage parses; healers use healing parses."
        ),
        color=discord.Color.orange(),
    )
    for role, label in (
        ("Tank", "🛡 Tanks — DPS"),
        ("Healer", "💚 Healers — HPS"),
        ("DPS", "⚔ DPS — DPS"),
    ):
        role_entries = [entry for entry in result.entries if entry.role_category == role]
        lines: list[str] = []
        for position, entry in enumerate(role_entries[:20], start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"**{position}.**")
            emoji = _find_emoji(entry.spec_name, entry.class_name, guild_emojis)
            icon = f"{emoji} " if emoji else ""
            spec = f" ({entry.spec_name})" if entry.spec_name else ""
            parse = "—" if entry.best_parse is None else f"{entry.best_parse:.1f}"
            lines.append(
                f"{medal} {icon}**{entry.name}**{spec} — Best **{parse}**"
            )
        embed.add_field(
            name=label,
            value="\n".join(lines)[:1024] if lines else "No ranked players.",
            inline=False,
        )
    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=(
            f"Latest report: {result.latest_report_title or 'Unknown'} • "
            f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    )
    return embed


def build_dtps_embed(result: ReportLeaderboardResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.report_title} — Avoidable DTPS"[:256],
        description=(
            f"[Open report]({result.url})\n"
            "Only configured avoidable mechanics count. Lower is better."
        ),
        color=discord.Color.orange(),
    )
    lines = [
        f"**{position}. {entry.name}** — {entry.dtps:,.1f} DTPS • "
        f"{entry.total_avoidable_damage:,.0f} damage • {entry.hit_count} hits"
        for position, entry in enumerate(result.dtps_entries[:20], start=1)
    ]
    embed.add_field(
        name="Avoidable damage ranking",
        value="\n".join(lines)[:1024] if lines else "No configured avoidable damage was found.",
        inline=False,
    )
    embed.add_field(
        name="Included bosses",
        value=(", ".join(result.covered_bosses) or "None")[:1024],
        inline=False,
    )
    if result.excluded_bosses:
        embed.add_field(
            name="Not yet covered",
            value=", ".join(result.excluded_bosses)[:1024],
            inline=False,
        )
    return embed


def _find_emoji(
    spec_name: str | None,
    class_name: str | None,
    emojis: tuple[discord.Emoji, ...],
) -> discord.Emoji | None:
    wanted = {
        _normalize_name(value)
        for value in (spec_name, class_name)
        if value
    }
    for emoji in emojis:
        name = _normalize_name(emoji.name)
        if name in wanted or any(value and value in name for value in wanted):
            return emoji
    return None


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


async def setup(bot: commands.Bot) -> None:
    logs_group = bot.tree.get_command("logs")
    if not isinstance(logs_group, app_commands.Group):
        raise RuntimeError("The Warcraft Logs command group must load before rankings.")

    existing = logs_group.get_command("rankings")
    if existing is None:
        raise RuntimeError("The existing guild rankings command was not found.")
    guild_callback = existing.callback
    logs_group.remove_command("rankings")

    cog = WarcraftLogsReportLeaderboardCommands(bot)
    await bot.add_cog(cog)

    rankings_group = app_commands.Group(
        name="rankings",
        description="Guild, DPS/HPS, and avoidable-DTPS rankings.",
    )
    rankings_group.add_command(
        app_commands.Command(
            name="guild",
            description="Show guild world, region, and realm rankings.",
            callback=guild_callback,
        )
    )
    rankings_group.add_command(
        app_commands.Command(
            name="dps",
            description="Show recent role-based player rankings.",
            callback=cog.dps_rankings,
        )
    )
    rankings_group.add_command(
        app_commands.Command(
            name="dtps",
            description="Show avoidable damage taken per second for a report.",
            callback=cog.dtps_rankings,
        )
    )
    cog.rankings_group = rankings_group
    logs_group.add_command(rankings_group)
    if bool(config.DEV_MODE):
        logs_group.add_command(cog.debug_leaderboard_command)
