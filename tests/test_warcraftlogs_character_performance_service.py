import unittest

from services.warcraftlogs.character_performance_service import (
    WarcraftLogsCharacterPerformanceService,
    parse_character_rankings,
)


class FakeClient:
    def __init__(self):
        self.calls = []

    async def query(self, query, variables=None):
        self.calls.append((query, variables))
        return {
            "characterData": {
                "character": {
                    "name": "Lenef",
                    "normalDamage": {
                        "rankings": [
                            {
                                "encounter": {"name": "Immerseus"},
                                "spec": "Affliction",
                                "rankPercent": 91.2,
                                "amount": 345000,
                            }
                        ]
                    },
                    "heroicDamage": {
                        "rankings": [
                            {
                                "encounter": {"name": "Garrosh Hellscream"},
                                "spec": "Affliction",
                                "rankPercent": 97.5,
                                "amount": 512000,
                            }
                        ]
                    },
                    "normalHealing": {},
                    "heroicHealing": {
                        "encounters": [
                            {
                                "name": "Norushen",
                                "rankings": [
                                    {
                                        "specName": "Destruction",
                                        "bestPercent": 44.0,
                                        "hps": 12000,
                                    }
                                ],
                            }
                        ]
                    },
                }
            }
        }


class CharacterRankingParserTests(unittest.TestCase):
    def test_parses_direct_encounter_rows(self):
        entries = parse_character_rankings(
            {
                "rankings": [
                    {
                        "encounter": {"name": "Immerseus"},
                        "spec": "Affliction",
                        "rankPercent": 93,
                        "amount": 345745,
                    }
                ]
            }
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].encounter_name, "Immerseus")
        self.assertEqual(entries[0].spec_name, "Affliction")
        self.assertEqual(entries[0].rank_percent, 93)

    def test_carries_parent_encounter_context(self):
        entries = parse_character_rankings(
            {
                "encounters": [
                    {
                        "encounterName": "Fallen Protectors",
                        "rankings": [
                            {
                                "specName": "Affliction",
                                "bestPercent": 88,
                                "dps": 400000,
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(entries[0].encounter_name, "Fallen Protectors")
        self.assertEqual(entries[0].spec_name, "Affliction")
        self.assertEqual(entries[0].rank_percent, 88)


class CharacterPerformanceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_all_four_character_views(self):
        client = FakeClient()
        service = WarcraftLogsCharacterPerformanceService(client)

        result = await service.get_character_performance("Lenef", "Hoptallus", "EU")

        self.assertEqual(result.character_name, "Lenef")
        self.assertEqual(result.server_slug, "hoptallus")
        self.assertEqual(result.region, "eu")
        self.assertEqual(result.heroic_damage[0].encounter_name, "Garrosh Hellscream")
        self.assertEqual(result.heroic_healing[0].encounter_name, "Norushen")
        self.assertIn("difficulty=4&size=10", result.url("heroic", "damage"))
        self.assertIn("metric=hps", result.url("heroic", "healing"))
        self.assertEqual(
            client.calls[0][1],
            {"name": "Lenef", "serverSlug": "hoptallus", "serverRegion": "eu"},
        )

    async def test_uses_cache(self):
        client = FakeClient()
        service = WarcraftLogsCharacterPerformanceService(client)

        first = await service.get_character_performance("Lenef", "Hoptallus", "EU")
        second = await service.get_character_performance("Lenef", "Hoptallus", "EU")

        self.assertIs(first, second)
        self.assertEqual(len(client.calls), 1)

    async def test_rejects_missing_character_identity(self):
        service = WarcraftLogsCharacterPerformanceService(FakeClient())
        with self.assertRaises(ValueError):
            await service.get_character_performance("", "Hoptallus", "EU")


if __name__ == "__main__":
    unittest.main()
