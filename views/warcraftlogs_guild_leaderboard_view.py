from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

import config
from services.warcraftlogs.boss_emoji_config import BOSS_EMOJIS
from services.warcraftlogs.character_performance_service import (
    CharacterPerformanceResult,
    WarcraftLogsCharacterPerformanceService,
)
from services.warcraftlogs.guild_recent_leaderboard_service import (
    GuildRecentLeaderboardResult,
    WarcraftLogsGuildRecentLeaderboardService,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceResult,
    WarcraftLogsPlayerSummary,
)
from services.warcraftlogs.report_leaderboard_service import (
    ReportLeaderboardResult,
    WarcraftLogsReportLeaderboardService,
)
from views.warcraftlogs_character_view import build_character_card_embed
from views.warcraftlogs_player_view import build_player_detail_embed


class GuildLeaderboardPlayerSelect(discord.ui.Select):
    def __init__(self, view: "WarcraftLogsGuildLeaderboardView") -> None:
        players = view.selectable_players()
        options: list[discord.SelectOption] = []
        for index, player in enumerate(players[:25]):
            spec = player.primary_spec or player.class_name or "Unknown spec"
            average = "—" if player.average_parse is None else f"{player.average_parse:.1f}"
            options.append(
                discord.SelectOption(
                    label=player.name[:100],
                    value=str(index),
                    description=f"{spec} • Avg {average}"[:100],
                    emoji=_select_emoji(player),
                )
            )
        super().__init__(
            placeholder="Select a player",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not options,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, WarcraftLogsGuildLeaderboardView):
            return
        players = view.selectable_players()
        selected = players[int(self.values[0])]
        view.selected_identity = (
            selected.name.casefold(),
            (selected.server or "").casefold(),
        )
        view.character_result = None
        view.mode = "latest"
        view._sync_controls()
        latest = view.latest_player()
        if latest is None:
            embed = discord.Embed(
                title=f"{selected.name} — Latest Raid",
                description=(
                    "This player appears in the recent guild rankings but has no ranked rows "
                    "in the latest report. Use **Top Parses** for historical results."
                ),
                color=discord.Color.orange(),
            )
        else:
            embed = build_player_detail_embed(
                view.latest_report,
                latest,
                guild_emojis=view.guild_emojis,
            )
        await interaction.response.edit_message(embed=embed, view=view)


