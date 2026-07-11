import unittest

from services.warcraftlogs.guild_recent_leaderboard_service import (
    WarcraftLogsGuildRecentLeaderboardService,
)


class FakeSchemaService:
    async def _get_zone_ranking_schema(self):
        return {"size", "metric", "recent"}, "GuildZoneRankings"

    async def _build_type_selection(self, type_name, *, visited, depth):
        return "data"


class FakeClient:
    def __init__(self, *, include_difficulty_blocks=False):
        self.include_difficulty_blocks = include_difficulty_blocks
        self.queries = []

    async def query(self, query, variables=None):
        self.queries.append(query)
        healing = "metric: hps" in query
        rows = (
            [
                {
                    "name": "Healz",
                    "server": "Shek'zeer",
                    "spec": "Restoration",
                    "role": "Healer",
                    "rankPercent": 82,
                    "encounterName": "Immerseus",
                },
                {
                    "name": "Healz",
                    "server": "Shek'zeer",
                    "spec": "Restoration",
                    "role": "Healer",
                    "rankPercent": 90,
                    "encounterName": "Norushen",
                },
            ]
            if healing
            else [
                {
                    "name": "Tanky",
                    "server": "Realm",
                    "spec": "Guardian",
                    "role": "Tank",
                    "rankPercent": 60,
                    "encounterName": "Immerseus",
                },
                {
                    "name": "Damage",
                    "server": "Realm",
                    "spec": "Elemental",
                    "role": "DPS",
                    "rankPercent": 95,
                    "encounterName": "Immerseus",
                },
            ]
        )
        payload = {"data": rows}
        if self.include_difficulty_blocks:
            payload = {
                "difficulties": [
                    {"difficulty": 3, "data": rows},
                    {"difficulty": 4, "data": rows},
                ]
            }
        return {
            "guildData": {
                "guild": {
                    "id": 800007,
                    "name": "Test Guild",
                    "zoneRankings": payload,
                }
            }
        }


class GuildRecentLeaderboardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_default_heroic_without_difficulty_argument(self):
        client = FakeClient()
        service = WarcraftLogsGuildRecentLeaderboardService(client)
        service.schema_service = FakeSchemaService()

        result = await service.get_leaderboard(800007, difficulty=4)

        self.assertEqual(result.guild_name, "Test Guild")
        self.assertEqual(result.difficulty, 4)
        self.assertTrue(result.difficulty_available)
        self.assertEqual([p.name for p in result.damage_players], ["Damage", "Tanky"])
        self.assertEqual([p.name for p in result.healing_players], ["Healz"])
        self.assertEqual(result.healing_players[0].average_parse, 86)
        self.assertTrue(all("difficulty:" not in query for query in client.queries))

    async def test_normal_is_unavailable_without_payload_markers(self):
        client = FakeClient()
        service = WarcraftLogsGuildRecentLeaderboardService(client)
        service.schema_service = FakeSchemaService()

        result = await service.get_leaderboard(800007, difficulty=3)

        self.assertFalse(result.difficulty_available)
        self.assertEqual(result.damage_players, ())
        self.assertEqual(result.healing_players, ())
        self.assertIn("difficulty=3", result.url)

    async def test_normal_filters_labeled_difficulty_blocks(self):
        client = FakeClient(include_difficulty_blocks=True)
        service = WarcraftLogsGuildRecentLeaderboardService(client)
        service.schema_service = FakeSchemaService()

        result = await service.get_leaderboard(800007, difficulty=3)

        self.assertTrue(result.difficulty_available)
        self.assertEqual([p.name for p in result.damage_players], ["Damage", "Tanky"])


if __name__ == "__main__":
    unittest.main()
