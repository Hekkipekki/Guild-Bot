from __future__ import annotations

from typing import Any

from services.warcraftlogs.rankings_service import GuildRankingEntry


_CATEGORY_LABELS = {
    "progress": "Progress",
    "speed": "Speed",
    "completeRaidSpeed": "Complete Raid Speed",
}


def parse_guild_ranking_categories(value: Any) -> tuple[GuildRankingEntry, ...]:
    """Parse the current Classic Warcraft Logs GuildZoneRankings response.

    The API returns overall categories such as ``progress`` and ``speed``.
    Each scope rank is an object whose numeric rank is stored in ``number``.
    Missing categories are retained as unranked entries so Discord can show the
    complete ranking summary instead of silently omitting them.
    """
    if not isinstance(value, dict):
        return ()

    entries: list[GuildRankingEntry] = []
    for key, label in _CATEGORY_LABELS.items():
        block = value.get(key)
        if block is None:
            continue
        if not isinstance(block, dict):
            continue

        entries.append(
            GuildRankingEntry(
                encounter_name=label,
                world_rank=_nested_rank_number(block.get("worldRank")),
                region_rank=_nested_rank_number(block.get("regionRank")),
                server_rank=_nested_rank_number(block.get("serverRank")),
                rank_percent=_first_nested_percentile(block),
            )
        )

    return tuple(entries)


def _nested_rank_number(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        value = value.get("number")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_nested_percentile(block: dict[str, Any]) -> float | None:
    for key in ("worldRank", "regionRank", "serverRank"):
        value = block.get(key)
        if not isinstance(value, dict):
            continue
        percentile = value.get("percentile")
        if percentile is None or isinstance(percentile, bool):
            continue
        try:
            return float(percentile)
        except (TypeError, ValueError):
            continue
    return None
