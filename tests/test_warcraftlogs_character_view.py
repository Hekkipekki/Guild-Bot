import unittest

from services.warcraftlogs.character_performance_service import CharacterParseEntry
from views.warcraftlogs_character_view import _best_kill_per_boss


class CharacterViewTests(unittest.TestCase):
    def test_keeps_one_best_killed_parse_per_boss_across_specs(self):
        entries = (
            CharacterParseEntry("Norushen", "Elemental", 92.9, 256725, 4),
            CharacterParseEntry("Norushen", "Restoration", 78.4, 1048, 1),
            CharacterParseEntry("Iron Juggernaut", "Elemental", 75.6, 251033, 1),
            CharacterParseEntry("Iron Juggernaut", "Enhancement", 66.7, 220000, 2),
            CharacterParseEntry("Garrosh Hellscream", "Elemental", None, 0, 0),
            CharacterParseEntry("Malkorok", "Elemental", 80.0, 300000, 0),
        )

        result = _best_kill_per_boss(entries)

        self.assertEqual(
            [entry.encounter_name for entry in result],
            ["Norushen", "Iron Juggernaut"],
        )
        self.assertEqual(result[0].spec_name, "Elemental")
        self.assertEqual(result[0].rank_percent, 92.9)
        self.assertEqual(result[1].rank_percent, 75.6)

    def test_helper_is_difficulty_agnostic(self):
        entries = (
            CharacterParseEntry("Immerseus", "Affliction", 81.2, 400000, 2),
            CharacterParseEntry("Immerseus", "Demonology", 88.4, 420000, 1),
        )

        result = _best_kill_per_boss(entries)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].spec_name, "Demonology")
        self.assertEqual(result[0].rank_percent, 88.4)


if __name__ == "__main__":
    unittest.main()
