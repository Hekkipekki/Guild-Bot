from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError


PLAYER_PERFORMANCE_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class WarcraftLogsPlayerPerformance:
    name: str
    server: str | None
    class_name: str | None
    spec_name: str | None
    role: str | None
    amount: float | None
    rank_percent: float | None
    item_level: float | None
    encounter_name: str | None


@dataclass(frozen=True)
class WarcraftLogsPlayerPerformanceResult:
    report_code: str
    report_title: str
    players: tuple[WarcraftLogsPlayerPerformance, ...]
    raw_rankings: Any
    fetched_at: float

    @property
    def url(self) -> str:
        return f"https://classic.warcraftlogs.com/reports/{self.report_code}"


@dataclass
class _CacheEntry:
    result: WarcraftLogsPlayerPerformanceResult
    expires_at: float


class WarcraftLogsPlayerPerformanceService:
    """Fetch and normalize the report-level rankings payload.

    Warcraft Logs exposes report rankings as a JSON scalar whose exact nested
    shape can differ between game versions and report views. The parser keeps
    the raw payload and conservatively extracts rows that contain a character
    name plus at least one performance value.
    """

    _REPORT_RANKINGS_QUERY = """
    query ReportPlayerPerformance($code: String!) {
      reportData {
        report(code: $code) {
          code
          title
          rankings
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[str, _CacheEntry] = {}

    async def get_report_player_performance(
        self,
        report_code: str,
        *,
        force_refresh: bool = False,
    ) -> WarcraftLogsPlayerPerformanceResult:
        code = str(report_code or "").strip()
        if not code:
            raise ValueError("A Warcraft Logs report code is required.")

        now = time.monotonic()
        cached = self._cache.get(code)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        data = await self.client.query(self._REPORT_RANKINGS_QUERY, {"code": code})
        report = data.get("reportData", {}).get("report")
        if not isinstance(report, dict):
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned no report data for that report code."
            )

        returned_code = str(report.get("code") or code).strip()
        raw_rankings = report.get("rankings")
        result = WarcraftLogsPlayerPerformanceResult(
            report_code=returned_code,
            report_title=str(report.get("title") or "Untitled report").strip()
            or "Untitled report",
            players=parse_player_performance_rows(raw_rankings),
            raw_rankings=raw_rankings,
            fetched_at=time.time(),
        )
        self._cache[code] = _CacheEntry(
            result=result,
            expires_at=now + PLAYER_PERFORMANCE_CACHE_TTL_SECONDS,
        )
        return result


def parse_player_performance_rows(payload: Any) -> tuple[WarcraftLogsPlayerPerformance, ...]:
    rows: list[WarcraftLogsPlayerPerformance] = []
    seen: set[tuple[str, str | None, str | None, float | None]] = set()

    for candidate in _walk_dicts(payload):
        parsed = _parse_candidate(candidate)
        if parsed is None:
            continue
        key = (parsed.name.lower(), parsed.spec_name, parsed.encounter_name, parsed.rank_percent)
        if key in seen:
            continue
        seen.add(key)
        rows.append(parsed)

    rows.sort(
        key=lambda row: (
            row.rank_percent is None,
            -(row.rank_percent or 0),
            row.name.lower(),
        )
    )
    return tuple(rows)


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _parse_candidate(data: dict[str, Any]) -> WarcraftLogsPlayerPerformance | None:
    name = _first_text(data, "name", "characterName", "playerName")
    if not name:
        return None

    rank_percent = _first_number(
        data,
        "rankPercent",
        "rankPercentage",
        "percentile",
        "historicalPercent",
        "todayPercent",
    )
    amount = _first_number(data, "amount", "total", "dps", "hps", "score")
    item_level = _first_number(data, "itemLevel", "ilvl", "averageItemLevel")

    # Avoid treating arbitrary metadata objects as player rows.
    if rank_percent is None and amount is None and item_level is None:
        return None

    return WarcraftLogsPlayerPerformance(
        name=name,
        server=_first_text(data, "server", "serverName"),
        class_name=_first_text(data, "class", "className", "type"),
        spec_name=_first_text(data, "spec", "specName", "specialization"),
        role=_first_text(data, "role"),
        amount=amount,
        rank_percent=rank_percent,
        item_level=item_level,
        encounter_name=_first_text(data, "encounter", "encounterName", "bossName"),
    )


def _first_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested_name = value.get("name")
            if isinstance(nested_name, str) and nested_name.strip():
                return nested_name.strip()
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
