from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

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
    WarcraftLogsPlayerPerformanceService,
    WarcraftLogsPlayerSummary,
)
from services.warcraftlogs.report_leaderboard_service import (
    ReportLeaderboardResult,
    WarcraftLogsReportLeaderboardService,
)
from services.warcraftlogs.reports_service import WarcraftLogsReport
from views.warcraftlogs_character_view import build_character_card_embed
from views.warcraftlogs_player_view import build_player_detail_embed


_SPEC_EMOJI_ALIASES = {
    ("restoration", "druid"): ("restorationdruid",),
    ("restoration", "shaman"): ("restorationshaman",),
    ("holy", "priest"): ("holypriest",),
    ("holy", "paladin"): ("holypaladin",),
    ("protection", "warrior"): ("protectionwarrior",),
    ("protection", "paladin"): ("protectionpaladin",),
    ("frost", "deathknight"): ("frostdk",),
    ("enhancement", "shaman"): ("enhancement", "enmhancement"),
    ("subtlety", "rogue"): ("subtlety", "sublety"),
}


class PlayerSelect(discord.ui.Select):
    def __init__(self, view: "WarcraftLogsGuildLeaderboardView") -> None:
        players = view.active_players()
        if not players:
            raise ValueError("Cannot create a player dropdown without players.")

        options: list[discord.SelectOption] = []
        for index, player in enumerate(players[:25]):
            spec = player.primary_spec or player.class_name or "Unknown spec"
            average = "—" if player.average_parse is None else f"{player.average_parse:.1f}"
            options.append(
                discord.SelectOption(
                    label=player.name[:100],
                    value=str(index),
                    description=f"{spec} • Avg {average}"[:100],
                    emoji=_find_spec_emoji(player, view.guild_emojis),
                )
            )

        super().__init__(
            placeholder="Select a player",
            min_values=1,
            max_values=1,
            options=options,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, WarcraftLogsGuildLeaderboardView):
            return

        players = view.active_players()
        if not players:
            await interaction.response.send_message(
                "No players are available in this view.",
                ephemeral=True,
            )
            return

        try:
            selected = players[int(self.values[0])]
        except (IndexError, TypeError, ValueError):
            await interaction.response.send_message(
                "That player is no longer available. Reopen the player list.",
                ephemeral=True,
            )
            return

        view.selected_identity = _identity(selected)
        view.character_result = None
        report_player = view.report_player(selected)

        if report_player is None:
            embed = discord.Embed(
                title=f"{selected.name} — Performance",
                description=(
                    "This player is present in the three-week leaderboard but has no matching "
                    "rows in the currently selected report. Use **Top Parses** for historical data."
                ),
                color=discord.Color.orange(),
            )
        else:
            embed = build_player_detail_embed(
                view.current_report,
                report_player,
                guild_emojis=view.guild_emojis,
            )

        view.mode = "player"
        view._sync_controls()
        await interaction.response.edit_message(embed=embed, view=view)


