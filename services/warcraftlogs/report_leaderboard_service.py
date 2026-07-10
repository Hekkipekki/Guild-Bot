from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError
from services.warcraftlogs.avoidable_damage_registry import (
    is_avoidable_damage,
    mechanics_for_boss,
    normalize_mechanic_name,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceService,
)
from services.warcraftlogs.report_summary_service import (
    WarcraftLogsFight,
    WarcraftLogsReportSummaryService,
)


REPORT_LEADERBOARD_CACHE_TTL_SECONDS = 300
MAX_EVENT_PAGES_PER_FIGHT = 50
EVENT_PAGE_LIMIT = 10_000


@dataclass(frozen=True)
class DpsLeaderboardEntry:
    name: str
    spec_name: str | None
    dps: float
    ranked_fights: int


@dataclass(frozen=True)
class DtpsLeaderboardEntry:
    name: str
    total_avoidable_damage: float
    dtps: float
    hit_count: int
    ability_damage: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ReportLeaderboardResult:
    report_code: str
    report_title: str
    metric: str
    dps_entries: tuple[DpsLeaderboardEntry, ...]
    dtps_entries: tuple[DtpsLeaderboardEntry, ...]
    covered_bosses: tuple[str, ...]
    excluded_bosses: tuple[str, ...]
    covered_duration_ms: float
    raw_event_pages: tuple[Any, ...]
    unmatched_abilities: tuple[str, ...]
    fetched_at: float

    @property
    def url(self) -> str:
        return f"https://classic.warcraftlogs.com/reports/{self.report_code}"


@dataclass
class _CacheEntry:
    result: ReportLeaderboardResult
    expires_at: float


