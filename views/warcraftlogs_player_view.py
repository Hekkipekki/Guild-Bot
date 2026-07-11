from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

from services.warcraftlogs.character_performance_service import (
    CharacterPerformanceResult,
    WarcraftLogsCharacterPerformanceService,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceResult,
    WarcraftLogsPlayerSummary,
)
from views.warcraftlogs_character_view import build_character_card_embed


_ROLE_ORDER = ("Tank", "Healer", "DPS")
_ROLE_LABELS = {
    "Tank": "🛡 Tanks — DPS",
    "Healer": "💚 Healers — HPS",
    "DPS": "⚔ DPS — DPS",
}


class WarcraftLogsPlayerSelect(discord.ui.Select):
    def __init__(
        self,
        summaries: tuple[WarcraftLogsPlayerSummary, ...],
        guild_emojis: tuple[discord.Emoji, ...],
    ) -> None:
        options: list[discord.SelectOption] = []
        for index, player in enumerate(summaries[:25]):
            spec = player.primary_spec or player.class_name or "Unknown spec"
            average = (
                f"Avg {player.average_parse:.1f}"
                if player.average_parse is not None
                else "No ranked average"
            )
            options.append(
                discord.SelectOption(
                    label=player.name[:100],
                    value=str(index),
                    description=f"{spec} • {average}"[:100],
                    emoji=_find_spec_emoji(player, guild_emojis),
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
        if not isinstance(view, WarcraftLogsPlayerView):
            return
        view.selected_player = view.result.player_summaries[int(self.values[0])]
        view.character_result = None
        view._sync_controls(top_parse_mode=False)
        await interaction.response.edit_message(
            embed=build_player_detail_embed(
                view.result,
                view.selected_player,
                guild_emojis=view.guild_emojis,
            ),
            view=view,
        )


class WarcraftLogsPlayerView(discord.ui.View):
    def __init__(
        self,
        result: WarcraftLogsPlayerPerformanceResult,
        *,
        owner_id: int,
        character_service: WarcraftLogsCharacterPerformanceService,
        region: str,
        guild_emojis: tuple[discord.Emoji, ...] = (),
        leaderboard_embed: discord.Embed | None = None,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.result = result
        self.owner_id = int(owner_id)
        self.character_service = character_service
        self.region = region
        self.guild_emojis = guild_emojis
        self.leaderboard_embed = leaderboard_embed
        self.selected_player: WarcraftLogsPlayerSummary | None = None
        self.character_result: CharacterPerformanceResult | None = None
        self.difficulty = "heroic"
        self.metric = "damage"
        self.add_item(WarcraftLogsPlayerSelect(result.player_summaries, guild_emojis))
        self._sync_controls(top_parse_mode=False)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this player view can use its controls.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self._sync_controls(top_parse_mode=False)
        embed = self.leaderboard_embed or build_player_leaderboard_embed(
            self.result,
            guild_emojis=self.guild_emojis,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Latest Raid", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def latest_raid(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.selected_player is None:
            await interaction.response.send_message("Select a player first.", ephemeral=True)
            return
        self._sync_controls(top_parse_mode=False)
        await interaction.response.edit_message(
            embed=build_player_detail_embed(
                self.result,
                self.selected_player,
                guild_emojis=self.guild_emojis,
            ),
            view=self,
        )

    @discord.ui.button(label="Top Parses", style=discord.ButtonStyle.success, emoji="🏆", row=0)
    async def top_parses(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        player = self.selected_player
        if player is None:
            await interaction.response.send_message("Select a player first.", ephemeral=True)
            return
        server = str(player.server or "").strip()
        if not server:
            await interaction.response.send_message(
                "Warcraft Logs did not provide a realm for this player, so historical parses cannot be loaded yet.",
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

        self.difficulty = "heroic"
        self._sync_controls(top_parse_mode=True)
        await interaction.edit_original_response(
            embed=build_character_card_embed(
                self.character_result,
                self.difficulty,
                self.metric,
                self.guild_emojis,
            ),
            view=self,
        )

    @discord.ui.button(label="Normal 10", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def normal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_message(
            "Top Parses currently shows Heroic 10-player kills only.", ephemeral=True
        )

    @discord.ui.button(label="Heroic 10", style=discord.ButtonStyle.secondary, row=1)
    async def heroic(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.difficulty = "heroic"
        await self._show_character_state(interaction)

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.secondary, emoji="⚔️", row=1)
    async def damage(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.metric = "damage"
        await self._show_character_state(interaction)

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=1)
    async def healing(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.metric = "healing"
        await self._show_character_state(interaction)

    async def _show_character_state(self, interaction: discord.Interaction) -> None:
        if self.character_result is None:
            await interaction.response.send_message("Open Top Parses first.", ephemeral=True)
            return
        self._sync_controls(top_parse_mode=True)
        await interaction.response.edit_message(
            embed=build_character_card_embed(
                self.character_result,
                "heroic",
                self.metric,
                self.guild_emojis,
            ),
            view=self,
        )

    def _sync_controls(self, *, top_parse_mode: bool) -> None:
        self.normal.disabled = True
        for control in (self.heroic, self.damage, self.healing):
            control.disabled = not top_parse_mode
            control.style = discord.ButtonStyle.secondary
        if top_parse_mode:
            self.heroic.style = discord.ButtonStyle.primary
            self.damage.style = (
                discord.ButtonStyle.success
                if self.metric == "damage"
                else discord.ButtonStyle.secondary
            )
            self.healing.style = (
                discord.ButtonStyle.success
                if self.metric == "healing"
                else discord.ButtonStyle.secondary
            )


def build_player_leaderboard_embed(
    result: WarcraftLogsPlayerPerformanceResult,
    *,
    guild_emojis: tuple[discord.Emoji, ...] = (),
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.report_title} — Player Leaderboard"[:256],
        description=(
            f"[Open report]({result.url})\n"
            "Grouped by role and ranked by report average. Tanks and DPS use damage rankings; healers use healing rankings."
        ),
        color=discord.Color.orange(),
    )

    grouped = {
        role: sorted(
            (p for p in result.player_summaries if p.role_category == role),
            key=lambda p: (p.average_parse is None, -(p.average_parse or 0), p.name.casefold()),
        )
        for role in _ROLE_ORDER
    }
    for role in _ROLE_ORDER:
        players = grouped[role]
        if not players:
            continue
        lines = [
            _format_leaderboard_player(index + 1, player, guild_emojis)
            for index, player in enumerate(players)
        ]
        embed.add_field(
            name=_ROLE_LABELS[role],
            value="\n".join(lines)[:1024],
            inline=False,
        )

    if not result.player_summaries:
        embed.add_field(
            name="Players",
            value="No player performance rows could be normalized for this report.",
            inline=False,
        )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=f"Report {result.report_code} • Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return embed


def build_player_detail_embed(
    result: WarcraftLogsPlayerPerformanceResult,
    player: WarcraftLogsPlayerSummary,
    *,
    guild_emojis: tuple[discord.Emoji, ...] = (),
) -> discord.Embed:
    identity = player.name
    if player.primary_spec:
        identity += f" — {player.primary_spec}"

    embed = discord.Embed(
        title=identity[:256],
        description=f"{player.role_category} • Latest raid • [Open report]({result.url})",
        color=discord.Color.orange(),
    )

    overview: list[str] = []
    if player.average_parse is not None:
        overview.append(f"**Average:** {player.average_parse:.1f}")
    if player.median_parse is not None:
        overview.append(f"**Median:** {player.median_parse:.1f}")
    if player.best_parse is not None:
        overview.append(f"**Best:** {player.best_parse:.1f}")
    if player.worst_parse is not None:
        overview.append(f"**Worst:** {player.worst_parse:.1f}")
    if player.parse_stddev is not None:
        overview.append(
            f"**Consistency:** {_consistency_stars(player.parse_stddev)} "
            f"(σ {player.parse_stddev:.1f}; lower spread is better)"
        )
    overview.append(f"**Ranked fights:** {player.encounter_count}")
    if player.average_item_level is not None:
        overview.append(f"**Average ilvl:** {player.average_item_level:.1f}")
    embed.add_field(name="Overview", value="\n".join(overview), inline=False)

    boss_rows = sorted(
        player.rows,
        key=lambda row: (
            row.encounter_name is None,
            str(row.encounter_name or "").casefold(),
        ),
    )
    lines = [
        _format_boss_row(
            row.encounter_name,
            row.rank_percent,
            row.amount,
            guild_emojis,
        )
        for row in boss_rows
    ]
    embed.add_field(
        name="Bosses",
        value="\n".join(lines)[:1024] if lines else "No boss rows available.",
        inline=False,
    )
    embed.set_footer(
        text=(
            f"Report {result.report_code} • Consistency: 5★ ≤5σ, 4★ ≤10σ, "
            "3★ ≤15σ, 2★ ≤20σ, 1★ >20σ"
        )
    )
    return embed


def _format_leaderboard_player(
    position: int,
    player: WarcraftLogsPlayerSummary,
    guild_emojis: tuple[discord.Emoji, ...],
) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"**{position}.**")
    emoji = _find_spec_emoji(player, guild_emojis)
    icon = f"{emoji} " if emoji is not None else ""
    spec = f" ({player.primary_spec})" if player.primary_spec else ""
    average = (
        f"Avg **{player.average_parse:.1f}**"
        if player.average_parse is not None
        else "Avg —"
    )
    return f"{medal} {icon}**{player.name}**{spec} — {average}"


def _format_boss_row(
    encounter_name: str | None,
    rank_percent: float | None,
    amount: float | None,
    guild_emojis: tuple[discord.Emoji, ...],
) -> str:
    name = encounter_name or "Unknown encounter"
    emoji = _find_named_emoji(name, guild_emojis)
    icon = f"{emoji} " if emoji else ""
    details: list[str] = []
    if rank_percent is not None:
        details.append(f"**{rank_percent:.1f}**")
    if amount is not None:
        details.append(f"{amount:,.0f}")
    return f"{icon}**{name}** — {' • '.join(details) if details else 'No metrics'}"


def _find_spec_emoji(
    player: WarcraftLogsPlayerSummary,
    emojis: tuple[discord.Emoji, ...],
) -> discord.Emoji | None:
    for candidate in (player.primary_spec, player.class_name):
        found = _find_named_emoji(candidate, emojis)
        if found is not None:
            return found
    return None


def _find_named_emoji(
    value: str | None,
    emojis: tuple[discord.Emoji, ...],
) -> discord.Emoji | None:
    wanted = _normalize_emoji_name(value)
    if not wanted:
        return None
    for emoji in emojis:
        emoji_name = _normalize_emoji_name(emoji.name)
        if emoji_name == wanted or wanted in emoji_name or emoji_name in wanted:
            return emoji
    return None


def _normalize_emoji_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _consistency_stars(stddev: float) -> str:
    if stddev <= 5:
        stars = 5
    elif stddev <= 10:
        stars = 4
    elif stddev <= 15:
        stars = 3
    elif stddev <= 20:
        stars = 2
    else:
        stars = 1
    return "★" * stars + "☆" * (5 - stars)