class ReportSelect(discord.ui.Select):
    def __init__(self, view: "WarcraftLogsGuildLeaderboardView") -> None:
        reports = view.leaderboard_result.reports[:20]
        if not reports:
            raise ValueError("Cannot create a report dropdown without reports.")

        options = [
            discord.SelectOption(
                label=report.title[:100],
                value=report.code,
                description=_report_description(report)[:100],
            )
            for report in reports
        ]
        super().__init__(
            placeholder="Select a recent report",
            min_values=1,
            max_values=1,
            options=options,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, WarcraftLogsGuildLeaderboardView):
            return

        await interaction.response.defer()
        code = self.values[0]
        try:
            view.current_report = await view.performance_service.get_report_player_performance(code)
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not load report: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        view.selected_identity = None
        view.character_result = None
        view.mode = "report"
        view._replace_select(view._make_player_select())
        view._sync_controls()
        await interaction.edit_original_response(
            embed=build_report_overview_embed(
                view.current_report,
                view.metric,
                view.guild_emojis,
                allowed_character_names=view.allowed_character_names,
            ),
            view=view,
        )


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
        performance_service: WarcraftLogsPlayerPerformanceService,
        character_service: WarcraftLogsCharacterPerformanceService,
        dtps_service: WarcraftLogsReportLeaderboardService,
        guild_emojis: tuple[discord.Emoji, ...] = (),
        allowed_character_names: set[str] | None = None,
        timeout: float = 600,
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = int(owner_id)
        self.guild_id = int(guild_id)
        self.region = region
        self.latest_report = latest_report
        self.current_report = latest_report
        self.leaderboard_result = leaderboard_result
        self.recent_service = recent_service
        self.performance_service = performance_service
        self.character_service = character_service
        self.dtps_service = dtps_service
        self.guild_emojis = guild_emojis
        self.allowed_character_names = (
            None
            if allowed_character_names is None
            else {
                _normalize_name(name)
                for name in allowed_character_names
                if _normalize_name(name)
            }
        )
        self.difficulty = leaderboard_result.difficulty
        self.metric = "dps"
        self.mode = "leaderboard"
        self.mode_before_reports = "leaderboard"
        self.selected_identity: tuple[str, str] | None = None
        self.character_result: CharacterPerformanceResult | None = None
        self._replace_select(self._make_player_select())
        self._sync_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this leaderboard can use its controls.",
            ephemeral=True,
        )
        return False

    def active_players(self) -> tuple[WarcraftLogsPlayerSummary, ...]:
        if self.mode in {"report", "player"}:
            players = self._filter_raid_team(self.current_report.player_summaries)
            if self.metric == "hps":
                return tuple(player for player in players if player.role_category == "Healer")
            return tuple(player for player in players if player.role_category != "Healer")

        if self.metric == "hps":
            return self.leaderboard_result.healing_players
        return self.leaderboard_result.damage_players

    def _filter_raid_team(
        self,
        players: tuple[WarcraftLogsPlayerSummary, ...],
    ) -> tuple[WarcraftLogsPlayerSummary, ...]:
        if self.allowed_character_names is None:
            return players
        return tuple(
            player
            for player in players
            if _normalize_name(player.name) in self.allowed_character_names
        )

    def selected_player(self) -> WarcraftLogsPlayerSummary | None:
        if self.selected_identity is None:
            return None

        for player in self.active_players():
            if _identity(player) == self.selected_identity:
                return player

        for player in (
            *self.leaderboard_result.damage_players,
            *self.leaderboard_result.healing_players,
            *self._filter_raid_team(self.current_report.player_summaries),
        ):
            if _identity(player) == self.selected_identity:
                return player
        return None

    def report_player(self, selected: WarcraftLogsPlayerSummary) -> WarcraftLogsPlayerSummary | None:
        eligible = self._filter_raid_team(self.current_report.player_summaries)
        exact = [player for player in eligible if _identity(player) == _identity(selected)]
        if exact:
            return exact[0]
        return next(
            (
                player
                for player in eligible
                if player.name.casefold() == selected.name.casefold()
            ),
            None,
        )

    def _make_player_select(self) -> PlayerSelect | None:
        return PlayerSelect(self) if self.active_players() else None

    def _make_report_select(self) -> ReportSelect | None:
        return ReportSelect(self) if self.leaderboard_result.reports else None

    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.mode = "leaderboard"
        self.selected_identity = None
        self.character_result = None
        self._replace_select(self._make_player_select())
        self._sync_controls()
        await interaction.response.edit_message(
            embed=build_guild_recent_embed(self.leaderboard_result, self.metric),
            view=self,
        )

    @discord.ui.button(label="Latest Raid", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def latest_raid(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        code = self.leaderboard_result.latest_report_code
        if not code:
            await interaction.response.send_message(
                "No matching report exists for this difficulty.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            self.current_report = await self.performance_service.get_report_player_performance(code)
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not load latest report: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        self.mode = "report"
        self.mode_before_reports = "report"
        self.selected_identity = None
        self.character_result = None
        self._replace_select(self._make_player_select())
        self._sync_controls()
        await interaction.edit_original_response(
            embed=build_report_overview_embed(
                self.current_report,
                self.metric,
                self.guild_emojis,
                allowed_character_names=self.allowed_character_names,
            ),
            view=self,
        )

    @discord.ui.button(label="Recent Reports", style=discord.ButtonStyle.secondary, emoji="🗂️", row=0)
    async def recent_reports(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.mode == "reports":
            self.mode = self.mode_before_reports
            self._replace_select(self._make_player_select())
            self._sync_controls()
            embed = (
                build_report_overview_embed(
                    self.current_report,
                    self.metric,
                    self.guild_emojis,
                    allowed_character_names=self.allowed_character_names,
                )
                if self.mode in {"report", "player"}
                else build_guild_recent_embed(self.leaderboard_result, self.metric)
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        self.mode_before_reports = (
            "report" if self.mode in {"report", "player"} else "leaderboard"
        )
        self.mode = "reports"
        self._replace_select(self._make_report_select())
        self._sync_controls()
        await interaction.response.edit_message(
            embed=build_recent_reports_embed(self.leaderboard_result),
            view=self,
        )

    @discord.ui.button(label="Top Parses", style=discord.ButtonStyle.success, emoji="🏆", row=0)
    async def top_parses(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        player = self.selected_player()
        if player is None:
            await interaction.response.send_message(
                "Select a player first. Use **Players** if the report dropdown is open.",
                ephemeral=True,
            )
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
                "healing" if self.metric == "hps" else "damage",
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

    @discord.ui.button(label="DPS", style=discord.ButtonStyle.success, emoji="⚔️", row=1)
    async def damage(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.metric = "dps"
        await self._refresh_metric_view(interaction)

    @discord.ui.button(label="HPS", style=discord.ButtonStyle.secondary, emoji="💚", row=1)
    async def healing(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.metric = "hps"
        await self._refresh_metric_view(interaction)

    @discord.ui.button(label="DTPS", style=discord.ButtonStyle.danger, emoji="🩸", row=1)
    async def dtps(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        previous_mode = self.mode
        button.disabled = True
        loading_embed = discord.Embed(
            title="Calculating Avoidable DTPS…",
            description=(
                "Fetching and filtering damage-taken events for the selected report. "
                "The first request can take a little while."
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(embed=loading_embed, view=self)
        try:
            result = await self.dtps_service.get_leaderboard(
                self.current_report.report_code,
                "dtps",
            )
        except Exception as exc:
            button.disabled = False
            self.mode = previous_mode
            self._sync_controls()
            error_embed = discord.Embed(
                title="Avoidable DTPS could not be loaded",
                description=f"`{type(exc).__name__}: {exc}`",
                color=discord.Color.red(),
            )
            await interaction.edit_original_response(embed=error_embed, view=self)
            return

        button.disabled = False
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
            self._sync_controls()
            await interaction.response.edit_message(
                embed=build_character_card_embed(
                    self.character_result,
                    "heroic" if difficulty == 4 else "normal",
                    "healing" if self.metric == "hps" else "damage",
                    self.guild_emojis,
                ),
                view=self,
            )
            return

        await interaction.response.defer()
        try:
            self.leaderboard_result = await self.recent_service.get_leaderboard(
                self.guild_id,
                difficulty=difficulty,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"⚠ Could not switch difficulty: `{type(exc).__name__}: {exc}`",
                ephemeral=True,
            )
            return

        if self.leaderboard_result.latest_report_code:
            self.latest_report = await self.performance_service.get_report_player_performance(
                self.leaderboard_result.latest_report_code
            )
            self.current_report = self.latest_report

        self.mode = "leaderboard"
        self.mode_before_reports = "leaderboard"
        self.selected_identity = None
        self.character_result = None
        self._replace_select(self._make_player_select())
        self._sync_controls()
        await interaction.edit_original_response(
            embed=build_guild_recent_embed(self.leaderboard_result, self.metric),
            view=self,
        )

    async def _refresh_metric_view(self, interaction: discord.Interaction) -> None:
        if self.mode == "top" and self.character_result is not None:
            self._sync_controls()
            await interaction.response.edit_message(
                embed=build_character_card_embed(
                    self.character_result,
                    "heroic" if self.difficulty == 4 else "normal",
                    "healing" if self.metric == "hps" else "damage",
                    self.guild_emojis,
                ),
                view=self,
            )
            return

        self.selected_identity = None
        self.character_result = None
        if self.mode in {"report", "player"}:
            self.mode = "report"
            embed = build_report_overview_embed(
                self.current_report,
                self.metric,
                self.guild_emojis,
                allowed_character_names=self.allowed_character_names,
            )
        else:
            self.mode = "leaderboard"
            embed = build_guild_recent_embed(self.leaderboard_result, self.metric)

        self._replace_select(self._make_player_select())
        self._sync_controls()
        await interaction.response.edit_message(embed=embed, view=self)

    def _replace_select(self, item: discord.ui.Select | None) -> None:
        for child in tuple(self.children):
            if isinstance(child, (PlayerSelect, ReportSelect)):
                self.remove_item(child)
        if item is not None:
            self.add_item(item)

    def _sync_controls(self) -> None:
        self.normal.style = (
            discord.ButtonStyle.primary
            if self.difficulty == 3
            else discord.ButtonStyle.secondary
        )
        self.heroic.style = (
            discord.ButtonStyle.primary
            if self.difficulty == 4
            else discord.ButtonStyle.secondary
        )
        self.damage.style = (
            discord.ButtonStyle.success
            if self.metric == "dps"
            else discord.ButtonStyle.secondary
        )
        self.healing.style = (
            discord.ButtonStyle.success
            if self.metric == "hps"
            else discord.ButtonStyle.secondary
        )
        self.recent_reports.label = "Players" if self.mode == "reports" else "Recent Reports"
        self.recent_reports.emoji = "👥" if self.mode == "reports" else "🗂️"


def build_guild_recent_embed(
    result: GuildRecentLeaderboardResult,
    metric: str = "dps",
) -> discord.Embed:
    metric_label = "HPS" if metric == "hps" else "DPS"
    filter_note = (
        "\nFiltered to characters registered by configured raid-team members."
        if result.raid_team_filtered
        else ""
    )
    embed = discord.Embed(
        title=f"Recent Performance — {result.difficulty_label} {metric_label}",
        url=result.url,
        description=(
            "Three-week window (21 days). For every player and boss, the best kill parse "
            "is retained; the displayed average is calculated from those best boss parses."
            f"{filter_note}"
        ),
        color=discord.Color.orange(),
    )
    players = result.healing_players if metric == "hps" else result.damage_players
    if metric == "hps":
        sections = (("💚 Healers — HPS", players),)
    else:
        sections = (
            ("🛡 Tanks — DPS", tuple(player for player in players if player.role_category == "Tank")),
            ("⚔ DPS — DPS", tuple(player for player in players if player.role_category == "DPS")),
        )

    empty_text = (
        "No registered raid-team characters had matching kill parses."
        if result.raid_team_filtered
        else "No matching kill parses."
    )
    for label, section in sections:
        lines = [
            _format_player(position, player)
            for position, player in enumerate(section[:20], start=1)
        ]
        embed.add_field(
            name=label,
            value="\n".join(lines)[:1024] if lines else empty_text,
            inline=False,
        )

    embed.set_footer(
        text=(
            f"{len(result.reports)} reports included • Latest: "
            f"{result.latest_report_title or 'None'}"
        )
    )
    return embed


def build_report_overview_embed(
    result: WarcraftLogsPlayerPerformanceResult,
    metric: str,
    guild_emojis: tuple[discord.Emoji, ...],
    *,
    allowed_character_names: set[str] | None = None,
) -> discord.Embed:
    metric_label = "HPS" if metric == "hps" else "DPS"
    players = tuple(
        player
        for player in result.player_summaries
        if (player.role_category == "Healer") == (metric == "hps")
        and (
            allowed_character_names is None
            or _normalize_name(player.name) in allowed_character_names
        )
    )
    players = tuple(
        sorted(players, key=lambda player: (player.average_parse is None, -(player.average_parse or 0)))
    )
    embed = discord.Embed(
        title=f"{result.report_title} — {metric_label} Rankings",
        url=result.url,
        description="Select a player below for the complete boss-by-boss score sheet.",
        color=discord.Color.orange(),
    )
    lines = [
        _format_player(position, player, guild_emojis)
        for position, player in enumerate(players[:20], start=1)
    ]
    embed.add_field(
        name="Players",
        value="\n".join(lines)[:1024] if lines else "No matching ranked raid-team players.",
        inline=False,
    )
    return embed


def build_recent_reports_embed(result: GuildRecentLeaderboardResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"Recent Reports — {result.difficulty_label}",
        description=(
            "Choose a report from the dropdown to inspect its player rankings. "
            "Press **Players** to return without changing report."
        ),
        color=discord.Color.orange(),
    )
    lines = [
        f"**{report.title}** — <t:{int(report.start_time / 1000)}:d>"
        for report in result.reports[:20]
    ]
    embed.add_field(
        name="Included three-week reports",
        value="\n".join(lines)[:1024] if lines else "No matching reports.",
        inline=False,
    )
    return embed


def build_dtps_embed(result: ReportLeaderboardResult) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.report_title} — Avoidable DTPS",
        url=result.url,
        description="Only configured avoidable mechanics count. Lower is better.",
        color=discord.Color.red(),
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
    return embed


def _format_player(
    position: int,
    player: WarcraftLogsPlayerSummary,
    guild_emojis: tuple[discord.Emoji, ...] = (),
) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"**{position}.**")
    emoji = _find_spec_emoji(player, guild_emojis)
    icon = f"{emoji} " if emoji else ""
    spec = f" ({player.primary_spec})" if player.primary_spec else ""
    average = "—" if player.average_parse is None else f"{player.average_parse:.1f}"
    return (
        f"{medal} {icon}**{player.name}**{spec} — Avg **{average}** "
        f"• {player.encounter_count} bosses"
    )


def _find_spec_emoji(
    player: WarcraftLogsPlayerSummary,
    emojis: tuple[discord.Emoji, ...],
) -> discord.Emoji | None:
    emoji_by_name = {_normalize_name(emoji.name): emoji for emoji in emojis}
    spec = _normalize_name(player.primary_spec)
    class_name = _normalize_name(player.class_name)

    aliases = list(_SPEC_EMOJI_ALIASES.get((spec, class_name), ()))
    if spec:
        aliases.append(spec)
    for alias in aliases:
        match = emoji_by_name.get(alias)
        if match is not None:
            return match

    if class_name:
        return emoji_by_name.get(class_name)
    return None


def _identity(player: WarcraftLogsPlayerSummary) -> tuple[str, str]:
    return player.name.casefold(), (player.server or "").casefold()


def _normalize_realm_slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _report_description(report: WarcraftLogsReport) -> str:
    timestamp = datetime.fromtimestamp(report.start_time / 1000, tz=timezone.utc)
    return f"{timestamp.strftime('%Y-%m-%d')} • {report.zone_name or 'Unknown zone'}"
