from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerSummary,
    aggregate_player_performance,
    parse_player_performance_rows,
)
from services.warcraftlogs.rankings_service import WarcraftLogsRankingsService

CACHE_TTL_SECONDS = 600
_DIFFICULTY_ARGUMENT_NAMES = ("difficulty",)
_METRIC_ARGUMENT_NAMES = ("metric", "playerMetric", "playermetric")
_RECENT_ARGUMENT_NAMES = ("recent", "includeRecent", "recentRaiders")


@dataclass(frozen=True)
class GuildRecentLeaderboardResult:
    guild_id: int
    guild_name: str
    difficulty: int
    damage_players: tuple[WarcraftLogsPlayerSummary, ...]
    healing_players: tuple[WarcraftLogsPlayerSummary, ...]
    fetched_at: float
    raw_damage: Any
    raw_healing: Any

    @property
    def difficulty_label(self) -> str:
        return "Heroic 10" if self.difficulty == 4 else "Normal 10"

    @property
    def url(self) -> str:
        difficulty_query = "" if self.difficulty == 4 else "&difficulty=3"
        return (
            "https://classic.warcraftlogs.com/guild/rankings/"
            f"{self.guild_id}/latest?recent=true&size=10{difficulty_query}"
        )


@dataclass
class _CacheEntry:
    result: GuildRecentLeaderboardResult
    expires_at: float


class WarcraftLogsGuildRecentLeaderboardService:
    """Fetch exact guild recent-raider DPS/HPS rankings from Guild.zoneRanking."""

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self.schema_service = WarcraftLogsRankingsService(client)
        self._cache: dict[tuple[int, int], _CacheEntry] = {}

    async def get_leaderboard(
        self,
        guild_id: int,
        *,
        difficulty: int = 4,
        force_refresh: bool = False,
    ) -> GuildRecentLeaderboardResult:
        clean_guild_id = int(guild_id)
        clean_difficulty = int(difficulty)
        if clean_guild_id <= 0:
            raise ValueError("Warcraft Logs guild ID must be positive.")
        if clean_difficulty not in (3, 4):
            raise ValueError("Difficulty must be 3 (Normal) or 4 (Heroic).")

        cache_key = (clean_guild_id, clean_difficulty)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        damage_guild, raw_damage = await self._fetch_metric(
            clean_guild_id,
            clean_difficulty,
            "dps",
        )
        healing_guild, raw_healing = await self._fetch_metric(
            clean_guild_id,
            clean_difficulty,
            "hps",
        )

        damage_summaries = aggregate_player_performance(
            parse_player_performance_rows(raw_damage)
        )
        healing_summaries = aggregate_player_performance(
            parse_player_performance_rows(raw_healing)
        )

        # Damage rankings contain tanks and damage dealers. Healing rankings are
        # kept separate so healer averages always come from HPS.
        damage_players = tuple(
            sorted(
                (player for player in damage_summaries if player.role_category != "Healer"),
                key=_average_sort_key,
            )
        )
        healing_players = tuple(
            sorted(
                (player for player in healing_summaries if player.role_category == "Healer"),
                key=_average_sort_key,
            )
        )

        result = GuildRecentLeaderboardResult(
            guild_id=clean_guild_id,
            guild_name=damage_guild or healing_guild or f"Guild {clean_guild_id}",
            difficulty=clean_difficulty,
            damage_players=damage_players,
            healing_players=healing_players,
            fetched_at=time.time(),
            raw_damage=raw_damage,
            raw_healing=raw_healing,
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + CACHE_TTL_SECONDS,
        )
        return result

    async def _fetch_metric(
        self,
        guild_id: int,
        difficulty: int,
        metric: str,
    ) -> tuple[str, Any]:
        supported_args, ranking_type_name = await self.schema_service._get_zone_ranking_schema()
        selection = await self.schema_service._build_type_selection(
            ranking_type_name,
            visited=frozenset(),
            depth=0,
        )

        argument_parts: list[str] = []
        if "size" in supported_args:
            argument_parts.append("size: 10")

        difficulty_arg = _first_supported(supported_args, _DIFFICULTY_ARGUMENT_NAMES)
        if difficulty_arg is None:
            raise WarcraftLogsRequestError(
                "The Warcraft Logs Guild.zoneRanking schema does not expose a difficulty filter."
            )
        argument_parts.append(f"{difficulty_arg}: {difficulty}")

        metric_arg = _first_supported(supported_args, _METRIC_ARGUMENT_NAMES)
        if metric_arg is None:
            raise WarcraftLogsRequestError(
                "The Warcraft Logs Guild.zoneRanking schema does not expose a player metric filter."
            )
        argument_parts.append(f"{metric_arg}: {metric}")

        recent_arg = _first_supported(supported_args, _RECENT_ARGUMENT_NAMES)
        if recent_arg is None:
            raise WarcraftLogsRequestError(
                "The Warcraft Logs Guild.zoneRanking schema does not expose recent raiders."
            )
        argument_parts.append(f"{recent_arg}: true")

        arguments = ", ".join(argument_parts)
        query = f"""
        query GuildRecentPlayerRankings {{
          guildData {{
            guild(id: {guild_id}) {{
              id
              name
              zoneRankings: zoneRanking({arguments}) {{
                {selection}
              }}
            }}
          }}
        }}
        """
        data = await self.client.query(query)
        guild = data.get("guildData", {}).get("guild")
        if not isinstance(guild, dict):
            raise WarcraftLogsRequestError(f"Warcraft Logs guild {guild_id} was not found.")
        raw = guild.get("zoneRankings")
        if raw is None:
            raise WarcraftLogsRequestError(
                f"Warcraft Logs returned no recent {metric.upper()} rankings."
            )
        return str(guild.get("name") or ""), raw


def _average_sort_key(player: WarcraftLogsPlayerSummary) -> tuple[bool, float, str]:
    return (
        player.average_parse is None,
        -(player.average_parse or 0),
        player.name.casefold(),
    )


def _first_supported(supported: set[str], candidates: tuple[str, ...]) -> str | None:
    return next((name for name in candidates if name in supported), None)
