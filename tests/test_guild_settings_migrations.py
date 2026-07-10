import unittest

from data.guild_settings_migrations import (
    CURRENT_GUILD_SETTINGS_VERSION,
    UnsupportedGuildSettingsVersionError,
    migrate_guild_settings,
)


class GuildSettingsMigrationTests(unittest.TestCase):
    def test_unversioned_settings_are_migrated(self):
        migrated = migrate_guild_settings({"guild_name": "Test Guild"})

        self.assertEqual(
            migrated["config_version"], CURRENT_GUILD_SETTINGS_VERSION
        )
        self.assertEqual(migrated["hidden_weakaura_items"], [])
        self.assertEqual(migrated["raid_weekdays"], [2, 6])
        self.assertIsNone(migrated["warcraftlogs_guild_id"])
        self.assertEqual(migrated["warcraftlogs_region"], "eu")
        self.assertEqual(migrated["warcraftlogs_raid_size"], 10)

    def test_version_one_settings_are_upgraded_to_version_two(self):
        migrated = migrate_guild_settings(
            {
                "config_version": 1,
                "guild_name": "Existing Guild",
            }
        )

        self.assertEqual(migrated["config_version"], 2)
        self.assertEqual(migrated["guild_name"], "Existing Guild")
        self.assertIsNone(migrated["warcraftlogs_guild_id"])

    def test_existing_values_and_unknown_keys_are_preserved(self):
        migrated = migrate_guild_settings(
            {
                "raid_weekdays": [1, 4],
                "hidden_weakaura_items": ["optional.example"],
                "warcraftlogs_guild_id": 800007,
                "warcraftlogs_region": "eu",
                "warcraftlogs_raid_size": 10,
                "future_custom_key": {"enabled": True},
            }
        )

        self.assertEqual(migrated["raid_weekdays"], [1, 4])
        self.assertEqual(
            migrated["hidden_weakaura_items"], ["optional.example"]
        )
        self.assertEqual(migrated["warcraftlogs_guild_id"], 800007)
        self.assertEqual(migrated["future_custom_key"], {"enabled": True})

    def test_input_is_not_mutated(self):
        original = {"raid_weekdays": [2, 6]}

        migrate_guild_settings(original)

        self.assertNotIn("config_version", original)

    def test_invalid_version_is_treated_as_legacy(self):
        migrated = migrate_guild_settings({"config_version": "invalid"})

        self.assertEqual(
            migrated["config_version"], CURRENT_GUILD_SETTINGS_VERSION
        )

    def test_newer_version_is_rejected(self):
        with self.assertRaises(UnsupportedGuildSettingsVersionError):
            migrate_guild_settings(
                {"config_version": CURRENT_GUILD_SETTINGS_VERSION + 1}
            )


if __name__ == "__main__":
    unittest.main()
