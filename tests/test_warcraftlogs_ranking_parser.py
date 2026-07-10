import unittest

from services.warcraftlogs.ranking_parser import parse_guild_ranking_categories


class WarcraftLogsRankingParserTests(unittest.TestCase):
    def test_parses_current_classic_guild_ranking_shape(self):
        entries = parse_guild_ranking_categories(
            {
                "progress": {
                    "worldRank": {"number": 501, "color": "rare", "percentile": None},
                    "regionRank": {"number": 327, "color": "rare", "percentile": None},
                    "serverRank": {"number": 186, "color": "epic", "percentile": None},
                },
                "speed": {
                    "worldRank": {"number": 1079, "color": "uncommon", "percentile": None},
                    "regionRank": {"number": 574, "color": "rare", "percentile": None},
                    "serverRank": {"number": 184, "color": "epic", "percentile": None},
                },
                "completeRaidSpeed": {
                    "worldRank": None,
                    "regionRank": None,
                    "serverRank": None,
                },
            }
        )

        self.assertEqual([entry.encounter_name for entry in entries], [
            "Progress",
            "Speed",
            "Complete Raid Speed",
        ])
        self.assertEqual(entries[0].world_rank, 501)
        self.assertEqual(entries[0].region_rank, 327)
        self.assertEqual(entries[0].server_rank, 186)
        self.assertEqual(entries[1].world_rank, 1079)
        self.assertIsNone(entries[2].world_rank)

    def test_ignores_unknown_top_level_fields(self):
        entries = parse_guild_ranking_categories({"unknown": {"worldRank": 1}})
        self.assertEqual(entries, ())

    def test_supports_direct_numeric_rank_values(self):
        entries = parse_guild_ranking_categories(
            {
                "progress": {
                    "worldRank": 10,
                    "regionRank": 5,
                    "serverRank": 1,
                }
            }
        )
        self.assertEqual(entries[0].world_rank, 10)
        self.assertEqual(entries[0].region_rank, 5)
        self.assertEqual(entries[0].server_rank, 1)


if __name__ == "__main__":
    unittest.main()
