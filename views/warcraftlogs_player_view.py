from __future__ import annotations

from datetime import datetime, timezone

import discord

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceResult,
    WarcraftLogsPlayerSummary,
)


_ROLE_ORDER = ("Tank", "Healer", "DPS")
_ROLE_LABELS = {
    "Tank": "🛡 Tanks",
    "Healer": "💚 Healers",
    "DPS": "⚔ DPS",
}


class WarcraftLogsPlayerSelect(discord.ui.Select):
    def __init__(self, summaries: tuple[WarcraftLogsPlayerSummary, ...]) -> None:
        options: list[discord.SelectOption] = []
        for index, player in enumerate(summaries[:25]):
            spec = player.primary_spec or player.class_name or "Unknown spec"
            average = (
                f"Avg {player.average_parse:.1f}"
                if player.average_parse is not None
                else "No parse average"
            )
            options.append(
                discord.SelectOption(
                    label=player.name[:100],
                    value=str(index),
                    description=f"{spec} • {average}"[:100],
                )
            )

        super().__init__(
            placeholder="Select a player for boss-by-boss details",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, WarcraftLogsPlayerView):
            return
        index = int(self.values[0])
        player = view.result.player_summaries[index]
        await interaction.response.edit_message(
            embed=build_player_detail_embed(view.result, player),
            view=view,
        )


class WarcraftLogsPlayerView(discord.ui.View):
    def __init__(
        self,
        result: WarcraftLogsPlayerPerformanceResult,
        *,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.result = result
        self.owner_id = int(owner_id)
        self.add_item(WarcraftLogsPlayerSelect(result.player_summaries))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this player view can use its controls.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Leaderboard", style=discord.ButtonStyle.secondary, emoji="📊")
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            embed=build_player_leaderboard_embed(self.result),
            view=self,
        )


def build_player_leaderboard_embed(
    result: WarcraftLogsPlayerPerformanceResult,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{result.report_title} — Player Performance"[:256],
        description=(
            f"[Open report]({result.url})\n"
            "Players are grouped by role and ranked by average parse."
        ),
        color=discord.Color.orange(),
    )

    if not result.player_summaries:
        embed.add_field(
            name="Players",
            value="No player performance rows could be normalized for this report.",
            inline=False,
        )
    else:
        grouped = {
            role: [p for p in result.player_summaries if p.role_category == role]
            for role in _ROLE_ORDER
        }
        for role in _ROLE_ORDER:
            players = grouped[role]
            if not players:
                continue
            lines = [
                _format_leaderboard_player(index + 1, player)
                for index, player in enumerate(players)
            ]
            embed.add_field(
                name=_ROLE_LABELS[role],
                value="\n".join(lines)[:1024],
                inline=False,
            )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=(
            f"Report {result.report_code} • "
            f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    )
    return embed


def build_player_detail_embed(
    result: WarcraftLogsPlayerPerformanceResult,
    player: WarcraftLogsPlayerSummary,
) -> discord.Embed:
    identity = player.name
    if player.primary_spec:
        identity += f" — {player.primary_spec}"

    embed = discord.Embed(
        title=identity[:256],
        description=f"{player.role_category} • [Open report]({result.url})",
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
            f"(σ {player.parse_stddev:.1f})"
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
    lines = [_format_boss_row(row.encounter_name, row.rank_percent, row.amount) for row in boss_rows]
    if lines:
        embed.add_field(name="Bosses", value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(name="Bosses", value="No boss rows available.", inline=False)

    embed.set_footer(text=f"Report {result.report_code} • Use Leaderboard to return")
    return embed


def _format_leaderboard_player(position: int, player: WarcraftLogsPlayerSummary) -> str:
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(position, f"**{position}.**")
    spec = f" ({player.primary_spec})" if player.primary_spec else ""
    average = f"Avg {player.average_parse:.1f}" if player.average_parse is not None else "Avg —"
    best = f"Best {player.best_parse:.1f}" if player.best_parse is not None else "Best —"
    return f"{medal} **{player.name}**{spec} — {average} • {best}"


def _format_boss_row(
    encounter_name: str | None,
    rank_percent: float | None,
    amount: float | None,
) -> str:
    name = encounter_name or "Unknown encounter"
    details: list[str] = []
    if rank_percent is not None:
        details.append(f"{rank_percent:.1f}")
    if amount is not None:
        details.append(f"{amount:,.0f}")
    return f"**{name}** — {' • '.join(details) if details else 'No metrics'}"


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
