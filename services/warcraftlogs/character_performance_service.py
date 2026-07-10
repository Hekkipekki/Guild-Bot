from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError

CHARACTER_CACHE_TTL_SECONDS = 600
_DIFFICULTIES = {"normal": 3, "heroic": 4}
_METRICS = {"damage": "dps", "healing": "hps"}


@dataclass(frozen=True)
class CharacterParseEntry:
    encounter_name: str
    spec_name: str | None
    rank_percent: float | None
    amount: float | None
    total_kills: int | None


@dataclass(frozen=True)
class CharacterPerformanceResult:
    character_name: str
    server_slug: str
    region: str
    normal_damage: tuple[CharacterParseEntry, ...]
    heroic_damage: tuple[CharacterParseEntry, ...]
    normal_healing: tuple[CharacterParseEntry, ...]
    heroic_healing: tuple[CharacterParseEntry, ...]
    raw_response: Any
    fetched_at: float

    def entries(self, difficulty: str, metric: str) -> tuple[CharacterParseEntry, ...]:
        clean_difficulty = difficulty.casefold()
        clean_metric = metric.casefold()
        mapping = {
            ("normal", "damage"): self.normal_damage,
            ("heroic", "damage"): self.heroic_damage,
            ("normal", "healing"): self.normal_healing,
            ("heroic", "healing"): self.heroic_healing,
        }
        return mapping.get((clean_difficulty, clean_metric), ())

    def url(self, difficulty: str, metric: str) -> str:
        difficulty_id = _DIFFICULTIES.get(difficulty.casefold(), 4)
        metric_value = _METRICS.get(metric.casefold(), "dps")
        metric_query = "" if metric_value == "dps" else f"&metric={metric_value}"
        return (
            "https://classic.warcraftlogs.com/character/"
            f"{self.region}/{self.server_slug}/{self.character_name.casefold()}"
            f"?difficulty={difficulty_id}&size=10{metric_query}"
        )


@dataclass
class _CacheEntry:
    result: CharacterPerformanceResult
    expires_at: float


class WarcraftLogsCharacterPerformanceService:
    """Fetch all-spec 10-player Normal/Heroic damage and healing rankings."""

    _QUERY = """
    query CharacterTopParses($name: String!, $serverSlug: String!, $serverRegion: String!) {
      characterData {
        character(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
          name
          normalDamage: zoneRankings(difficulty: 3, size: 10, metric: dps)
          heroicDamage: zoneRankings(difficulty: 4, size: 10, metric: dps)
          normalHealing: zoneRankings(difficulty: 3, size: 10, metric: hps)
          heroicHealing: zoneRankings(difficulty: 4, size: 10, metric: hps)
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[tuple[str, str, str], _CacheEntry] = {}

    async def get_character_performance(
        self,
        character_name: str,
        server_slug: str,
        region: str,
        *,
        force_refresh: bool = False,
    ) -> CharacterPerformanceResult:
        clean_name = str(character_name or "").strip()
        clean_server = _slugify(server_slug)
        clean_region = str(region or "").strip().casefold()
        if not clean_name:
            raise ValueError("A character name is required.")
        if not clean_server:
            raise ValueError("A Warcraft Logs server slug is required.")
        if not clean_region:
            raise ValueError("A Warcraft Logs region is required.")

        cache_key = (clean_region, clean_server, clean_name.casefold())
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        data = await self.client.query(
            self._QUERY,
            {
                "name": clean_name,
                "serverSlug": clean_server,
                "serverRegion": clean_region,
            },
        )
        character = data.get("characterData", {}).get("character")
        if not isinstance(character, dict):
            raise WarcraftLogsRequestError(
                f"Warcraft Logs could not find {clean_name} on {clean_server}-{clean_region}."
            )

        result = CharacterPerformanceResult(
            character_name=str(character.get("name") or clean_name),
            server_slug=clean_server,
            region=clean_region,
            normal_damage=parse_character_rankings(character.get("normalDamage")),
            heroic_damage=parse_character_rankings(character.get("heroicDamage")),
            normal_healing=parse_character_rankings(character.get("normalHealing")),
            heroic_healing=parse_character_rankings(character.get("heroicHealing")),
            raw_response=character,
            fetched_at=time.time(),
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + CHARACTER_CACHE_TTL_SECONDS,
        )
        return result


def parse_character_rankings(payload: Any) -> tuple[CharacterParseEntry, ...]:
    entries: list[CharacterParseEntry] = []
    seen: set[tuple[str, str | None, float | None, float | None]] = set()
    for candidate, encounter_context, spec_context in _walk(payload):
        entry = _parse_candidate(candidate, encounter_context, spec_context)
        if entry is None:
            continue
        key = (
            entry.encounter_name.casefold(),
            entry.spec_name.casefold() if entry.spec_name else None,
            entry.rank_percent,
            entry.amount,
        )
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)
    entries.sort(
        key=lambda item: (
            item.rank_percent is None,
            -(item.rank_percent or 0),
            item.encounter_name.casefold(),
            str(item.spec_name or "").casefold(),
        )
    )
    return tuple(entries)


def _walk(
    value: Any,
    encounter_context: str | None = None,
    spec_context: str | None = None,
) -> Iterable[tuple[dict[str, Any], str | None, str | None]]:
    if isinstance(value, dict):
        local_encounter = _encounter_name(value) or encounter_context
        local_spec = _first_text(value, "spec", "specName", "specialization") or spec_context
        yield value, encounter_context, spec_context
        for child in value.values():
            yield from _walk(child, local_encounter, local_spec)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, encounter_context, spec_context)


def _parse_candidate(
    data: dict[str, Any],
    encounter_context: str | None,
    spec_context: str | None,
) -> CharacterParseEntry | None:
    rank_percent = _first_number(
        data,
        "rankPercent",
        "rankPercentage",
        "percentile",
        "bestPercent",
        "historicalPercent",
    )
    amount = _first_number(data, "amount", "total", "dps", "hps", "bestAmount")
    if rank_percent is None and amount is None:
        return None
    encounter_name = _encounter_name(data) or encounter_context
    if not encounter_name:
        return None
    total_kills_value = _first_number(data, "totalKills", "kills")
    return CharacterParseEntry(
        encounter_name=encounter_name,
        spec_name=_first_text(data, "spec", "specName", "specialization") or spec_context,
        rank_percent=rank_percent,
        amount=amount,
        total_kills=int(total_kills_value) if total_kills_value is not None else None,
    )


def _encounter_name(data: dict[str, Any]) -> str | None:
    encounter = data.get("encounter")
    if isinstance(encounter, dict):
        value = encounter.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _first_text(data, "encounterName", "bossName")


def _first_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _first_number(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().casefold()).strip("-")
