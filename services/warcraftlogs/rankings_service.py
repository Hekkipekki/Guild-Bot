from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import (
    WarcraftLogsClient,
    WarcraftLogsRequestError,
)


CACHE_TTL_SECONDS = 600


@dataclass(frozen=True)
class GuildRankingEntry:
    encounter_name: str
    world_rank: int | None = None
    region_rank: int | None = None
    server_rank: int | None = None
    rank_percent: float | None = None


@dataclass(frozen=True)
class GuildRankingsResult:
    guild_id: int
    guild_name: str
    raid_size: int
    zone_name: str | None
    entries: tuple[GuildRankingEntry, ...]
    raw_rankings: Any
    fetched_at: float


@dataclass
class _CacheEntry:
    result: GuildRankingsResult
    expires_at: float


class WarcraftLogsRankingsService:
    """Fetch and normalize guild rankings from the Classic Warcraft Logs API."""

    _GUILD_TYPE_QUERY = """
    query GuildRankingSchema {
      __type(name: "Guild") {
        fields {
          name
          args { name type { kind name ofType { kind name } } }
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[tuple[int, int], _CacheEntry] = {}
        self._zone_ranking_args: set[str] | None = None

    async def get_guild_rankings(
        self,
        guild_id: int,
        *,
        raid_size: int = 10,
        force_refresh: bool = False,
    ) -> GuildRankingsResult:
        clean_guild_id = int(guild_id)
        clean_raid_size = int(raid_size)
        if clean_guild_id <= 0:
            raise ValueError("Warcraft Logs guild ID must be positive.")
        if clean_raid_size not in (10, 25):
            raise ValueError("Raid size must be 10 or 25.")

        cache_key = (clean_guild_id, clean_raid_size)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        supported_args = await self._get_zone_ranking_args()
        argument_parts: list[str] = []
        if "size" in supported_args:
            argument_parts.append(f"size: {clean_raid_size}")
        arguments = f"({', '.join(argument_parts)})" if argument_parts else ""

        # The Classic API field is singular (`zoneRanking`). Alias it to the
        # plural response key so existing parser code and cached payloads remain
        # backward-compatible.
        query = f"""
        query GuildRankings {{
          guildData {{
            guild(id: {clean_guild_id}) {{
              id
              name
              zoneRankings: zoneRanking{arguments}
            }}
          }}
        }}
        """

        data = await self.client.query(query)
        guild_block = data.get("guildData", {}).get("guild")
        if not isinstance(guild_block, dict):
            raise WarcraftLogsRequestError(
                f"Warcraft Logs guild {clean_guild_id} was not found."
            )

        raw_rankings = guild_block.get("zoneRankings")
        if raw_rankings is None:
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned no guild ranking data."
            )

        entries = tuple(_extract_ranking_entries(raw_rankings))
        result = GuildRankingsResult(
            guild_id=clean_guild_id,
            guild_name=str(guild_block.get("name") or f"Guild {clean_guild_id}"),
            raid_size=clean_raid_size,
            zone_name=_find_zone_name(raw_rankings),
            entries=entries,
            raw_rankings=raw_rankings,
            fetched_at=time.time(),
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + CACHE_TTL_SECONDS,
        )
        return result

    async def _get_zone_ranking_args(self) -> set[str]:
        if self._zone_ranking_args is not None:
            return self._zone_ranking_args

        try:
            data = await self.client.query(self._GUILD_TYPE_QUERY)
            type_block = data.get("__type")
            fields = type_block.get("fields", []) if isinstance(type_block, dict) else []
            for field in fields:
                if not isinstance(field, dict) or field.get("name") != "zoneRanking":
                    continue
                args = field.get("args", [])
                self._zone_ranking_args = {
                    str(arg.get("name"))
                    for arg in args
                    if isinstance(arg, dict) and arg.get("name")
                }
                return self._zone_ranking_args
        except WarcraftLogsRequestError:
            # Some GraphQL deployments disable introspection. Size is the only
            # optional argument needed by the current rankings command.
            pass

        self._zone_ranking_args = {"size"}
        return self._zone_ranking_args


def _extract_ranking_entries(value: Any) -> list[GuildRankingEntry]:
    candidates: list[GuildRankingEntry] = []
    seen: set[tuple[str, int | None, int | None, int | None]] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            entry = _ranking_entry_from_dict(node)
            if entry is not None:
                key = (
                    entry.encounter_name,
                    entry.world_rank,
                    entry.region_rank,
                    entry.server_rank,
                )
                if key not in seen:
                    seen.add(key)
                    candidates.append(entry)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return candidates


def _ranking_entry_from_dict(data: dict[str, Any]) -> GuildRankingEntry | None:
    encounter_name = _extract_name(data)
    if not encounter_name:
        return None

    world_rank = _first_int(data, "worldRank", "world_rank", "rank")
    region_rank = _first_int(data, "regionRank", "region_rank")
    server_rank = _first_int(data, "serverRank", "server_rank")
    rank_percent = _first_float(
        data,
        "rankPercent",
        "rankPercentage",
        "percentile",
        "bestPercent",
    )

    if all(value is None for value in (world_rank, region_rank, server_rank, rank_percent)):
        return None

    return GuildRankingEntry(
        encounter_name=encounter_name,
        world_rank=world_rank,
        region_rank=region_rank,
        server_rank=server_rank,
        rank_percent=rank_percent,
    )


def _extract_name(data: dict[str, Any]) -> str | None:
    encounter = data.get("encounter")
    if isinstance(encounter, dict) and encounter.get("name"):
        return str(encounter["name"])

    for key in ("encounterName", "encounter_name", "name"):
        value = data.get(key)
        if value and isinstance(value, str):
            return value
    return None


def _first_int(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_float(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _find_zone_name(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("zoneName", "zone_name"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        zone = value.get("zone")
        if isinstance(zone, dict) and isinstance(zone.get("name"), str):
            return str(zone["name"])
        for child in value.values():
            found = _find_zone_name(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_zone_name(child)
            if found:
                return found
    return None
