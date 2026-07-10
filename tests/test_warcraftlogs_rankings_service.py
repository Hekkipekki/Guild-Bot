import unittest

from services.warcraftlogs.rankings_service import (
    WarcraftLogsRankingsService,
    _extract_ranking_entries,
    _unwrap_graphql_type,
)


class FakeClient:
    def __init__(self):
        self.queries = []

    async def query(self, query, variables=None):
        self.queries.append(query)
        if 'name: "GuildZoneRankings"' in query:
            return {
                "__type": {
                    "fields": [
                        {"name": "zoneName", "type": {"kind": "SCALAR", "name": "String"}},
                        {"name": "rankings", "type": {"kind": "SCALAR", "name": "JSON"}},
                    ]
                }
            }
        if 'name: "Guild"' in query:
            return {
                "__type": {
                    "fields": [
                        {
                            "name": "zoneRanking",
                            "args": [{"name": "size", "type": {"kind": "SCALAR"}}],
                        }
                    ]
                }
            }
        return {
            "guildData": {
                "guild": {
                    "id": 800007,
                    "name": "Example Guild",
                    "zoneRankings": {
                        "zoneName": "Siege of Orgrimmar",
                        "rankings": [
                            {
                                "encounter": {"name": "Immerseus"},
                                "worldRank": 100,
                                "regionRank": 50,
                                "serverRank": 3,
                            }
                        ],
                    },
                }
            }
        }


class WarcraftLogsRankingsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_and_caches_rankings(self):
        client = FakeClient()
        service = WarcraftLogsRankingsService(client)

        first = await service.get_guild_rankings(800007, raid_size=10)
        second = await service.get_guild_rankings(800007, raid_size=10)

        self.assertIs(first, second)
        self.assertEqual(first.guild_name, "Example Guild")
        self.assertEqual(first.zone_name, "Siege of Orgrimmar")
        self.assertEqual(first.entries[0].encounter_name, "Immerseus")
        self.assertEqual(first.entries[0].world_rank, 100)
        self.assertEqual(len(client.queries), 3)
        self.assertIn("zoneRankings: zoneRanking", client.queries[-1])
        self.assertIn("size: 10", client.queries[-1])
        self.assertIn("zoneName", client.queries[-1])
        self.assertIn("rankings", client.queries[-1])

    async def test_force_refresh_bypasses_cache_but_reuses_schema(self):
        client = FakeClient()
        service = WarcraftLogsRankingsService(client)

        await service.get_guild_rankings(800007)
        await service.get_guild_rankings(800007, force_refresh=True)

        self.assertEqual(len(client.queries), 4)

    def test_parser_supports_flat_ranking_shape(self):
        entries = _extract_ranking_entries(
            [
                {
                    "encounterName": "Garrosh Hellscream",
                    "rank": 42,
                    "regionRank": 18,
                    "percentile": 96.5,
                }
            ]
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].encounter_name, "Garrosh Hellscream")
        self.assertEqual(entries[0].world_rank, 42)
        self.assertEqual(entries[0].region_rank, 18)
        self.assertEqual(entries[0].rank_percent, 96.5)

    def test_parser_ignores_non_ranking_named_objects(self):
        entries = _extract_ranking_entries({"name": "Guild Name", "id": 800007})
        self.assertEqual(entries, [])

    def test_unwraps_list_and_non_null_graphql_types(self):
        kind, name = _unwrap_graphql_type(
            {
                "kind": "NON_NULL",
                "ofType": {
                    "kind": "LIST",
                    "ofType": {"kind": "SCALAR", "name": "JSON"},
                },
            }
        )
        self.assertEqual((kind, name), ("SCALAR", "JSON"))


if __name__ == "__main__":
    unittest.main()