class WarcraftLogsGuildLeaderboardView(discord.ui.View):
    def __init__(
        self,
        *,
        owner_id: int,
        guild_id: int,
        region: str,
        latest_report: WarcraftLogsPlayerPerformanceResult,
        leaderboard_result: GuildRecentLeaderboardResult,
        recent_service: WarcraftLogsGuildRecentLeaderboardService,
        character_service: WarcraftLogsCharacterPerformanceService,
        dtps_service: WarcraftLogsReportLeaderboardService,
        guild_emojis: tuple[discord.Emoji, ...] = (),
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = int(owner_id)
        self.guild_id = int(guild_id)
        self.region = region
        self.latest_report = latest_report
        self.leaderboard_result = leaderboard_result
        self.recent_service = recent_service
        self.character_service = character_service
        self.dtps_service = dtps_service
        self.guild_emojis = guild_emojis
        self.difficulty = leaderboard_result.difficulty
        self.metric = "damage"
        self.mode = "leaderboard"
        self.selected_identity: tuple[str, str] | None = None
        self.character_result: CharacterPerformanceResult | None = None
        self.add_item(GuildLeaderboardPlayerSelect(self))
        self._sync_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this leaderboard can use its controls.",
            ephemeral=True,
        )
        return False

    def selectable_players(self) -> tuple[WarcraftLogsPlayerSummary, ...]:
        combined: dict[tuple[str, str], WarcraftLogsPlayerSummary] = {}
        for player in (
            *self.leaderboard_result.damage_players,
            *self.leaderboard_result.healing_players,
        ):
            key = (player.name.casefold(), (player.server or "").casefold())
            combined.setdefault(key, player)
        return tuple(sorted(combined.values(), key=lambda p: p.name.casefold()))

    def selected_player(self) -> WarcraftLogsPlayerSummary | None:
        if self.selected_identity is None:
            return None
        for player in self.selectable_players():
            key = (player.name.casefold(), (player.server or "").casefold())
            if key == self.selected_identity:
                return player
        return None

    def latest_player(self) -> WarcraftLogsPlayerSummary | None:
        selected = self.selected_player()
        if selected is None:
            return None
        exact = [
            player
            for player in self.latest_report.player_summaries
            if player.name.casefold() == selected.name.casefold()
            and (player.server or "").casefold() == (selected.server or "").casefold()
        ]
        if exact:
            return exact[0]
        return next(
            (
                player
                for player in self.latest_report.player_summaries
                if player.name.casefold() == selected.name.casefold()
            ),
            None,
        )

    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.mode = "leaderboard"
        self._sync_controls()
        await interaction.response.edit_message(
            embed=build_guild_recent_embed(self.leaderboard_result),
            view=self,
        )

    @discord.ui.button(label="Latest Raid", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def latest_raid(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = self.latest_player()
        if player is None:
            await interaction.response.send_message(
                "Select a player who participated in the latest report first.",
                ephemeral=True,
            )
            return
        self.mode = "latest"
        self._sync_controls()
        await interaction.response.edit_message(
            embed=build_player_detail_embed(
                self.latest_report,
                player,
                guild_emojis=self.guild_emojis,
            ),
            view=self,
        )

    @discord.ui.button(label="Top Parses", style=discord.ButtonStyle.success, emoji="🏆", row=0)
    async def top_parses(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = self.selected_player()
        if player is None:
            await interaction.response.send_message("Select a player first.", ephemeral=True)
            return
        server = _normalize_realm_slug(player.server)
        if not server:
            await interaction.response.send_message(
                "Warcraft Logs did not provide a realm for this player.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        try:
            self.character_result = await self.character_service.get_character_performance(
                player.name,
                server,
                self.region,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not load historical parses: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        self.mode = "top"
        self._sync_controls()
        await interaction.edit_original_response(
            embed=build_character_card_embed(
                self.character_result,
                "heroic" if self.difficulty == 4 else "normal",
                self.metric,
                self.guild_emojis,
            ),
            view=self,
        )

    @discord.ui.button(label="Normal 10", style=discord.ButtonStyle.secondary, row=1)
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._switch_difficulty(interaction, 3)

    @discord.ui.button(label="Heroic 10", style=discord.ButtonStyle.primary, row=1)
    async def heroic(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._switch_difficulty(interaction, 4)

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.secondary, emoji="⚔️", row=1)
    async def damage(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.metric = "damage"
        await self._show_character_state(interaction)

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=1)
    async def healing(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.metric = "healing"
        await self._show_character_state(interaction)

    @discord.ui.button(label="Avoidable DTPS", style=discord.ButtonStyle.danger, emoji="🩸", row=1)
    async def dtps(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            result = await self.dtps_service.get_leaderboard(
                self.latest_report.report_code,
                "dtps",
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not load avoidable DTPS: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        self.mode = "dtps"
        self._sync_controls()
        await interaction.edit_original_response(embed=build_dtps_embed(result), view=self)

    async def _switch_difficulty(
        self,
        interaction: discord.Interaction,
        difficulty: int,
    ) -> None:
        self.difficulty = difficulty
        if self.mode == "top" and self.character_result is not None:
            await self._show_character_state(interaction)
            return
        await interaction.response.defer()
        try:
            self.leaderboard_result = await self.recent_service.get_leaderboard(
                self.guild_id,
                difficulty=difficulty,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not switch leaderboard difficulty: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return
        self.mode = "leaderboard"
        self._replace_select()
        self._sync_controls()
        await interaction.edit_original_response(
            embed=build_guild_recent_embed(self.leaderboard_result),
            view=self,
        )

    async def _show_character_state(self, interaction: discord.Interaction) -> None:
        if self.character_result is None:
            await interaction.response.send_message("Open Top Parses first.", ephemeral=True)
            return
        self.mode = "top"
        self._sync_controls()
        await interaction.response.edit_message(
            embed=build_character_card_embed(
                self.character_result,
                "heroic" if self.difficulty == 4 else "normal",
                self.metric,
                self.guild_emojis,
            ),
            view=self,
        )

    def _replace_select(self) -> None:
        for child in tuple(self.children):
            if isinstance(child, GuildLeaderboardPlayerSelect):
                self.remove_item(child)
        self.add_item(GuildLeaderboardPlayerSelect(self))

    def _sync_controls(self) -> None:
        self.normal.style = (
            discord.ButtonStyle.primary if self.difficulty == 3 else discord.ButtonStyle.secondary
        )
        self.heroic.style = (
            discord.ButtonStyle.primary if self.difficulty == 4 else discord.ButtonStyle.secondary
        )
        top_mode = self.mode == "top"
        self.damage.disabled = not top_mode
        self.healing.disabled = not top_mode
        self.damage.style = (
            discord.ButtonStyle.success
            if top_mode and self.metric == "damage"
            else discord.ButtonStyle.secondary
        )
        self.healing.style = (
            discord.ButtonStyle.success
            if top_mode and self.metric == "healing"
            else discord.ButtonStyle.secondary
        )


def build_guild_recent_embed(result: GuildRecentLeaderboardResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.guild_name} — Recent Raider Leaderboard",
        url=result.url,
        description=(
            f"**{result.difficulty_label} • Recent raiders**\n"
            "Tanks and DPS use DPS rankings; healers use HPS rankings. "
            "Players are ordered by average parse."
        ),
        color=discord.Color.orange(),
    )
    tanks = [p for p in result.damage_players if p.role_category == "Tank"]
    dps = [p for p in result.damage_players if p.role_category == "DPS"]
    healers = list(result.healing_players)
    for label, players in (
        ("🛡 Tanks — DPS", tanks),
        ("💚 Healers — HPS", healers),
        ("⚔ DPS — DPS", dps),
    ):
        lines = [_format_player(position, player) for position, player in enumerate(players, 1)]
        embed.add_field(
            name=label,
            value="\n".join(lines)[:1024] if lines else "No ranked players.",
            inline=False,
        )
    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(text=f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}")
    return embed


def build_dtps_embed(result: ReportLeaderboardResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.report_title} — Avoidable DTPS"[:256],
        url=result.url,
        description="Configured avoidable mechanics only. Lower is better.",
        color=discord.Color.red(),
    )
    lines = [
        f"**{position}. {entry.name}** — {entry.dtps:,.1f} DTPS • "
        f"{entry.total_avoidable_damage:,.0f} damage • {entry.hit_count} hits"
        for position, entry in enumerate(result.dtps_entries[:20], 1)
    ]
    embed.add_field(
        name="Avoidable damage ranking",
        value="\n".join(lines)[:1024] if lines else "No configured avoidable damage was found.",
        inline=False,
    )
    return embed


def _format_player(position: int, player: WarcraftLogsPlayerSummary) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"**{position}.**")
    icon = _spec_emoji_text(player.primary_spec, player.class_name)
    average = "—" if player.average_parse is None else f"{player.average_parse:.1f}"
    spec = f" ({player.primary_spec})" if player.primary_spec else ""
    return f"{medal} {icon}**{player.name}**{spec} — Avg **{average}**"


def _spec_emoji_text(spec_name: str | None, class_name: str | None) -> str:
    for candidate in (spec_name, class_name):
        if not candidate:
            continue
        direct = config.SPEC_EMOJIS.get(candidate) or config.CLASS_EMOJIS.get(candidate)
        if direct:
            return f"{direct} "
        wanted = _normalize(candidate)
        for key, emoji in config.SPEC_EMOJIS.items():
            if _normalize(key) == wanted:
                return f"{emoji} "
    return ""


def _select_emoji(player: WarcraftLogsPlayerSummary) -> str | None:
    # SelectOption accepts a partial emoji string in discord.py.
    value = _spec_emoji_text(player.primary_spec, player.class_name).strip()
    return value or None


def boss_emoji_text(encounter_name: str | None) -> str:
    return BOSS_EMOJIS.get(_normalize(encounter_name), "")


def _normalize_realm_slug(value: str | None) -> str:
    # Warcraft Logs realm slugs remove apostrophes: Shek'zeer -> shekzeer.
    text = str(value or "").strip().casefold().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
