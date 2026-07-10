import unittest

from services.warcraftlogs.encounter_label_parser import parse_encounter_label


class EncounterLabelParserTests(unittest.TestCase):
    def test_parses_heroic_ten_player_label(self):
        parsed = parse_encounter_label("Garrosh Hellscream Heroic (10 Player)")

        self.assertEqual(parsed.original_label, "Garrosh Hellscream Heroic (10 Player)")
        self.assertEqual(parsed.encounter_name, "Garrosh Hellscream")
        self.assertEqual(parsed.difficulty, "Heroic")
        self.assertEqual(parsed.raid_size, 10)

    def test_parses_normal_twenty_five_player_label(self):
        parsed = parse_encounter_label("Immerseus Normal (25 Player)")

        self.assertEqual(parsed.encounter_name, "Immerseus")
        self.assertEqual(parsed.difficulty, "Normal")
        self.assertEqual(parsed.raid_size, 25)

    def test_preserves_unknown_suffix_in_encounter_name(self):
        parsed = parse_encounter_label("Custom Encounter Challenge Mode")

        self.assertEqual(parsed.encounter_name, "Custom Encounter Challenge Mode")
        self.assertIsNone(parsed.difficulty)
        self.assertIsNone(parsed.raid_size)

    def test_parses_raid_size_without_difficulty(self):
        parsed = parse_encounter_label("Sha of Pride (10 Player)")

        self.assertEqual(parsed.encounter_name, "Sha of Pride")
        self.assertIsNone(parsed.difficulty)
        self.assertEqual(parsed.raid_size, 10)

    def test_empty_label_is_safe(self):
        parsed = parse_encounter_label(None)

        self.assertEqual(parsed.original_label, "")
        self.assertEqual(parsed.encounter_name, "Unknown encounter")
        self.assertIsNone(parsed.difficulty)
        self.assertIsNone(parsed.raid_size)


if __name__ == "__main__":
    unittest.main()
