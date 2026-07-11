from __future__ import annotations

from datetime import datetime, timezone

import discord

from services.warcraftlogs.character_performance_service import (
    CharacterParseEntry,
    CharacterPerformanceResult,
)


class WarcraftLogsCharacterView(discord.ui.View):
    def __init__(
        self,
        result: CharacterPerformanceResult,
        *,
        owner_id: int,
        difficulty: str = "heroic",
        metric: str = "damage",
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.result = result
        self.owner_id = int(owner_id)
        self.difficulty = difficulty
        self.metric = metric
        self._sync_button_styles()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this character card can use its controls.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Normal 10", style=discord.ButtonStyle.secondary, row=0)
    async def normal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.difficulty = "normal"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Heroic 10", style=discord.ButtonStyle.primary, row=0)
    async def heroic(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.difficulty = "heroic"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.success, emoji="⚔️", row=1)
    async def damage(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.metric = "damage"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=1)
    async def healing(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.metric = "healing"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    def _sync_button_styles(self) -> None:
        self.normal.style = (
            discord.ButtonStyle.primary
            if self.difficulty == "normal"
            else discord.ButtonStyle.secondary
        )
        self.heroic.style = (
            discord.ButtonStyle.primary
            if self.difficulty == "heroic"
            else discord.ButtonStyle.secondary
        )
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


def build_character_card_embed(
    result: CharacterPerformanceResult,
    difficulty: str,
    metric: str,
) -> discord.Embed:
    difficulty_label = "Heroic 10-player" if difficulty == "heroic" else "Normal 10-player"
    metric_label = "Damage" if metric == "damage" else "Healing"
    entries = result.entries(difficulty, metric)

    embed = discord.Embed(
        title=f"{result.character_name} — Top Parses"[:256],
        description=(
            f"**{difficulty_label} • {metric_label} • All specs**\n"
            f"[{result.server_slug.title()} • {result.region.upper()} • Open character page]"
            f"({result.url(difficulty, metric)})"
        ),
        color=discord.Color.orange(),
    )

    if not entries:
        embed.add_field(
            name="Personal bests",
            value=(
                "No character ranking rows were returned for this difficulty and metric. "
                "This can also mean the live Classic schema needs one more parser adjustment."
            ),
            inline=False,
        )
    else:
        by_spec: dict[str, list[CharacterParseEntry]] = {}
        for entry in entries:
            by_spec.setdefault(entry.spec_name or "Unknown spec", []).append(entry)

        for spec_name, spec_entries in list(by_spec.items())[:6]:
            lines = [_format_entry(entry) for entry in spec_entries[:14]]
            embed.add_field(
                name=spec_name[:256],
                value="\n".join(lines)[:1024],
                inline=False,
            )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=(
            "Historical character rankings • separate from the selected report • "
            f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    )
    return embed


def _format_entry(entry: CharacterParseEntry) -> str:
    percentile = "—" if entry.rank_percent is None else f"{entry.rank_percent:.1f}"
    color_marker = _parse_marker(entry.rank_percent)
    details = [f"{color_marker} **{entry.encounter_name}** — **{percentile}**"]
    suffix: list[str] = []
    if entry.amount is not None:
        suffix.append(f"{entry.amount:,.0f}")
    if entry.total_kills is not None:
        suffix.append(f"{entry.total_kills} kills")
    if suffix:
        details.append(f" ({' • '.join(suffix)})")
    return "".join(details)


def _parse_marker(value: float | None) -> str:
    if value is None:
        return "⚪"
    if value >= 99:
        return "🟨"
    if value >= 95:
        return "🟧"
    if value >= 75:
        return "🟪"
    if value >= 50:
        return "🟦"
    if value >= 25:
        return "🟩"
    return "⬜"
