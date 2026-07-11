from __future__ import annotations

import re
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
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.difficulty = "normal"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Heroic 10", style=discord.ButtonStyle.primary, row=0)
    async def heroic(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.difficulty = "heroic"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Damage", style=discord.ButtonStyle.success, emoji="⚔️", row=1)
    async def damage(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.metric = "damage"
        self._sync_button_styles()
        await interaction.response.edit_message(
            embed=build_character_card_embed(self.result, self.difficulty, self.metric),
            view=self,
        )

    @discord.ui.button(label="Healing", style=discord.ButtonStyle.secondary, emoji="💚", row=1)
    async def healing(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
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
    guild_emojis: tuple[discord.Emoji, ...] = (),
) -> discord.Embed:
    clean_difficulty = "normal" if difficulty.casefold() == "normal" else "heroic"
    metric_label = "Damage" if metric == "damage" else "Healing"
    difficulty_label = "Normal 10-player" if clean_difficulty == "normal" else "Heroic 10-player"
    entries = _best_kill_per_boss(result.entries(clean_difficulty, metric))

    embed = discord.Embed(
        title=f"{result.character_name} — Top Parses"[:256],
        description=(
            f"**{difficulty_label} • {metric_label} • Best result across all specs**\n"
            f"[{result.server_slug.title()} • {result.region.upper()} • Open character page]"
            f"({result.url(clean_difficulty, metric)})"
        ),
        color=discord.Color.orange(),
    )

    if not entries:
        embed.add_field(
            name="Personal bests",
            value=f"No {difficulty_label} boss kills with a ranked parse were returned.",
            inline=False,
        )
    else:
        lines = [_format_entry(entry, guild_emojis) for entry in entries]
        embed.add_field(
            name=f"{difficulty_label} personal bests",
            value="\n".join(lines)[:1024],
            inline=False,
        )

    fetched = datetime.fromtimestamp(result.fetched_at, tz=timezone.utc)
    embed.set_footer(
        text=(
            "One best parse per boss across all specs • kills only • "
            f"Fetched {fetched.strftime('%Y-%m-%d %H:%M UTC')}"
        )
    )
    return embed


def _best_kill_per_boss(
    entries: tuple[CharacterParseEntry, ...],
) -> tuple[CharacterParseEntry, ...]:
    best: dict[str, CharacterParseEntry] = {}
    for entry in entries:
        if entry.rank_percent is None:
            continue
        if entry.total_kills is None or entry.total_kills <= 0:
            continue
        key = _normalize_name(entry.encounter_name)
        if not key:
            continue
        current = best.get(key)
        if current is None or (entry.rank_percent or 0) > (current.rank_percent or 0):
            best[key] = entry
    return tuple(
        sorted(
            best.values(),
            key=lambda entry: (-(entry.rank_percent or 0), entry.encounter_name.casefold()),
        )
    )


def _format_entry(
    entry: CharacterParseEntry,
    guild_emojis: tuple[discord.Emoji, ...],
) -> str:
    percentile = f"{entry.rank_percent:.1f}" if entry.rank_percent is not None else "—"
    boss_emoji = _find_emoji(entry.encounter_name, guild_emojis)
    spec_emoji = _find_emoji(entry.spec_name, guild_emojis)
    boss_icon = f"{boss_emoji} " if boss_emoji else ""
    spec_icon = f"{spec_emoji} " if spec_emoji else ""
    spec = entry.spec_name or "Unknown spec"
    suffix: list[str] = []
    if entry.amount is not None:
        suffix.append(f"{entry.amount:,.0f}")
    if entry.total_kills is not None:
        suffix.append(f"{entry.total_kills} kills")
    details = f" • {' • '.join(suffix)}" if suffix else ""
    return (
        f"{_parse_marker(entry.rank_percent)} {boss_icon}**{entry.encounter_name}** — "
        f"**{percentile}**{details} • {spec_icon}{spec}"
    )


def _find_emoji(
    value: str | None,
    emojis: tuple[discord.Emoji, ...],
) -> discord.Emoji | None:
    wanted = _normalize_name(value)
    if not wanted:
        return None
    for emoji in emojis:
        name = _normalize_name(emoji.name)
        if name == wanted or wanted in name or name in wanted:
            return emoji
    return None


def _normalize_name(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


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
