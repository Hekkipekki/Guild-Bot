import unittest

from services.warcraftlogs.encounter_label_parser import parse_encounter_label
from services.warcraftlogs.guild_recent_leaderboard_service import (
    WarcraftLogsGuildRecentLeaderboardService,
    _filter_report_window,
)
from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceResult,
    aggregate_player_performance,
)
from services.warcraftlogs.report_summary_service import (
    WarcraftLogsFight,
    WarcraftLogsReportSummary,
)
from services.warcraftlogs.reports_service import (
    WarcraftLogsReport,
    WarcraftLogsReportsResult,
)


class FakeReportsService:
    async def get_recent_reports(self, guild_id, *, limit, force_refresh=False):
        reports = (
            WarcraftLogsReport("NEW", "Heroic New", 2_000_000, 2_100_000, None, "SoO"),
            WarcraftLogsReport("OLD", "Heroic Old", 1_000_000, 1_100_000, None, "SoO"),
            WarcraftLogsReport("NORMAL", "Normal", 900_000, 950_000, None, "SoO"),
        )
        return WarcraftLogsReportsResult(guild_id, reports, {}, 0)


class FakeSummaryService:
    async def get_report_summary(self, code, *, force_refresh=False):
        difficulty = 3 if code == "NORMAL" else 4
        encounters = ["Immerseus", "Norushen"] if code != "NORMAL" else ["Immerseus"]
        fights = tuple(
            WarcraftLogsFight(
                id=index,
                encounter_id=index,
                label=parse_encounter_label(f"{name} {'Heroic' if difficulty == 4 else 'Normal'} (10 Player)"),
                kill=True,
                start_time=0,
                end_time=1000,
                raw_difficulty=difficulty,
            )
            for index, name in enumerate(encounters, start=1)
        )
        return WarcraftLogsReportSummary(
            code=code,
            title=code,
            start_time=0,
            end_time=1000,
            owner_name=None,
            zone_name="SoO",
            fights=fights,
            encounters=(),
            raw_response={},
            fetched_at=0,
        )


class FakePerformanceService:
    async def get_report_player_performance(self, code, *, force_refresh=False):
        if code == "NEW":
            rows = (
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 100, 80, 570, "Immerseus"
                ),
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 100, 70, 570, "Norushen"
                ),
                WarcraftLogsPlayerPerformance(
                    "Healz", "Realm", "Priest", "Discipline", "Healer", 100, 88, 570, "Immerseus"
                ),
            )
        elif code == "OLD":
            rows = (
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 100, 95, 568, "Immerseus"
                ),
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 100, 60, 568, "Norushen"
                ),
            )
        else:
            rows = (
                WarcraftLogsPlayerPerformance(
                    "Normalguy", "Realm", "Mage", "Arcane", "DPS", 100, 90, 560, "Immerseus"
                ),
            )
        return WarcraftLogsPlayerPerformanceResult(
            report_code=code,
            report_title=code,
            players=rows,
            player_summaries=aggregate_player_performance(rows),
            raw_rankings={},
            fetched_at=0,
        )


class GuildRecentLeaderboardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_keeps_best_parse_per_boss_and_averages_them(self):
        service = WarcraftLogsGuildRecentLeaderboardService(
            FakeReportsService(),
            FakeSummaryService(),
            FakePerformanceService(),
        )

        result = await service.get_leaderboard(800007, difficulty=4)

        self.assertEqual(result.latest_report_code, "NEW")
        self.assertEqual([report.code for report in result.reports], ["NEW", "OLD"])
        alpha = next(player for player in result.damage_players if player.name == "Alpha")
        self.assertEqual(alpha.average_parse, 82.5)
        self.assertEqual(alpha.encounter_count, 2)
        self.assertEqual([player.name for player in result.healing_players], ["Healz"])
        self.assertFalse(result.raid_team_filtered)

    async def test_filters_reports_by_normal_difficulty(self):
        service = WarcraftLogsGuildRecentLeaderboardService(
            FakeReportsService(),
            FakeSummaryService(),
            FakePerformanceService(),
        )

        result = await service.get_leaderboard(800007, difficulty=3)

        self.assertEqual([report.code for report in result.reports], ["NORMAL"])
        self.assertEqual([player.name for player in result.damage_players], ["Normalguy"])

    async def test_filters_players_to_registered_raid_team_characters(self):
        service = WarcraftLogsGuildRecentLeaderboardService(
            FakeReportsService(),
            FakeSummaryService(),
            FakePerformanceService(),
        )

        result = await service.get_leaderboard(
            800007,
            difficulty=4,
            allowed_character_names={"Alpha"},
        )

        self.assertEqual([player.name for player in result.damage_players], ["Alpha"])
        self.assertEqual(result.healing_players, ())
        self.assertTrue(result.raid_team_filtered)

    async def test_configured_empty_raid_team_returns_no_players_but_keeps_reports(self):
        service = WarcraftLogsGuildRecentLeaderboardService(
            FakeReportsService(),
            FakeSummaryService(),
            FakePerformanceService(),
        )

        result = await service.get_leaderboard(
            800007,
            difficulty=4,
            allowed_character_names=set(),
        )

        self.assertEqual(result.damage_players, ())
        self.assertEqual(result.healing_players, ())
        self.assertEqual([report.code for report in result.reports], ["NEW", "OLD"])
        self.assertTrue(result.raid_team_filtered)

    def test_report_window_is_21_days(self):
        day_ms = 24 * 60 * 60 * 1000
        newest = WarcraftLogsReport("NEW", "New", 30 * day_ms, None, None, "SoO")
        inside = WarcraftLogsReport("IN", "Inside", 9 * day_ms, None, None, "SoO")
        outside = WarcraftLogsReport("OUT", "Outside", 8 * day_ms, None, None, "SoO")

        result = _filter_report_window((newest, inside, outside))

        self.assertEqual([report.code for report in result], ["NEW", "IN"])


if __name__ == "__main__":
    unittest.main()
