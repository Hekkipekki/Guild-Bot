import unittest

from services.warcraftlogs.report_leaderboard_service import (
    WarcraftLogsReportLeaderboardService,
    _event_damage_amount,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def query(self, query, variables=None):
        self.calls.append((query, variables))
        if "ReportPlayerPerformance" in query:
            return {
                "reportData": {
                    "report": {
                        "code": "ABC123",
                        "title": "Sunday Raid",
                        "rankings": {
                            "data": [
                                {
                                    "name": "Alpha",
                                    "spec": "Elemental",
                                    "role": "DPS",
                                    "rankPercent": 90,
                                    "amount": 200000,
                                    "encounterName": "Immerseus",
                                },
                                {
                                    "name": "Alpha",
                                    "spec": "Elemental",
                                    "role": "DPS",
                                    "rankPercent": 95,
                                    "amount": 300000,
                                    "encounterName": "Fallen Protectors",
                                },
                                {
                                    "name": "Healer",
                                    "spec": "Holy",
                                    "role": "Healer",
                                    "rankPercent": 99,
                                    "amount": 500000,
                                    "encounterName": "Immerseus",
                                },
                            ]
                        },
                    }
                }
            }
        if "ReportSummary" in query:
            return {
                "reportData": {
                    "report": {
                        "code": "ABC123",
                        "title": "Sunday Raid",
                        "startTime": 0,
                        "endTime": 20000,
                        "owner": {"name": "Owner"},
                        "zone": {"name": "Siege of Orgrimmar"},
                        "fights": [
                            {
                                "id": 1,
                                "encounterID": 1,
                                "name": "Immerseus Heroic (10 Player)",
                                "difficulty": 4,
                                "kill": True,
                                "startTime": 0,
                                "endTime": 10000,
                                "bossPercentage": 0,
                            },
                            {
                                "id": 2,
                                "encounterID": 2,
                                "name": "Malkorok Heroic (10 Player)",
                                "difficulty": 4,
                                "kill": True,
                                "startTime": 10000,
                                "endTime": 20000,
                                "bossPercentage": 0,
                            },
                        ],
                    }
                }
            }
        if "ReportActors" in query:
            return {
                "reportData": {
                    "report": {
                        "masterData": {
                            "actors": [
                                {"id": 10, "name": "Alpha", "type": "Player", "subType": "Shaman"},
                                {"id": 11, "name": "Bravo", "type": "Player", "subType": "Mage"},
                                {"id": 99, "name": "Enemy", "type": "NPC", "subType": "Boss"},
                            ]
                        }
                    }
                }
            }
        if "ReportAvoidableDamage" in query:
            return {
                "reportData": {
                    "report": {
                        "events": {
                            "data": [
                                {"targetID": 10, "ability": {"name": "Swirl"}, "amount": 1000, "overkill": 100},
                                {"targetID": 10, "ability": {"name": "Melee"}, "amount": 5000},
                                {"targetID": 11, "abilityName": "Sha Corruption", "amount": 200},
                                {"targetID": 99, "ability": {"name": "Swirl"}, "amount": 9999},
                            ],
                            "nextPageTimestamp": None,
                        }
                    }
                }
            }
        raise AssertionError(f"Unexpected query: {query}")


class ReportLeaderboardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_dps_leaderboard_from_damage_players_only(self):
        service = WarcraftLogsReportLeaderboardService(FakeClient())

        result = await service.get_leaderboard("ABC123", "dps")

        self.assertEqual(result.metric, "dps")
        self.assertEqual(len(result.dps_entries), 1)
        self.assertEqual(result.dps_entries[0].name, "Alpha")
        self.assertEqual(result.dps_entries[0].dps, 250000)
        self.assertEqual(result.dps_entries[0].ranked_fights, 2)

    async def test_builds_avoidable_dtps_and_excludes_uncovered_bosses(self):
        service = WarcraftLogsReportLeaderboardService(FakeClient())

        result = await service.get_leaderboard("ABC123", "dtps")

        self.assertEqual(result.metric, "dtps")
        self.assertEqual(result.covered_bosses, ("Immerseus",))
        self.assertEqual(result.excluded_bosses, ("Malkorok",))
        self.assertEqual(result.covered_duration_ms, 10000)
        self.assertEqual([entry.name for entry in result.dtps_entries], ["Bravo", "Alpha"])
        bravo, alpha = result.dtps_entries
        self.assertEqual(bravo.total_avoidable_damage, 200)
        self.assertEqual(bravo.dtps, 20)
        self.assertEqual(alpha.total_avoidable_damage, 900)
        self.assertEqual(alpha.dtps, 90)
        self.assertEqual(alpha.hit_count, 1)
        self.assertIn("Melee", result.unmatched_abilities)

    async def test_rejects_unknown_metric(self):
        service = WarcraftLogsReportLeaderboardService(FakeClient())
        with self.assertRaises(ValueError):
            await service.get_leaderboard("ABC123", "healing")


class EventDamageTests(unittest.TestCase):
    def test_subtracts_overkill(self):
        self.assertEqual(_event_damage_amount({"amount": 1000, "overkill": 250}), 750)
        self.assertEqual(_event_damage_amount({"amount": 100, "overkill": 200}), 0)


if __name__ == "__main__":
    unittest.main()
