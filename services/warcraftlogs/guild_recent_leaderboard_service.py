from __future__ import annotations

import time
from dataclasses import dataclass

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceService,
    WarcraftLogsPlayerSummary,
    aggregate_player_performance,
)
from services.warcraftlogs.report_summary_service import WarcraftLogsReportSummaryService
from services.warcraftlogs.reports_service import WarcraftLogsReport, WarcraftLogsReportsService

CACHE_TTL_SECONDS = 600
REPORT_WINDOW_DAYS = 21
REPORT_LIMIT = 20


@dataclass(frozen=True)
class GuildRecentLeaderboardResult:
    guild_id: int
    guild_name: str
    difficulty: int
    damage_players: tuple[WarcraftLogsPlayerSummary, ...]
    healing_players: tuple[WarcraftLogsPlayerSummary, ...]
    reports: tuple[WarcraftLogsReport, ...]
    latest_report_code: str | None
    latest_report_title: str | None
    fetched_at: float
    raid_team_filtered: bool = False

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
    """Build a three-week leaderboard from public report data.

    Only boss kills for the selected difficulty are included. Each character's
    best parse per boss is retained before the final average is calculated.
    When registered raid-team character names are supplied, all other log
    characters are excluded.
    """

    def __init__(
        self,
        reports_service: WarcraftLogsReportsService,
        summary_service: WarcraftLogsReportSummaryService,
        performance_service: WarcraftLogsPlayerPerformanceService,
    ) -> None:
        self.reports_service = reports_service
        self.summary_service = summary_service
        self.performance_service = performance_service
        self._cache: dict[tuple[int, int, bool, tuple[str, ...]], _CacheEntry] = {}

    async def get_leaderboard(
        self,
        guild_id: int,
        *,
        difficulty: int = 4,
        allowed_character_names: set[str] | frozenset[str] | None = None,
        force_refresh: bool = False,
    ) -> GuildRecentLeaderboardResult:
        clean_guild_id = int(guild_id)
        clean_difficulty = int(difficulty)
        if clean_guild_id <= 0:
            raise ValueError("Warcraft Logs guild ID must be positive.")
        if clean_difficulty not in (3, 4):
            raise ValueError("Difficulty must be 3 (Normal) or 4 (Heroic).")

        filter_enabled = allowed_character_names is not None
        allowed = frozenset(
            _normalize_character_name(value)
            for value in (allowed_character_names or ())
            if _normalize_character_name(value)
        )
        cache_key = (
            clean_guild_id,
            clean_difficulty,
            filter_enabled,
            tuple(sorted(allowed)),
        )
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and now < cached.expires_at:
            return cached.result

        report_result = await self.reports_service.get_recent_reports(
            clean_guild_id,
            limit=REPORT_LIMIT,
            force_refresh=force_refresh,
        )
        reports = _filter_report_window(report_result.reports)
        latest_zone = reports[0].zone_name if reports else None
        reports = tuple(
            report for report in reports if not latest_zone or report.zone_name == latest_zone
        )

        best_rows: dict[tuple[str, str, str, str], WarcraftLogsPlayerPerformance] = {}
        included_reports: list[WarcraftLogsReport] = []

        for report in reports:
            summary = await self.summary_service.get_report_summary(
                report.code,
                force_refresh=force_refresh,
            )
            killed_encounters = {
                fight.label.encounter_name.casefold()
                for fight in summary.boss_fights
                if fight.kill
                and _difficulty_value(fight.raw_difficulty) == clean_difficulty
                and fight.label.encounter_name
            }
            if not killed_encounters:
                continue

            performance = await self.performance_service.get_report_player_performance(
                report.code,
                force_refresh=force_refresh,
            )
            matched_any = False
            for row in performance.players:
                if filter_enabled and _normalize_character_name(row.name) not in allowed:
                    continue
                encounter = str(row.encounter_name or "").strip()
                if not encounter or encounter.casefold() not in killed_encounters:
                    continue
                if row.rank_percent is None:
                    continue
                matched_any = True
                key = (
                    row.name.casefold(),
                    (row.server or "").casefold(),
                    (row.spec_name or "").casefold(),
                    encounter.casefold(),
                )
                current = best_rows.get(key)
                if current is None or (row.rank_percent or 0) > (current.rank_percent or 0):
                    best_rows[key] = row
            if matched_any:
                included_reports.append(report)

        summaries = aggregate_player_performance(best_rows.values())
        damage_players = tuple(
            sorted(
                (player for player in summaries if player.role_category != "Healer"),
                key=_average_sort_key,
            )
        )
        healing_players = tuple(
            sorted(
                (player for player in summaries if player.role_category == "Healer"),
                key=_average_sort_key,
            )
        )

        latest = included_reports[0] if included_reports else None
        result = GuildRecentLeaderboardResult(
            guild_id=clean_guild_id,
            guild_name=f"Guild {clean_guild_id}",
            difficulty=clean_difficulty,
            damage_players=damage_players,
            healing_players=healing_players,
            reports=tuple(included_reports),
            latest_report_code=latest.code if latest else None,
            latest_report_title=latest.title if latest else None,
            fetched_at=time.time(),
            raid_team_filtered=filter_enabled,
        )
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=now + CACHE_TTL_SECONDS,
        )
        return result


def _filter_report_window(
    reports: tuple[WarcraftLogsReport, ...],
) -> tuple[WarcraftLogsReport, ...]:
    if not reports:
        return ()
    newest_ms = max(report.start_time for report in reports)
    cutoff_ms = newest_ms - REPORT_WINDOW_DAYS * 24 * 60 * 60 * 1000
    return tuple(report for report in reports if report.start_time >= cutoff_ms)


def _normalize_character_name(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _difficulty_value(raw: object) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _average_sort_key(player: WarcraftLogsPlayerSummary) -> tuple[bool, float, str]:
    return (
        player.average_parse is None,
        -(player.average_parse or 0),
        player.name.casefold(),
    )
