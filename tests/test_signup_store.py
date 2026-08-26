import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data.signup_store import (
    load_signups,
    remove_signup_by_message_id,
    save_signups,
)


class SignupStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.guilds_root = Path(self.temp_dir.name) / "guilds"
        self.guilds_root_patch = patch(
            "data.guild_data.GUILDS_ROOT",
            self.guilds_root,
        )
        self.guilds_root_patch.start()

    def tearDown(self):
        self.guilds_root_patch.stop()
        self.temp_dir.cleanup()

    def _signup(self, guild_id: str, title: str) -> dict:
        return {
            "guild_id": guild_id,
            "channel_id": "456",
            "title": title,
            "start_ts": 1,
            "users": {},
        }

    def _read_guild_signups(self, guild_id: str) -> dict:
        path = self.guilds_root / guild_id / "signups.json"
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def test_global_save_clears_file_when_last_signup_is_removed(self):
        guild_id = "123"
        save_signups({"raid-1": self._signup(guild_id, "Expired raid")})

        removed = remove_signup_by_message_id("raid-1")

        self.assertTrue(removed)
        self.assertEqual(self._read_guild_signups(guild_id), {})
        self.assertEqual(load_signups(), {})

    def test_global_save_clears_only_affected_guild(self):
        first_guild_id = "123"
        second_guild_id = "789"
        save_signups(
            {
                "raid-1": self._signup(first_guild_id, "Expired raid"),
                "raid-2": self._signup(second_guild_id, "Future raid"),
            }
        )

        removed = remove_signup_by_message_id("raid-1")

        self.assertTrue(removed)
        self.assertEqual(self._read_guild_signups(first_guild_id), {})
        self.assertEqual(
            self._read_guild_signups(second_guild_id),
            {"raid-2": self._signup(second_guild_id, "Future raid")},
        )


if __name__ == "__main__":
    unittest.main()