class WarcraftLogsReportLeaderboardService:
    """Build report-level DPS and explicit avoidable-DTPS leaderboards."""

    _ACTORS_QUERY = """
    query ReportActors($code: String!) {
      reportData {
        report(code: $code) {
          masterData {
            actors { id name type subType }
          }
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self.performance_service = WarcraftLogsPlayerPerformanceService(client)
        self.summary_service = WarcraftLogsReportSummaryService(client)
        self._cache: dict[tuple[str, str], _CacheEntry] = {}

    async def get_leaderboard(
        self,
        report_code: str,
        metric: str,
        *,
        force_refresh: bool = False,
    ) -> ReportLeaderboardResult:
        code = str(report_code or "").strip()
        clean_metric = str(metric or "").strip().casefold()
        if not code:
            raise ValueError("A Warcraft Logs report code is required.")
        if clean_metric not in {"dps", "dtps"}:
            raise ValueError("Leaderboard metric must be DPS or DTPS.")

        cache_key = (code, clean_metric)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        if clean_metric == "dps":
            result = await self._build_dps(code, force_refresh=force_refresh)
        else:
            result = await self._build_dtps(code, force_refresh=force_refresh)

        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + REPORT_LEADERBOARD_CACHE_TTL_SECONDS,
        )
        return result

    async def _build_dps(
        self,
        code: str,
        *,
        force_refresh: bool,
    ) -> ReportLeaderboardResult:
        performance = await self.performance_service.get_report_player_performance(
            code,
            force_refresh=force_refresh,
        )
        entries = tuple(
            sorted(
                (
                    DpsLeaderboardEntry(
                        name=player.name,
                        spec_name=player.primary_spec,
                        dps=float(player.average_amount),
                        ranked_fights=player.encounter_count,
                    )
                    for player in performance.player_summaries
                    if player.role_category == "DPS" and player.average_amount is not None
                ),
                key=lambda entry: (-entry.dps, entry.name.casefold()),
            )
        )
        return ReportLeaderboardResult(
            report_code=performance.report_code,
            report_title=performance.report_title,
            metric="dps",
            dps_entries=entries,
            dtps_entries=(),
            covered_bosses=(),
            excluded_bosses=(),
            covered_duration_ms=0,
            raw_event_pages=(),
            unmatched_abilities=(),
            fetched_at=time.time(),
        )

    async def _build_dtps(
        self,
        code: str,
        *,
        force_refresh: bool,
    ) -> ReportLeaderboardResult:
        summary = await self.summary_service.get_report_summary(
            code,
            force_refresh=force_refresh,
        )
        actor_names, player_actor_ids = await self._get_actor_map(code)

        covered_fights: list[WarcraftLogsFight] = []
        excluded_bosses: list[str] = []
        for fight in summary.boss_fights:
            boss_name = fight.label.encounter_name
            if mechanics_for_boss(boss_name):
                covered_fights.append(fight)
            elif boss_name not in excluded_bosses:
                excluded_bosses.append(boss_name)

        damage_by_player: Counter[str] = Counter()
        hits_by_player: Counter[str] = Counter()
        abilities_by_player: dict[str, Counter[str]] = {}
        unmatched_abilities: set[str] = set()
        raw_pages: list[Any] = []

        for fight in covered_fights:
            boss_name = fight.label.encounter_name
            pages = await self._get_damage_taken_pages(code, fight)
            raw_pages.extend(pages)
            for page in pages:
                events = page.get("data", []) if isinstance(page, dict) else []
                if not isinstance(events, list):
                    continue
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    ability_name = _event_ability_name(event)
                    if not is_avoidable_damage(boss_name, ability_name):
                        if ability_name:
                            unmatched_abilities.add(ability_name)
                        continue
                    target_id = _optional_int(event.get("targetID"))
                    if target_id is not None and player_actor_ids and target_id not in player_actor_ids:
                        continue
                    target_name = _event_target_name(event) or actor_names.get(target_id)
                    if not target_name:
                        continue
                    amount = _event_damage_amount(event)
                    if amount <= 0:
                        continue
                    damage_by_player[target_name] += amount
                    hits_by_player[target_name] += 1
                    abilities_by_player.setdefault(target_name, Counter())[ability_name or "Unknown"] += amount

        covered_duration_ms = sum(fight.duration_ms for fight in covered_fights)
        duration_seconds = covered_duration_ms / 1000 if covered_duration_ms > 0 else 0
        entries = tuple(
            sorted(
                (
                    DtpsLeaderboardEntry(
                        name=name,
                        total_avoidable_damage=float(total),
                        dtps=float(total / duration_seconds) if duration_seconds else 0.0,
                        hit_count=int(hits_by_player[name]),
                        ability_damage=tuple(
                            sorted(
                                ((ability, float(amount)) for ability, amount in abilities_by_player.get(name, {}).items()),
                                key=lambda item: (-item[1], item[0].casefold()),
                            )
                        ),
                    )
                    for name, total in damage_by_player.items()
                ),
                key=lambda entry: (entry.dtps, entry.name.casefold()),
            )
        )

        covered_names: list[str] = []
        for fight in covered_fights:
            name = fight.label.encounter_name
            if name not in covered_names:
                covered_names.append(name)

        return ReportLeaderboardResult(
            report_code=summary.code,
            report_title=summary.title,
            metric="dtps",
            dps_entries=(),
            dtps_entries=entries,
            covered_bosses=tuple(covered_names),
            excluded_bosses=tuple(excluded_bosses),
            covered_duration_ms=covered_duration_ms,
            raw_event_pages=tuple(raw_pages),
            unmatched_abilities=tuple(sorted(unmatched_abilities, key=str.casefold)),
            fetched_at=time.time(),
        )

    async def _get_actor_map(self, code: str) -> tuple[dict[int, str], set[int]]:
        data = await self.client.query(self._ACTORS_QUERY, {"code": code})
        report = data.get("reportData", {}).get("report")
        master_data = report.get("masterData") if isinstance(report, dict) else None
        actors = master_data.get("actors", []) if isinstance(master_data, dict) else []
        names: dict[int, str] = {}
        player_ids: set[int] = set()
        if not isinstance(actors, list):
            return names, player_ids
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            actor_id = _optional_int(actor.get("id"))
            name = str(actor.get("name") or "").strip()
            if actor_id is None or not name:
                continue
            names[actor_id] = name
            if str(actor.get("type") or "").casefold() == "player":
                player_ids.add(actor_id)
        return names, player_ids

    async def _get_damage_taken_pages(
        self,
        code: str,
        fight: WarcraftLogsFight,
    ) -> tuple[dict[str, Any], ...]:
        pages: list[dict[str, Any]] = []
        page_start = fight.start_time
        for _ in range(MAX_EVENT_PAGES_PER_FIGHT):
            query = _build_damage_taken_query(
                start_time=page_start,
                end_time=fight.end_time,
            )
            data = await self.client.query(query, {"code": code})
            report = data.get("reportData", {}).get("report")
            events = report.get("events") if isinstance(report, dict) else None
            if not isinstance(events, dict):
                raise WarcraftLogsRequestError(
                    "Warcraft Logs returned an unexpected DamageTaken events payload."
                )
            pages.append(events)
            next_page = _optional_float(events.get("nextPageTimestamp"))
            if next_page is None or next_page <= page_start or next_page >= fight.end_time:
                break
            page_start = next_page
        return tuple(pages)


def _build_damage_taken_query(*, start_time: float, end_time: float) -> str:
    return f"""
    query ReportAvoidableDamage($code: String!) {{
      reportData {{
        report(code: $code) {{
          events(
            startTime: {float(start_time):.3f}
            endTime: {float(end_time):.3f}
            dataType: DamageTaken
            limit: {EVENT_PAGE_LIMIT}
          ) {{
            data
            nextPageTimestamp
          }}
        }}
      }}
    }}
    """


def _event_ability_name(event: dict[str, Any]) -> str | None:
    ability = event.get("ability")
    if isinstance(ability, dict):
        name = str(ability.get("name") or "").strip()
        if name:
            return name
    for key in ("abilityName", "spellName"):
        value = str(event.get(key) or "").strip()
        if value:
            return value
    return None


def _event_target_name(event: dict[str, Any]) -> str | None:
    target = event.get("target")
    if isinstance(target, dict):
        name = str(target.get("name") or "").strip()
        if name:
            return name
    value = str(event.get("targetName") or "").strip()
    return value or None


def _event_damage_amount(event: dict[str, Any]) -> float:
    amount = _optional_float(event.get("amount")) or 0.0
    overkill = _optional_float(event.get("overkill")) or 0.0
    return max(amount - max(overkill, 0.0), 0.0)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None
