from __future__ import annotations

import time
from dataclasses import dataclass

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceService,
    WarcraftLogsPlayerSummary,
)
from services.warcraftlogs.reports_service import WarcraftLogsReportsService


RECENT_RANKINGS_CACHE_TTL_SECONDS = 600


@dataclass(frozen=True)
class RecentGuildRankingEntry:
    name: str
    server: str | None
    class_name: str | None
    spec_name: str | None
    role_category: str
    best_parse: float | None
    best_amount: float | None
    ranked_fights: int
    report_count: int


@dataclass(frozen=True)
class RecentGuildRankingsResult:
    guild_id: int
    entries: tuple[RecentGuildRankingEntry, ...]
    latest_report_code: str | None
    latest_report_title: str | None
    report_codes: tuple[str, ...]
    fetched_at: float


@dataclass
class _CacheEntry:
    result: RecentGuildRankingsResult
    expires_at: float


class WarcraftLogsRecentGuildRankingsService:
    """Aggregate best player parses across recent guild reports."""

    def __init__(
        self,
        reports_service: WarcraftLogsReportsService,
        performance_service: WarcraftLogsPlayerPerformanceService,
    ) -> None:
        self.reports_service = reports_service
        self.performance_service = performance_service
        self._cache: dict[tuple[int, int], _CacheEntry] = {}

    async def get_recent_rankings(
        self,
        guild_id: int,
        *,
        report_limit: int = 10,
        force_refresh: bool = False,
    ) -> RecentGuildRankingsResult:
        clean_guild_id = int(guild_id)
        clean_limit = max(1, min(int(report_limit), 20))
        cache_key = (clean_guild_id, clean_limit)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        reports_result = await self.reports_service.get_recent_reports(
            clean_guild_id,
            limit=clean_limit,
            force_refresh=force_refresh,
        )
        reports = reports_result.reports
        grouped: dict[tuple[str, str, str], dict[str, object]] = {}

        for report in reports:
            performance = await self.performance_service.get_report_player_performance(
                report.code,
                force_refresh=force_refresh,
            )
            for summary in performance.player_summaries:
                key = (
                    summary.name.casefold(),
                    (summary.server or "").casefold(),
                    (summary.primary_spec or "").casefold(),
                )
                state = grouped.setdefault(
                    key,
                    {
                        "summary": summary,
                        "best_parse": None,
                        "best_amount": None,
                        "ranked_fights": 0,
                        "reports": set(),
                    },
                )
                state["summary"] = _prefer_identity(state["summary"], summary)
                state["best_parse"] = _max_optional(state["best_parse"], summary.best_parse)
                state["best_amount"] = _max_optional(state["best_amount"], summary.best_amount)
                state["ranked_fights"] = int(state["ranked_fights"]) + summary.parse_count
                cast_reports = state["reports"]
                if isinstance(cast_reports, set):
                    cast_reports.add(report.code)

        entries: list[RecentGuildRankingEntry] = []
        for state in grouped.values():
            summary = state["summary"]
            if not isinstance(summary, WarcraftLogsPlayerSummary):
                continue
            reports_seen = state["reports"] if isinstance(state["reports"], set) else set()
            entries.append(
                RecentGuildRankingEntry(
                    name=summary.name,
                    server=summary.server,
                    class_name=summary.class_name,
                    spec_name=summary.primary_spec,
                    role_category=summary.role_category,
                    best_parse=_as_float(state["best_parse"]),
                    best_amount=_as_float(state["best_amount"]),
                    ranked_fights=int(state["ranked_fights"]),
                    report_count=len(reports_seen),
                )
            )

        entries.sort(
            key=lambda entry: (
                {"Tank": 0, "Healer": 1, "DPS": 2}.get(entry.role_category, 3),
                entry.best_parse is None,
                -(entry.best_parse or 0),
                entry.name.casefold(),
            )
        )
        result = RecentGuildRankingsResult(
            guild_id=clean_guild_id,
            entries=tuple(entries),
            latest_report_code=reports[0].code if reports else None,
            latest_report_title=reports[0].title if reports else None,
            report_codes=tuple(report.code for report in reports),
            fetched_at=time.time(),
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + RECENT_RANKINGS_CACHE_TTL_SECONDS,
        )
        return result


def _prefer_identity(
    current: object,
    candidate: WarcraftLogsPlayerSummary,
) -> WarcraftLogsPlayerSummary:
    if not isinstance(current, WarcraftLogsPlayerSummary):
        return candidate
    if current.server is None and candidate.server is not None:
        return candidate
    return current


def _max_optional(current: object, candidate: float | None) -> float | None:
    current_value = _as_float(current)
    if candidate is None:
        return current_value
    if current_value is None:
        return float(candidate)
    return max(current_value, float(candidate))


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
