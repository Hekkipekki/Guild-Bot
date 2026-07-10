import unittest

from services.bot.command_sync_service import build_command_sync_plan


class CommandSyncPlanTests(unittest.TestCase):
    def test_production_uses_global_sync(self):
        plan = build_command_sync_plan(dev_mode=False, test_guild_id=None)

        self.assertTrue(plan.is_global_sync)
        self.assertFalse(plan.is_guild_sync)
        self.assertIsNone(plan.guild_id)

    def test_development_uses_test_guild_only(self):
        plan = build_command_sync_plan(
            dev_mode=True,
            test_guild_id="1480200690654777466",
        )

        self.assertTrue(plan.is_guild_sync)
        self.assertFalse(plan.is_global_sync)
        self.assertEqual(plan.guild_id, 1480200690654777466)

    def test_development_requires_test_guild(self):
        with self.assertRaises(RuntimeError):
            build_command_sync_plan(dev_mode=True, test_guild_id=None)

    def test_development_rejects_invalid_test_guild(self):
        with self.assertRaises(RuntimeError):
            build_command_sync_plan(dev_mode=True, test_guild_id="not-a-guild")

    def test_development_rejects_non_positive_test_guild(self):
        with self.assertRaises(RuntimeError):
            build_command_sync_plan(dev_mode=True, test_guild_id=0)


if __name__ == "__main__":
    unittest.main()
