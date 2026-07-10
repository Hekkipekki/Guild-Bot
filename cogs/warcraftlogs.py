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
from services.warcraftlogs.ranking_parser import parse_guild_ranking_categories
from services.warcraftlogs.rankings_service import (
    GuildRankingEntry,
    GuildRankingsResult,
    WarcraftLogsRankingsService,
)
from services.warcraftlogs.reports_service import (
    WarcraftLogsReport,
    WarcraftLogsReportsResult,
    WarcraftLogsReportsService,
)
from services.warcraftlogs.settings_service import (
    get_warcraftlogs_settings,
    set_warcraftlogs_settings,
)


REGION_CHOICES = [
    app_commands.Choice(name="Europe", value="eu"),
    app_commands.Choice(name="United States", value="us"),
    app_commands.Choice(name="Korea", value="kr"),
    app_commands.Choice(name="Taiwan", value="tw"),
    app_commands.Choice(name="China", value="cn"),
]

RAID_SIZE_CHOICES = [
    app_commands.Choice(name="10 player", value=10),
    app_commands.Choice(name="25 player", value=25),
]

REPORT_LIMIT_CHOICES = [
    app_commands.Choice(name="5 reports", value=5),
    app_commands.Choice(name="10 reports", value=10),
    app_commands.Choice(name="20 reports", value=20),
]


