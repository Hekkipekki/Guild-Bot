import unittest

from services.warcraftlogs.avoidable_damage_registry import (
    avoidable_ability_names,
    covered_bosses,
    is_avoidable_damage,
    mechanics_for_boss,
    normalize_boss_name,
    normalize_mechanic_name,
)


class AvoidableDamageRegistryTests(unittest.TestCase):
    def test_normalizes_names_and_punctuation(self):
        self.assertEqual(normalize_mechanic_name("  Self-Reflection "), "self reflection")
        self.assertEqual(normalize_boss_name("Kor’kron Dark Shamans"), "kor kron dark shaman")

    def test_matches_configured_boss_abilities(self):
        self.assertTrue(is_avoidable_damage("Immerseus", "Swirl"))
        self.assertTrue(is_avoidable_damage("Sha of Pride", "Ethereal Corruption"))
        self.assertTrue(is_avoidable_damage("Dark Shamans", "Iron Tomb"))
        self.assertTrue(is_avoidable_damage("General Nazgrim", "Aftershock"))

    def test_accepts_ricochet_spelling_alias(self):
        self.assertTrue(is_avoidable_damage("Iron Juggernaut", "Ricochet"))
        self.assertTrue(is_avoidable_damage("Iron Juggernaut", "Richochet"))

    def test_rejects_unregistered_damage(self):
        self.assertFalse(is_avoidable_damage("Immerseus", "Melee"))
        self.assertFalse(is_avoidable_damage("Malkorok", "Breath of Y'Shaarj"))
        self.assertFalse(is_avoidable_damage("General Nazgrim", "Ravager"))

    def test_exposes_registry_by_boss(self):
        mechanics = mechanics_for_boss("The Fallen Protectors")
        self.assertEqual([item.ability_name for item in mechanics], ["Noxious Poison"])
        self.assertIn("blind hatred", avoidable_ability_names("Norushen"))
        self.assertIn("General Nazgrim", covered_bosses())


if __name__ == "__main__":
    unittest.main()
