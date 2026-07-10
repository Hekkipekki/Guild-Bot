from __future__ import annotations

import unittest

from services.warcraftlogs.report_summary_service import WarcraftLogsReportSummaryService


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def query(self, query, variables=None):
        self.calls.append((query, variables or {}))
        return self.payload


class WarcraftLogsReportSummaryServiceTests(unittest.IsolatedAsyncioTestCase):
    def _payload(self):
        return {
            "reportData": {
                "report": {
                    "code": "ABC123",
                    "title": "SoO W5 - D1",
                    "startTime": 1000,
                    "endTime": 100000,
                    "owner": {"name": "Hekkipekki"},
                    "zone": {"name": "Siege of Orgrimmar"},
                    "fights": [
                        {
                            "id": 1,
                            "encounterID": 1622,
                            "name": "Galakras Heroic (10 Player)",
                            "difficulty": 4,
                            "kill": False,
                            "startTime": 1000,
                            "endTime": 61000,
                            "bossPercentage": 2400,
                        },
                        {
                            "id": 2,
                            "encounterID": 1622,
                            "name": "Galakras Heroic (10 Player)",
                            "difficulty": 4,
                            "kill": True,
                            "startTime": 62000,
                            "endTime": 92000,
                            "bossPercentage": 0,
                        },
                        {
                            "id": 3,
                            "encounterID": 0,
                            "name": "Trash",
                            "difficulty": None,
                            "kill": False,
                            "startTime": 93000,
                            "endTime": 99000,
                            "bossPercentage": None,
                        },
                    ],
                }
            }
        }

    async def test_parses_report_and_normalizes_encounter_label(self):
        service = WarcraftLogsReportSummaryService(_FakeClient(self._payload()))

        result = await service.get_report_summary("ABC123")

        self.assertEqual(result.code, "ABC123")
        self.assertEqual(result.total_kills, 1)
        self.assertEqual(result.total_wipes, 1)
        self.assertEqual(len(result.encounters), 1)
        encounter = result.encounters[0]
        self.assertEqual(encounter.label.encounter_name, "Galakras")
        self.assertEqual(encounter.label.difficulty, "Heroic")
        self.assertEqual(encounter.label.raid_size, 10)
        self.assertEqual(encounter.kills, 1)
        self.assertEqual(encounter.wipes, 1)
        self.assertEqual(encounter.fastest_kill_ms, 30000)
        self.assertEqual(encounter.best_wipe_percentage, 2400)

    async def test_uses_cache_unless_refresh_is_requested(self):
        client = _FakeClient(self._payload())
        service = WarcraftLogsReportSummaryService(client)

        first = await service.get_report_summary("ABC123")
        second = await service.get_report_summary("ABC123")
        refreshed = await service.get_report_summary("ABC123", force_refresh=True)

        self.assertIs(first, second)
        self.assertIsNot(first, refreshed)
        self.assertEqual(len(client.calls), 2)

    async def test_rejects_missing_report_code(self):
        service = WarcraftLogsReportSummaryService(_FakeClient(self._payload()))

        with self.assertRaises(ValueError):
            await service.get_report_summary("   ")


if __name__ == "__main__":
    unittest.main()
