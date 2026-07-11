import unittest

from services.warcraftlogs.guild_recent_leaderboard_service import (
    WarcraftLogsGuildRecentLeaderboardService,
)


class FakeSchemaService:
    async def _get_zone_ranking_schema(self):
        return {"size", "difficulty", "metric", "recent"}, "GuildZoneRankings"

    async def _build_type_selection(self, type_name, *, visited, depth):
        return "data"


class FakeClient:
    async def query(self, query, variables=None):
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
        return {
            "guildData": {
                "guild": {
                    "id": 800007,
                    "name": "Test Guild",
                    "zoneRankings": {"data": rows},
                }
            }
        }


class GuildRecentLeaderboardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_exact_recent_damage_and_healing_rankings(self):
        service = WarcraftLogsGuildRecentLeaderboardService(FakeClient())
        service.schema_service = FakeSchemaService()

        result = await service.get_leaderboard(800007, difficulty=4)

        self.assertEqual(result.guild_name, "Test Guild")
        self.assertEqual(result.difficulty, 4)
        self.assertEqual([p.name for p in result.damage_players], ["Damage", "Tanky"])
        self.assertEqual([p.name for p in result.healing_players], ["Healz"])
        self.assertEqual(result.healing_players[0].average_parse, 86)
        self.assertIn("recent=true", result.url)
        self.assertNotIn("difficulty=3", result.url)

    async def test_normal_url_contains_difficulty(self):
        service = WarcraftLogsGuildRecentLeaderboardService(FakeClient())
        service.schema_service = FakeSchemaService()

        result = await service.get_leaderboard(800007, difficulty=3)

        self.assertIn("difficulty=3", result.url)


if __name__ == "__main__":
    unittest.main()
