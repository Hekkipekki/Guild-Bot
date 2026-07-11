import unittest

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceResult,
    aggregate_player_performance,
)
from services.warcraftlogs.recent_guild_rankings_service import (
    WarcraftLogsRecentGuildRankingsService,
)
from services.warcraftlogs.reports_service import (
    WarcraftLogsReport,
    WarcraftLogsReportsResult,
)


class FakeReportsService:
    async def get_recent_reports(self, guild_id, *, limit, force_refresh=False):
        reports = (
            WarcraftLogsReport("LATEST", "Latest", 2, 3, None, "SoO"),
            WarcraftLogsReport("OLDER", "Older", 1, 2, None, "SoO"),
            WarcraftLogsReport("OTHER", "Other zone", 0, 1, None, "ToT"),
        )
        return WarcraftLogsReportsResult(guild_id, reports[:limit], {}, 0)


class FakePerformanceService:
    async def get_report_player_performance(self, code, *, force_refresh=False):
        if code == "LATEST":
            rows = (
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 300000, 82, 570, "Immerseus"
                ),
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 350000, 62, 570, "Fallen Protectors"
                ),
                WarcraftLogsPlayerPerformance(
                    "Healz", "Realm", "Priest", "Discipline", "Healer", 90000, 88, 569, "Immerseus"
                ),
            )
        elif code == "OLDER":
            rows = (
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 350000, 96, 568, "Norushen"
                ),
                WarcraftLogsPlayerPerformance(
                    "Alpha", "Realm", "Shaman", "Elemental", "DPS", 320000, 90, 568, "Sha of Pride"
                ),
                WarcraftLogsPlayerPerformance(
                    "Tanky", "Realm", "Druid", "Guardian", "Tank", 150000, 75, 570, "Norushen"
                ),
            )
        else:
            raise AssertionError("Reports from another zone must not be queried")
        return WarcraftLogsPlayerPerformanceResult(
            report_code=code,
            report_title=code,
            players=rows,
            player_summaries=aggregate_player_performance(rows),
            raw_rankings={},
            fetched_at=0,
        )


class RecentGuildRankingsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_best_report_average_across_latest_zone(self):
        service = WarcraftLogsRecentGuildRankingsService(
            FakeReportsService(),
            FakePerformanceService(),
        )

        result = await service.get_recent_rankings(800007)

        self.assertEqual(result.latest_report_code, "LATEST")
        self.assertEqual(result.report_codes, ("LATEST", "OLDER"))
        entries = {(entry.name, entry.spec_name): entry for entry in result.entries}
        self.assertEqual(entries[("Alpha", "Elemental")].best_average_parse, 93)
        self.assertEqual(entries[("Alpha", "Elemental")].report_count, 2)
        self.assertEqual(entries[("Healz", "Discipline")].role_category, "Healer")
        self.assertEqual(entries[("Tanky", "Guardian")].role_category, "Tank")


if __name__ == "__main__":
    unittest.main()
