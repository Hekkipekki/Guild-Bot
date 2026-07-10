from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from services.warcraftlogs.api_client import WarcraftLogsClient, WarcraftLogsRequestError
from services.warcraftlogs.encounter_label_parser import EncounterLabel, parse_encounter_label


REPORT_SUMMARY_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class WarcraftLogsFight:
    id: int
    encounter_id: int | None
    label: EncounterLabel
    kill: bool
    start_time: float
    end_time: float
    raw_difficulty: Any = None
    boss_percentage: float | None = None

    @property
    def duration_ms(self) -> float:
        return max(self.end_time - self.start_time, 0)


@dataclass(frozen=True)
class WarcraftLogsEncounterSummary:
    encounter_id: int | None
    label: EncounterLabel
    kills: int
    wipes: int
    fastest_kill_ms: float | None
    best_wipe_percentage: float | None


@dataclass(frozen=True)
class WarcraftLogsReportSummary:
    code: str
    title: str
    start_time: float
    end_time: float | None
    owner_name: str | None
    zone_name: str | None
    fights: tuple[WarcraftLogsFight, ...]
    encounters: tuple[WarcraftLogsEncounterSummary, ...]
    raw_response: Any
    fetched_at: float

    @property
    def url(self) -> str:
        return f"https://classic.warcraftlogs.com/reports/{self.code}"

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None or self.end_time < self.start_time:
            return None
        return self.end_time - self.start_time

    @property
    def boss_fights(self) -> tuple[WarcraftLogsFight, ...]:
        return tuple(fight for fight in self.fights if fight.encounter_id)

    @property
    def total_kills(self) -> int:
        return sum(1 for fight in self.boss_fights if fight.kill)

    @property
    def total_wipes(self) -> int:
        return sum(1 for fight in self.boss_fights if not fight.kill)


@dataclass
class _CacheEntry:
    result: WarcraftLogsReportSummary
    expires_at: float


class WarcraftLogsReportSummaryService:
    """Fetch and normalize fights for one Warcraft Logs report."""

    _REPORT_QUERY = """
    query ReportSummary($code: String!) {
      reportData {
        report(code: $code) {
          code
          title
          startTime
          endTime
          owner { name }
          zone { name }
          fights {
            id
            encounterID
            name
            difficulty
            kill
            startTime
            endTime
            bossPercentage
          }
        }
      }
    }
    """

    def __init__(self, client: WarcraftLogsClient) -> None:
        self.client = client
        self._cache: dict[str, _CacheEntry] = {}

    async def get_report_summary(
        self,
        report_code: str,
        *,
        force_refresh: bool = False,
    ) -> WarcraftLogsReportSummary:
        code = str(report_code or "").strip()
        if not code:
            raise ValueError("A Warcraft Logs report code is required.")

        now = time.monotonic()
        cached = self._cache.get(code)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        data = await self.client.query(self._REPORT_QUERY, {"code": code})
        report = data.get("reportData", {}).get("report")
        if not isinstance(report, dict):
            raise WarcraftLogsRequestError(
                "Warcraft Logs returned no report data for that report code."
            )

        result = _parse_report_summary(report)
        self._cache[code] = _CacheEntry(
            result=result,
            expires_at=now + REPORT_SUMMARY_CACHE_TTL_SECONDS,
        )
        return result


def _parse_report_summary(data: dict[str, Any]) -> WarcraftLogsReportSummary:
    code = str(data.get("code") or "").strip()
    if not code:
        raise WarcraftLogsRequestError("Warcraft Logs report data did not include a code.")

    try:
        start_time = float(data.get("startTime"))
    except (TypeError, ValueError) as exc:
        raise WarcraftLogsRequestError(
            "Warcraft Logs report data did not include a valid start time."
        ) from exc

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

    raw_fights = data.get("fights")
    if raw_fights is None:
        raw_fights = []
    if not isinstance(raw_fights, list):
        raise WarcraftLogsRequestError(
            "Warcraft Logs returned an unexpected fights response shape."
        )

    fights = tuple(
        fight
        for item in raw_fights
        if isinstance(item, dict)
        for fight in [_parse_fight(item)]
        if fight is not None
    )

    return WarcraftLogsReportSummary(
        code=code,
        title=str(data.get("title") or "Untitled report").strip() or "Untitled report",
        start_time=start_time,
        end_time=end_time,
        owner_name=owner_name,
        zone_name=zone_name,
        fights=fights,
        encounters=_summarize_encounters(fights),
        raw_response=data,
        fetched_at=time.time(),
    )


def _parse_fight(data: dict[str, Any]) -> WarcraftLogsFight | None:
    try:
        fight_id = int(data.get("id"))
        start_time = float(data.get("startTime"))
        end_time = float(data.get("endTime"))
    except (TypeError, ValueError):
        return None

    encounter_id: int | None
    try:
        raw_encounter_id = data.get("encounterID")
        parsed_encounter_id = int(raw_encounter_id) if raw_encounter_id is not None else 0
        encounter_id = parsed_encounter_id or None
    except (TypeError, ValueError):
        encounter_id = None

    boss_percentage: float | None
    try:
        raw_percentage = data.get("bossPercentage")
        boss_percentage = float(raw_percentage) if raw_percentage is not None else None
    except (TypeError, ValueError):
        boss_percentage = None

    return WarcraftLogsFight(
        id=fight_id,
        encounter_id=encounter_id,
        label=parse_encounter_label(data.get("name")),
        kill=bool(data.get("kill")),
        start_time=start_time,
        end_time=end_time,
        raw_difficulty=data.get("difficulty"),
        boss_percentage=boss_percentage,
    )


def _summarize_encounters(
    fights: tuple[WarcraftLogsFight, ...],
) -> tuple[WarcraftLogsEncounterSummary, ...]:
    grouped: dict[tuple[int | None, str], list[WarcraftLogsFight]] = {}
    order: list[tuple[int | None, str]] = []

    for fight in fights:
        if not fight.encounter_id:
            continue
        key = (fight.encounter_id, fight.label.original_label)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(fight)

    summaries: list[WarcraftLogsEncounterSummary] = []
    for key in order:
        encounter_fights = grouped[key]
        kill_times = [fight.duration_ms for fight in encounter_fights if fight.kill]
        wipe_percentages = [
            fight.boss_percentage
            for fight in encounter_fights
            if not fight.kill and fight.boss_percentage is not None
        ]
        summaries.append(
            WarcraftLogsEncounterSummary(
                encounter_id=key[0],
                label=encounter_fights[0].label,
                kills=sum(1 for fight in encounter_fights if fight.kill),
                wipes=sum(1 for fight in encounter_fights if not fight.kill),
                fastest_kill_ms=min(kill_times) if kill_times else None,
                best_wipe_percentage=min(wipe_percentages) if wipe_percentages else None,
            )
        )

    return tuple(summaries)
