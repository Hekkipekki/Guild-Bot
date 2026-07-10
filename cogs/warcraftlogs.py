from __future__ import annotations

from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from services.warcraftlogs.api_client import (
    WarcraftLogsAuthenticationError,
    WarcraftLogsClient,
    WarcraftLogsConfigurationError,
    WarcraftLogsRequestError,
)
from services.warcraftlogs.credentials import get_warcraftlogs_credentials
from services.warcraftlogs.rankings_service import (
    GuildRankingEntry,
    GuildRankingsResult,
    WarcraftLogsRankingsService,
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

    if result.entries:
        lines = [_format_ranking_entry(entry) for entry in result.entries[:20]]
        embed.add_field(
            name="Boss rankings",
            value="\n".join(lines)[:1024],
            inline=False,
        )
        if len(result.entries) > 20:
            embed.add_field(
                name="More",
                value=f"{len(result.entries) - 20} additional ranking entries were omitted.",
                inline=False,
            )
    else:
        embed.add_field(
            name="Ranking data",
            value=(
                "Warcraft Logs returned ranking data, but no encounter rows could be "
                "normalized. This usually means the API response shape changed."
            ),
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
    detail = " • ".join(ranks) if ranks else "No rank available"
    return f"**{entry.encounter_name}** — {detail}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WarcraftLogsCommands(bot))
