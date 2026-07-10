import unittest

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformanceService,
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
                            },
                            {
                                "characterName": "Playertwo",
                                "className": "Paladin",
                                "specName": "Retribution",
                                "percentile": 91.2,
                                "total": 231000.0,
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


class PlayerPerformanceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_and_normalizes_report_rankings(self):
        client = FakeClient()
        service = WarcraftLogsPlayerPerformanceService(client)

        result = await service.get_report_player_performance("ABC123")

        self.assertEqual(result.report_code, "ABC123")
        self.assertEqual(result.report_title, "Sunday Raid")
        self.assertEqual(len(result.players), 2)
        self.assertEqual(result.players[0].name, "Playerone")
        self.assertEqual(result.players[0].rank_percent, 97.4)
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
