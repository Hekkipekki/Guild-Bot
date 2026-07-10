import unittest

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceResult,
    aggregate_player_performance,
)
from services.warcraftlogs.player_ranking_graphic import render_player_ranking_graphic


class WarcraftLogsPlayerRankingGraphicTests(unittest.TestCase):
    def test_renders_png_with_role_and_boss_data(self):
        rows = (
            WarcraftLogsPlayerPerformance(
                "Alpha", "Realm", "Shaman", "Elemental", "DPS", 250000, 95, 570, "Immerseus"
            ),
            WarcraftLogsPlayerPerformance(
                "Alpha", "Realm", "Shaman", "Elemental", "DPS", 230000, 82, 570, "Norushen"
            ),
            WarcraftLogsPlayerPerformance(
                "Bravo", "Realm", "Druid", "Guardian", "Tank", 120000, 55, 568, "Immerseus"
            ),
        )
        result = WarcraftLogsPlayerPerformanceResult(
            report_code="ABC123",
            report_title="Sunday Raid",
            players=rows,
            player_summaries=aggregate_player_performance(rows),
            raw_rankings={},
            fetched_at=0,
        )

        image = render_player_ranking_graphic(result)

        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(image), 1000)


if __name__ == "__main__":
    unittest.main()
