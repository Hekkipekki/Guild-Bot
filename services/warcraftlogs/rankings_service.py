from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import (
    WarcraftLogsClient,
    WarcraftLogsRequestError,
)


CACHE_TTL_SECONDS = 600
_BOSS_ARGUMENT_NAMES = ("encounterID", "bossID", "boss")
_RECENT_ARGUMENT_NAMES = ("recent", "includeRecent", "recentRaiders")


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
    boss_id: int | None = None
    recent: bool = False


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

    _ZONE_RANKING_TYPE_QUERY = """
    query GuildZoneRankingSchema {
      __type(name: "GuildZoneRankings") {
        fields {
          name
          type {
            kind
            name
            ofType {
              kind
              name
              ofType { kind name }
            }
          }
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[tuple[int, int, int | None, bool], _CacheEntry] = {}
        self._zone_ranking_args: set[str] | None = None
        self._zone_ranking_selection: str | None = None

    async def get_guild_rankings(
        self,
        guild_id: int,
        *,
        raid_size: int = 10,
        boss_id: int | None = None,
        recent: bool = False,
        force_refresh: bool = False,
    ) -> GuildRankingsResult:
        clean_guild_id = int(guild_id)
        clean_raid_size = int(raid_size)
        clean_boss_id = int(boss_id) if boss_id is not None else None

        if clean_guild_id <= 0:
            raise ValueError("Warcraft Logs guild ID must be positive.")
        if clean_raid_size not in (10, 25):
            raise ValueError("Raid size must be 10 or 25.")
        if clean_boss_id is not None and clean_boss_id <= 0:
            raise ValueError("Boss ID must be a positive integer.")

        cache_key = (clean_guild_id, clean_raid_size, clean_boss_id, bool(recent))
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        supported_args = await self._get_zone_ranking_args()
        selection = await self._get_zone_ranking_selection()
        argument_parts: list[str] = []

        if "size" in supported_args:
            argument_parts.append(f"size: {clean_raid_size}")

        if clean_boss_id is not None:
            boss_argument = _first_supported_argument(
                supported_args,
                _BOSS_ARGUMENT_NAMES,
            )
            if boss_argument is None:
                raise WarcraftLogsRequestError(
                    "The current Warcraft Logs zoneRanking schema does not expose "
                    "a boss/encounter filter. Supported arguments: "
                    f"{', '.join(sorted(supported_args)) or 'none'}."
                )
            argument_parts.append(f"{boss_argument}: {clean_boss_id}")

        if recent:
            recent_argument = _first_supported_argument(
                supported_args,
                _RECENT_ARGUMENT_NAMES,
            )
            if recent_argument is None:
                raise WarcraftLogsRequestError(
                    "The current Warcraft Logs zoneRanking schema does not expose "
                    "a recent-raiders filter. Supported arguments: "
                    f"{', '.join(sorted(supported_args)) or 'none'}."
                )
            argument_parts.append(f"{recent_argument}: true")

        arguments = f"({', '.join(argument_parts)})" if argument_parts else ""
        query = f"""
        query GuildRankings {{
          guildData {{
            guild(id: {clean_guild_id}) {{
              id
              name
              zoneRankings: zoneRanking{arguments} {{
                {selection}
              }}
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
            boss_id=clean_boss_id,
            recent=bool(recent),
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
            pass

        self._zone_ranking_args = {"size"}
        return self._zone_ranking_args

    async def _get_zone_ranking_selection(self) -> str:
        if self._zone_ranking_selection is not None:
            return self._zone_ranking_selection

        data = await self.client.query(self._ZONE_RANKING_TYPE_QUERY)
        type_block = data.get("__type")
        fields = type_block.get("fields", []) if isinstance(type_block, dict) else []

        selections: list[str] = []
        available_names: list[str] = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            available_names.append(name)
            kind, _ = _unwrap_graphql_type(field.get("type"))
            if kind in {"SCALAR", "ENUM"}:
                selections.append(name)
            elif name == "zone" and kind == "OBJECT":
                selections.append("zone { name }")

        if not selections:
            names = ", ".join(sorted(available_names)) or "none"
            raise WarcraftLogsRequestError(
                "Warcraft Logs exposed no selectable scalar fields on "
                f"GuildZoneRankings. Available fields: {names}."
            )

        self._zone_ranking_selection = "\n".join(selections)
        return self._zone_ranking_selection


def _first_supported_argument(
    supported: set[str],
    candidates: tuple[str, ...],
) -> str | None:
    return next((name for name in candidates if name in supported), None)


def _unwrap_graphql_type(type_block: Any) -> tuple[str | None, str | None]:
    current = type_block
    while isinstance(current, dict):
        kind = current.get("kind")
        name = current.get("name")
        if kind not in {"NON_NULL", "LIST"}:
            return (
                str(kind) if kind else None,
                str(name) if name else None,
            )
        current = current.get("ofType")
    return None, None


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
