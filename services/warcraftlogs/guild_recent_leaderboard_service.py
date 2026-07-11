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
_DIFFICULTY_KEYS = ("difficulty", "difficultyID", "difficultyId")


@dataclass(frozen=True)
class GuildRecentLeaderboardResult:
    guild_id: int
    guild_name: str
    difficulty: int
    difficulty_available: bool
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
    """Fetch guild recent-raider DPS/HPS rankings from Guild.zoneRanking.

    Classic's web route accepts a difficulty query parameter, but the public
    Guild.zoneRanking GraphQL field may not expose a matching argument. In that
    case Heroic remains available from the default payload. Normal is only
    exposed when the payload itself contains identifiable difficulty blocks.
    """

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

        damage_guild, raw_damage, damage_filtered = await self._fetch_metric(
            clean_guild_id, clean_difficulty, "dps"
        )
        healing_guild, raw_healing, healing_filtered = await self._fetch_metric(
            clean_guild_id, clean_difficulty, "hps"
        )
        difficulty_available = damage_filtered or healing_filtered or clean_difficulty == 4

        if clean_difficulty == 3 and not difficulty_available:
            damage_players: tuple[WarcraftLogsPlayerSummary, ...] = ()
            healing_players: tuple[WarcraftLogsPlayerSummary, ...] = ()
        else:
            damage_summaries = aggregate_player_performance(
                parse_player_performance_rows(raw_damage)
            )
            healing_summaries = aggregate_player_performance(
                parse_player_performance_rows(raw_healing)
            )
            damage_players = tuple(
                sorted(
                    (p for p in damage_summaries if p.role_category != "Healer"),
                    key=_average_sort_key,
                )
            )
            healing_players = tuple(
                sorted(
                    (p for p in healing_summaries if p.role_category == "Healer"),
                    key=_average_sort_key,
                )
            )

        result = GuildRecentLeaderboardResult(
            guild_id=clean_guild_id,
            guild_name=damage_guild or healing_guild or f"Guild {clean_guild_id}",
            difficulty=clean_difficulty,
            difficulty_available=difficulty_available,
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
    ) -> tuple[str, Any, bool]:
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
        if difficulty_arg is not None:
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

        if difficulty_arg is not None:
            return str(guild.get("name") or ""), raw, True

        filtered, found_marker = _extract_difficulty_payload(raw, difficulty)
        return str(guild.get("name") or ""), filtered if found_marker else raw, found_marker


def _extract_difficulty_payload(value: Any, difficulty: int) -> tuple[Any, bool]:
    """Return only matching difficulty branches when the JSON payload labels them."""

    found_marker = False

    def walk(node: Any) -> Any:
        nonlocal found_marker
        if isinstance(node, dict):
            marker = _difficulty_value(node)
            if marker is not None:
                found_marker = True
                if marker != difficulty:
                    return None
            output: dict[str, Any] = {}
            for key, child in node.items():
                filtered = walk(child)
                if filtered is not None:
                    output[key] = filtered
            return output
        if isinstance(node, list):
            output = []
            for child in node:
                filtered = walk(child)
                if filtered is not None:
                    output.append(filtered)
            return output
        return node

    return walk(value), found_marker


def _difficulty_value(data: dict[str, Any]) -> int | None:
    for key in _DIFFICULTY_KEYS:
        value = data.get(key)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed in (3, 4):
            return parsed
    return None


def _average_sort_key(player: WarcraftLogsPlayerSummary) -> tuple[bool, float, str]:
    return (
        player.average_parse is None,
        -(player.average_parse or 0),
        player.name.casefold(),
    )


def _first_supported(supported: set[str], candidates: tuple[str, ...]) -> str | None:
    return next((name for name in candidates if name in supported), None)
