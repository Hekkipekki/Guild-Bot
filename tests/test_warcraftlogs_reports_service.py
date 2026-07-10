import unittest

from services.warcraftlogs.reports_service import WarcraftLogsReportsService


class FakeClient:
    def __init__(self):
        self.calls = []

    async def query(self, query, variables=None):
        self.calls.append((query, variables))
        return {
            "reportData": {
                "reports": {
                    "data": [
                        {
                            "code": "ABC123",
                            "title": "Sunday Raid",
                            "startTime": 1000,
                            "endTime": 3700000,
                            "owner": {"name": "Uploader"},
                            "zone": {"name": "Siege of Orgrimmar"},
                        }
                    ]
                }
            }
        }


class WarcraftLogsReportsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_and_normalizes_recent_reports(self):
        client = FakeClient()
        service = WarcraftLogsReportsService(client)

        result = await service.get_recent_reports(800007, limit=5)

        self.assertEqual(result.guild_id, 800007)
        self.assertEqual(len(result.reports), 1)
        report = result.reports[0]
        self.assertEqual(report.code, "ABC123")
        self.assertEqual(report.title, "Sunday Raid")
        self.assertEqual(report.owner_name, "Uploader")
        self.assertEqual(report.zone_name, "Siege of Orgrimmar")
        self.assertEqual(report.duration_ms, 3699000)
        self.assertEqual(
            report.url,
            "https://classic.warcraftlogs.com/reports/ABC123",
        )
        self.assertEqual(client.calls[0][1], {"guildID": 800007, "limit": 5})

    async def test_uses_cache_for_same_guild_and_limit(self):
        client = FakeClient()
        service = WarcraftLogsReportsService(client)

        first = await service.get_recent_reports(800007, limit=5)
        second = await service.get_recent_reports(800007, limit=5)

        self.assertIs(first, second)
        self.assertEqual(len(client.calls), 1)

    async def test_force_refresh_bypasses_cache(self):
        client = FakeClient()
        service = WarcraftLogsReportsService(client)

        await service.get_recent_reports(800007, limit=5)
        await service.get_recent_reports(800007, limit=5, force_refresh=True)

        self.assertEqual(len(client.calls), 2)

    async def test_different_limits_use_different_cache_entries(self):
        client = FakeClient()
        service = WarcraftLogsReportsService(client)

        await service.get_recent_reports(800007, limit=5)
        await service.get_recent_reports(800007, limit=10)

        self.assertEqual(len(client.calls), 2)

    async def test_rejects_invalid_limit(self):
        service = WarcraftLogsReportsService(FakeClient())

        with self.assertRaises(ValueError):
            await service.get_recent_reports(800007, limit=0)


if __name__ == "__main__":
    unittest.main()
