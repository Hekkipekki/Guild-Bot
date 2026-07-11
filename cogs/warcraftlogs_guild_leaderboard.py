from __future__ import annotations

import asyncio
import io
import time

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

LEADERBOARD_LOAD_TIMEOUT_SECONDS = 150
PROGRESS_EDIT_INTERVAL_SECONDS = 1.0
FINAL_SEND_TIMEOUT_SECONDS = 20


class _RaidTeamLeaderboardService:
    """Bind one Discord guild's registered raid-team characters to the service."""

    def __init__(
        self,
        service: WarcraftLogsGuildRecentLeaderboardService,
        allowed_character_names: set[str] | None,
    ) -> None:
        self.service = service
        self.allowed_character_names = allowed_character_names

    async def get_leaderboard(
        self,
        guild_id: int,
        *,
        difficulty: int = 4,
        force_refresh: bool = False,
        progress_callback=None,
    ):
        return await self.service.get_leaderboard(
            guild_id,
            difficulty=difficulty,
            allowed_character_names=self.allowed_character_names,
            force_refresh=force_refresh,
            progress_callback=progress_callback,
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
        filtered_service = _RaidTeamLeaderboardService(
            self.recent_service,
            raid_team_characters,
        )
        loading_embed = _build_loading_embed(
            "Starting",
            "Reading the configured raid team and Warcraft Logs settings…",
            refresh=refresh,
        )
        await interaction.response.send_message(embed=loading_embed, ephemeral=True)

        progress_lock = asyncio.Lock()
        last_edit = 0.0

        async def update_progress(stage: str, completed: int, total: int) -> None:
            nonlocal last_edit
            now = time.monotonic()
            finished = total > 0 and completed >= total
            if not finished and now - last_edit < PROGRESS_EDIT_INTERVAL_SECONDS:
                return
            async with progress_lock:
                now = time.monotonic()
                if not finished and now - last_edit < PROGRESS_EDIT_INTERVAL_SECONDS:
                    return
                last_edit = now
                title, detail = _progress_text(stage, completed, total)
                await interaction.edit_original_response(
                    embed=_build_loading_embed(title, detail, refresh=refresh),
                    view=None,
                )

        try:
            leaderboard_result = await asyncio.wait_for(
                filtered_service.get_leaderboard(
                    settings.guild_id,
                    difficulty=4,
                    force_refresh=refresh,
                    progress_callback=update_progress,
                ),
                timeout=LEADERBOARD_LOAD_TIMEOUT_SECONDS,
            )
            if not leaderboard_result.latest_report_code:
                raise WarcraftLogsRequestError(
                    "No Heroic 10-player kill reports were found in the latest three-week window."
                )
            await update_progress("latest", 0, 1)
            latest_report = await asyncio.wait_for(
                self.performance_service.get_report_player_performance(
                    leaderboard_result.latest_report_code,
                    force_refresh=refresh,
                ),
                timeout=45,
            )
            await update_progress("latest", 1, 1)
        except asyncio.TimeoutError:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Warcraft Logs timed out",
                    description=(
                        "The current Warcraft Logs request did not finish in time. The progress "
                        "step above identifies which phase stalled. Try again without "
                        "`refresh:true`; cached report data is much faster."
                    ),
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return
        except (
            WarcraftLogsConfigurationError,
            WarcraftLogsAuthenticationError,
            WarcraftLogsRequestError,
            ValueError,
        ) as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Could not build leaderboard",
                    description=f"`{exc}`",
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return
        except Exception as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Unexpected leaderboard error",
                    description=f"`{type(exc).__name__}: {exc}`",
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return

        await interaction.edit_original_response(
            embed=_build_loading_embed(
                "Finalizing interface",
                "Building the player dropdown and interactive controls…",
                refresh=refresh,
            ),
            view=None,
        )

        try:
            final_embed = build_guild_recent_embed(leaderboard_result)
            view = WarcraftLogsGuildLeaderboardView(
                owner_id=interaction.user.id,
                guild_id=settings.guild_id,
                region=settings.region,
                latest_report=latest_report,
                leaderboard_result=leaderboard_result,
                recent_service=filtered_service,
                performance_service=self.performance_service,
                character_service=self.character_service,
                dtps_service=self.dtps_service,
                guild_emojis=tuple(guild.emojis),
                allowed_character_names=raid_team_characters,
            )
        except Exception as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Could not build leaderboard controls",
                    description=f"`{type(exc).__name__}: {exc}`",
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return

        try:
            await asyncio.wait_for(
                interaction.followup.send(
                    embed=final_embed,
                    view=view,
                    ephemeral=True,
                    wait=True,
                ),
                timeout=FINAL_SEND_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Discord timed out while sending the leaderboard",
                    description=(
                        "Warcraft Logs data finished successfully, but Discord did not accept the "
                        "interactive response within 20 seconds. Run `/logs leaderboard` again; "
                        "the calculated data is now cached."
                    ),
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return
        except Exception as exc:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Could not send leaderboard interface",
                    description=f"`{type(exc).__name__}: {exc}`",
                    color=discord.Color.red(),
                ),
                view=None,
            )
            return

        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="Leaderboard ready",
                    description="The interactive leaderboard was posted below.",
                    color=discord.Color.green(),
                ),
                view=None,
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


def _build_loading_embed(title: str, detail: str, *, refresh: bool) -> discord.Embed:
    embed = discord.Embed(
        title=f"Building leaderboard — {title}",
        description=detail,
        color=discord.Color.orange(),
    )
    embed.set_footer(
        text="Forced refresh: all report caches are bypassed." if refresh else "Cached data is used when available."
    )
    return embed


def _progress_text(stage: str, completed: int, total: int) -> tuple[str, str]:
    if stage == "cache":
        return "Cache hit", "Using the completed three-week leaderboard from cache."
    if stage == "reports":
        return "Recent reports", "Loading the guild's recent report list…" if not completed else "Recent report list loaded."
    if stage == "summaries":
        return (
            "Checking raid reports",
            f"Checked **{completed}/{total}** report summaries for matching Heroic kills.",
        )
    if stage == "rankings":
        return (
            "Loading player rankings",
            f"Loaded rankings from **{completed}/{total}** matching reports.",
        )
    if stage == "latest":
        return (
            "Preparing latest raid",
            "Loading the latest matching report for player-card navigation…" if not completed else "Latest raid loaded.",
        )
    if stage == "done":
        return "Finalizing", "Sorting raid-team players and calculating their best-boss averages…"
    return "Working", "Processing Warcraft Logs data…"


def _registered_raid_team_characters(discord_guild_id: int) -> set[str] | None:
    """Return character names owned by configured raid-team Discord users."""

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
