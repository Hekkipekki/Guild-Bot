import unittest

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceService,
    aggregate_player_performance,
    parse_player_performance_rows,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def query(self, query, variables=None):
        self.calls.append((query, variables))
        return {
            "reportData": {
                "report": {
                    "code": "ABC123",
                    "title": "Sunday Raid",
                    "rankings": {
                        "data": [
                            {
                                "name": "Playerone",
                                "class": "Shaman",
                                "spec": "Elemental",
                                "rankPercent": 97.4,
                                "amount": 245000.0,
                                "itemLevel": 566,
                                "encounterName": "Immerseus",
                            },
                            {
                                "name": "Playerone",
                                "class": "Shaman",
                                "spec": "Elemental",
                                "rankPercent": 82.6,
                                "amount": 221000.0,
                                "itemLevel": 567,
                                "encounterName": "Fallen Protectors",
                            },
                            {
                                "characterName": "Playertwo",
                                "className": "Paladin",
                                "specName": "Retribution",
                                "percentile": 91.2,
                                "total": 231000.0,
                                "encounterName": "Immerseus",
                            },
                        ]
                    },
                }
            }
        }


class PlayerPerformanceParserTests(unittest.TestCase):
    def test_parses_common_player_row_shapes(self):
        rows = parse_player_performance_rows(
            {
                "rankings": [
                    {
                        "name": "Alpha",
                        "spec": "Fire",
                        "rankPercent": 99.1,
                        "amount": 1000,
                    },
                    {
                        "characterName": "Beta",
                        "specName": "Shadow",
                        "historicalPercent": 88.5,
                        "total": 900,
                    },
                ]
            }
        )

        self.assertEqual([row.name for row in rows], ["Alpha", "Beta"])
        self.assertEqual(rows[0].spec_name, "Fire")
        self.assertEqual(rows[0].rank_percent, 99.1)
        self.assertEqual(rows[1].amount, 900.0)

    def test_ignores_metadata_without_performance_values(self):
        rows = parse_player_performance_rows(
            {"guild": {"name": "Example Guild"}, "zone": {"name": "SoO"}}
        )

        self.assertEqual(rows, ())

    def test_deduplicates_nested_repeated_rows(self):
        row = {"name": "Alpha", "spec": "Fire", "rankPercent": 99.1}
        rows = parse_player_performance_rows({"data": [row], "copy": row})

        self.assertEqual(len(rows), 1)

    def test_keeps_same_percentile_when_amount_differs(self):
        rows = parse_player_performance_rows(
            {
                "data": [
                    {"name": "Alpha", "rankPercent": 95, "amount": 1000},
                    {"name": "Alpha", "rankPercent": 95, "amount": 1100},
                ]
            }
        )

        self.assertEqual(len(rows), 2)


class PlayerPerformanceAggregationTests(unittest.TestCase):
    def test_groups_rows_and_calculates_summary_metrics(self):
        rows = (
            WarcraftLogsPlayerPerformance(
                name="Alpha",
                server="Realm",
                class_name="Shaman",
                spec_name="Elemental",
                role="DPS",
                amount=1000,
                rank_percent=90,
                item_level=560,
                encounter_name="Immerseus",
            ),
            WarcraftLogsPlayerPerformance(
                name="Alpha",
                server="Realm",
                class_name="Shaman",
                spec_name="Elemental",
                role="DPS",
                amount=1400,
                rank_percent=98,
                item_level=562,
                encounter_name="Fallen Protectors",
            ),
            WarcraftLogsPlayerPerformance(
                name="Beta",
                server="Realm",
                class_name="Priest",
                spec_name="Discipline",
                role="Healer",
                amount=700,
                rank_percent=80,
                item_level=559,
                encounter_name="Immerseus",
            ),
        )

        summaries = aggregate_player_performance(rows)

        self.assertEqual([summary.name for summary in summaries], ["Alpha", "Beta"])
        alpha = summaries[0]
        self.assertEqual(alpha.primary_spec, "Elemental")
        self.assertEqual(alpha.average_parse, 94.0)
        self.assertEqual(alpha.median_parse, 94.0)
        self.assertEqual(alpha.best_parse, 98)
        self.assertEqual(alpha.worst_parse, 90)
        self.assertEqual(alpha.average_amount, 1200.0)
        self.assertEqual(alpha.best_amount, 1400)
        self.assertEqual(alpha.average_item_level, 561.0)
        self.assertEqual(alpha.encounter_count, 2)
        self.assertEqual(alpha.parse_count, 2)

    def test_groups_character_names_case_insensitively(self):
        rows = (
            WarcraftLogsPlayerPerformance(
                "Alpha", None, None, "Fire", None, 1000, 90, None, None
            ),
            WarcraftLogsPlayerPerformance(
                "alpha", None, None, "Fire", None, 1100, 95, None, None
            ),
        )

        summaries = aggregate_player_performance(rows)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].encounter_count, 2)


class PlayerPerformanceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_normalizes_and_aggregates_report_rankings(self):
        client = FakeClient()
        service = WarcraftLogsPlayerPerformanceService(client)

        result = await service.get_report_player_performance("ABC123")

        self.assertEqual(result.report_code, "ABC123")
        self.assertEqual(result.report_title, "Sunday Raid")
        self.assertEqual(len(result.players), 3)
        self.assertEqual(len(result.player_summaries), 2)
        self.assertEqual(
            [summary.name for summary in result.player_summaries],
            ["Playertwo", "Playerone"],
        )
        playerone = result.player_summaries[1]
        self.assertEqual(playerone.average_parse, 90.0)
        self.assertEqual(playerone.encounter_count, 2)
        self.assertEqual(
            result.url,
            "https://classic.warcraftlogs.com/reports/ABC123",
        )
        self.assertEqual(client.calls[0][1], {"code": "ABC123"})

    async def test_uses_cache_and_refresh_bypasses_it(self):
        client = FakeClient()
        service = WarcraftLogsPlayerPerformanceService(client)

        first = await service.get_report_player_performance("ABC123")
        second = await service.get_report_player_performance("ABC123")
        refreshed = await service.get_report_player_performance(
            "ABC123", force_refresh=True
        )

        self.assertIs(first, second)
        self.assertIsNot(first, refreshed)
        self.assertEqual(len(client.calls), 2)

    async def test_rejects_empty_report_code(self):
        service = WarcraftLogsPlayerPerformanceService(FakeClient())

        with self.assertRaises(ValueError):
            await service.get_report_player_performance("")


if __name__ == "__main__":
    unittest.main()