class WarcraftLogsCommands(commands.Cog):
    logs = app_commands.Group(
        name="logs",
        description="Warcraft Logs guild tools.",
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        client_id, client_secret = get_warcraftlogs_credentials()
        self.client = WarcraftLogsClient(client_id, client_secret)
        self.rankings_service = WarcraftLogsRankingsService(self.client)
        self.reports_service = WarcraftLogsReportsService(self.client)

    async def cog_unload(self) -> None:
        await self.client.close()

    @logs.command(name="setup", description="Configure Warcraft Logs for this Discord server.")
    @app_commands.describe(
        guild_id="Numeric Warcraft Logs guild ID from the guild rankings URL.",
        region="Warcraft Logs region.",
        raid_size="Default raid size for rankings.",
    )
    @app_commands.choices(region=REGION_CHOICES, raid_size=RAID_SIZE_CHOICES)
    async def setup_logs(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        region: app_commands.Choice[str],
        raid_size: app_commands.Choice[int],
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if not getattr(member.guild_permissions, "administrator", False):
            await interaction.response.send_message(
                "⛔ You must be a server administrator to configure Warcraft Logs.",
                ephemeral=True,
            )
            return

        try:
            settings = set_warcraftlogs_settings(
                guild.id,
                logs_guild_id=guild_id,
                region=region.value,
                raid_size=raid_size.value,
            )
        except (TypeError, ValueError) as exc:
            await interaction.response.send_message(f"⚠ {exc}", ephemeral=True)
            return

        await interaction.response.send_message(
            "✅ Warcraft Logs configured.\n"
            f"Guild ID: `{settings.guild_id}`\n"
            f"Region: `{settings.region.upper()}`\n"
            f"Default raid size: `{settings.raid_size}`",
            ephemeral=True,
        )

    @logs.command(name="rankings", description="Show the latest configured guild rankings.")
    @app_commands.describe(
        raid_size="Override the configured raid size for this request.",
        boss_id="Optional boss ID from the Warcraft Logs rankings URL.",
        recent="Only include recent raiders when supported by Warcraft Logs.",
        refresh="Bypass the ten-minute rankings cache.",
    )
    @app_commands.choices(raid_size=RAID_SIZE_CHOICES)
    async def rankings(
        self,
        interaction: discord.Interaction,
        raid_size: app_commands.Choice[int] | None = None,
        boss_id: int | None = None,
        recent: bool = False,
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

        selected_size = raid_size.value if raid_size is not None else settings.raid_size
        await interaction.response.defer(thinking=True)

        try:
            result = await self.rankings_service.get_guild_rankings(
                settings.guild_id,
                raid_size=selected_size,
                boss_id=boss_id,
                recent=recent,
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
        except WarcraftLogsRequestError as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs could not return guild rankings: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=_build_rankings_embed(result, settings.region))

    @logs.command(name="reports", description="Show recent Warcraft Logs reports for this guild.")
    @app_commands.describe(
        limit="Number of recent reports to show.",
        refresh="Bypass the five-minute reports cache.",
    )
    @app_commands.choices(limit=REPORT_LIMIT_CHOICES)
    async def reports(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Choice[int] | None = None,
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

        selected_limit = limit.value if limit is not None else 5
        await interaction.response.defer(thinking=True)

        try:
            result = await self.reports_service.get_recent_reports(
                settings.guild_id,
                limit=selected_limit,
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
                f"⚠ Warcraft Logs could not return recent reports: `{exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs reports error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(embed=_build_reports_embed(result))

    @logs.command(
        name="debug",
        description="DEV only: export the raw Warcraft Logs rankings response.",
    )
    @app_commands.describe(
        raid_size="Override the configured raid size for this request.",
        boss_id="Optional boss ID from the Warcraft Logs rankings URL.",
        recent="Only include recent raiders when supported by Warcraft Logs.",
    )
    @app_commands.choices(raid_size=RAID_SIZE_CHOICES)
    async def debug_rankings(
        self,
        interaction: discord.Interaction,
        raid_size: app_commands.Choice[int] | None = None,
        boss_id: int | None = None,
        recent: bool = False,
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

        member = interaction.user
        if not getattr(member.guild_permissions, "administrator", False):
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

        selected_size = raid_size.value if raid_size is not None else settings.raid_size
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            result = await self.rankings_service.get_guild_rankings(
                settings.guild_id,
                raid_size=selected_size,
                boss_id=boss_id,
                recent=recent,
                force_refresh=True,
            )
        except (WarcraftLogsConfigurationError, WarcraftLogsAuthenticationError, WarcraftLogsRequestError) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs debug error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        parsed_entries = _get_display_entries(result)
        debug_bytes = build_debug_json_bytes(
            operation="guild_rankings",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "region": settings.region,
                "raid_size": selected_size,
                "boss_id": boss_id,
                "recent": recent,
            },
            response={
                "guild_name": result.guild_name,
                "zone_name": result.zone_name,
                "fetched_at": result.fetched_at,
                "normalized_entries": parsed_entries,
                "raw_rankings": result.raw_rankings,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-rankings-{settings.guild_id}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE Warcraft Logs response export. Credential-like fields were redacted.",
            file=file,
            ephemeral=True,
        )

    @logs.command(
        name="debug-reports",
        description="DEV only: export the raw Warcraft Logs reports response.",
    )
    @app_commands.describe(limit="Number of recent reports to request.")
    @app_commands.choices(limit=REPORT_LIMIT_CHOICES)
    async def debug_reports(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Choice[int] | None = None,
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

        member = interaction.user
        if not getattr(member.guild_permissions, "administrator", False):
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

        selected_limit = limit.value if limit is not None else 5
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            result = await self.reports_service.get_recent_reports(
                settings.guild_id,
                limit=selected_limit,
                force_refresh=True,
            )
        except (WarcraftLogsConfigurationError, WarcraftLogsAuthenticationError, WarcraftLogsRequestError, ValueError) as exc:
            await interaction.followup.send(
                f"⚠ Warcraft Logs reports debug request failed: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Unexpected Warcraft Logs reports debug error: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        debug_bytes = build_debug_json_bytes(
            operation="guild_reports",
            request={
                "discord_guild_id": guild.id,
                "warcraftlogs_guild_id": settings.guild_id,
                "region": settings.region,
                "limit": selected_limit,
            },
            response={
                "fetched_at": result.fetched_at,
                "normalized_reports": result.reports,
                "raw_reports": result.raw_response,
            },
        )
        file = discord.File(
            io.BytesIO(debug_bytes),
            filename=f"warcraftlogs-reports-{settings.guild_id}.json",
        )
        await interaction.followup.send(
            "🧪 DEV_MODE Warcraft Logs reports export. Credential-like fields were redacted.",
            file=file,
            ephemeral=True,
        )


def _get_display_entries(result: GuildRankingsResult) -> tuple[GuildRankingEntry, ...]:
    category_entries = parse_guild_ranking_categories(result.raw_rankings)
    return category_entries or result.entries


def _build_rankings_embed(
    result: GuildRankingsResult,
    region: str,
) -> discord.Embed:
    zone_label = result.zone_name or "Latest raid zone"
    filters = [f"{result.raid_size}-player", region.upper()]
    if result.boss_id is not None:
        filters.append(f"Boss {result.boss_id}")
    if result.recent:
        filters.append("Recent raiders")

    embed = discord.Embed(
        title=f"{result.guild_name} — Guild Rankings",
        description=f"{zone_label} • {' • '.join(filters)}",
        color=discord.Color.orange(),
    )

    entries = _get_display_entries(result)
    if entries:
        lines = [_format_ranking_entry(entry) for entry in entries[:20]]
        embed.add_field(
            name="Guild rankings",
            value="\n".join(lines)[:1024],
            inline=False,
        )
        if len(entries) > 20:
            embed.add_field(
                name="More",
                value=f"{len(entries) - 20} additional ranking entries were omitted.",
                inline=False,
            )
    else:
        embed.add_field(
            name="Ranking data",
            value="Warcraft Logs returned no usable ranking values for these filters.",
            inline=False,
        )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=(
            f"Warcraft Logs guild {result.guild_id} • "
            f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    )
    return embed


def _build_reports_embed(result: WarcraftLogsReportsResult) -> discord.Embed:
    embed = discord.Embed(
        title="Recent Warcraft Logs Reports",
        description=f"Guild {result.guild_id}",
        color=discord.Color.orange(),
    )

    if not result.reports:
        embed.description = (
            f"Guild {result.guild_id}\nNo recent reports were returned by Warcraft Logs."
        )
    else:
        for report in result.reports[:10]:
            embed.add_field(
                name=report.title[:256],
                value=_format_report(report),
                inline=False,
            )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(text=f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}")
    return embed


def _format_report(report: WarcraftLogsReport) -> str:
    started = datetime.fromtimestamp(report.start_time / 1000, tz=timezone.utc)
    details = [f"<t:{int(started.timestamp())}:f>"]
    if report.zone_name:
        details.append(report.zone_name)
    if report.duration_ms is not None:
        details.append(_format_duration(report.duration_ms))
    if report.owner_name:
        details.append(f"Uploaded by {report.owner_name}")
    details.append(f"[Open report]({report.url})")
    return "\n".join(details)


def _format_duration(duration_ms: float) -> str:
    total_seconds = max(int(duration_ms // 1000), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"Duration: {hours}h {minutes}m"
    return f"Duration: {minutes}m {seconds}s"


def _format_ranking_entry(entry: GuildRankingEntry) -> str:
    ranks: list[str] = []
    if entry.world_rank is not None:
        ranks.append(f"World #{entry.world_rank:,}")
    if entry.region_rank is not None:
        ranks.append(f"Region #{entry.region_rank:,}")
    if entry.server_rank is not None:
        ranks.append(f"Realm #{entry.server_rank:,}")
    if entry.rank_percent is not None:
        ranks.append(f"{entry.rank_percent:.1f}%")
    detail = " • ".join(ranks) if ranks else "Unranked"
    return f"**{entry.encounter_name}** — {detail}"


async def setup(bot: commands.Bot) -> None:
    cog = WarcraftLogsCommands(bot)
    if not bool(config.DEV_MODE):
        cog.logs.remove_command("debug")
        cog.logs.remove_command("debug-reports")
    await bot.add_cog(cog)
