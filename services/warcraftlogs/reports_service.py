from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError


REPORTS_CACHE_TTL_SECONDS = 300
REPORTS_LIMIT_MIN = 1
REPORTS_LIMIT_MAX = 20


@dataclass(frozen=True)
class WarcraftLogsReport:
    code: str
    title: str
    start_time: float
    end_time: float | None
    owner_name: str | None
    zone_name: str | None

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None or self.end_time < self.start_time:
            return None
        return self.end_time - self.start_time

    @property
    def url(self) -> str:
        return f"https://classic.warcraftlogs.com/reports/{self.code}"


@dataclass(frozen=True)
class WarcraftLogsReportsResult:
    guild_id: int
    reports: tuple[WarcraftLogsReport, ...]
    raw_response: Any
    fetched_at: float


@dataclass
class _CacheEntry:
    result: WarcraftLogsReportsResult
    expires_at: float


class WarcraftLogsReportsService:
    """Fetch recent reports for a configured Warcraft Logs guild."""

    _REPORTS_QUERY = """
    query GuildRecentReports($guildID: Int!, $limit: Int!) {
      reportData {
        reports(guildID: $guildID, limit: $limit) {
          data {
            code
            title
            startTime
            endTime
            owner { name }
            zone { name }
          }
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[tuple[int, int], _CacheEntry] = {}

    async def get_recent_reports(
        self,
        guild_id: int,
        *,
        limit: int = 5,
        force_refresh: bool = False,
    ) -> WarcraftLogsReportsResult:
        clean_guild_id = int(guild_id)
        clean_limit = int(limit)
        if clean_guild_id <= 0:
            raise ValueError("Warcraft Logs guild ID must be positive.")
        if not REPORTS_LIMIT_MIN <= clean_limit <= REPORTS_LIMIT_MAX:
            raise ValueError(
                f"Report limit must be between {REPORTS_LIMIT_MIN} and {REPORTS_LIMIT_MAX}."
            )

        cache_key = (clean_guild_id, clean_limit)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        data = await self.client.query(
            self._REPORTS_QUERY,
            {"guildID": clean_guild_id, "limit": clean_limit},
        )
        reports_block = data.get("reportData", {}).get("reports")
        if not isinstance(reports_block, dict):
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned no report pagination data for this guild."
            )

        raw_reports = reports_block.get("data")
        if raw_reports is None:
            raw_reports = []
        if not isinstance(raw_reports, list):
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned an unexpected reports response shape."
            )

        reports = tuple(
            report
            for item in raw_reports
            if isinstance(item, dict)
            for report in [_parse_report(item)]
            if report is not None
        )
        result = WarcraftLogsReportsResult(
            guild_id=clean_guild_id,
            reports=reports,
            raw_response=reports_block,
            fetched_at=time.time(),
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + REPORTS_CACHE_TTL_SECONDS,
        )
        return result


def _parse_report(data: dict[str, Any]) -> WarcraftLogsReport | None:
    code = str(data.get("code") or "").strip()
    if not code:
        return None

    try:
        start_time = float(data.get("startTime"))
    except (TypeError, ValueError):
        return None

    end_time: float | None
    try:
        raw_end = data.get("endTime")
        end_time = float(raw_end) if raw_end is not None else None
    except (TypeError, ValueError):
        end_time = None

    owner = data.get("owner")
    zone = data.get("zone")
    owner_name = (
        str(owner.get("name")).strip()
        if isinstance(owner, dict) and owner.get("name")
        else None
    )
    zone_name = (
        str(zone.get("name")).strip()
        if isinstance(zone, dict) and zone.get("name")
        else None
    )

    return WarcraftLogsReport(
        code=code,
        title=str(data.get("title") or "Untitled report").strip() or "Untitled report",
        start_time=start_time,
        end_time=end_time,
        owner_name=owner_name,
        zone_name=zone_name,
    )
