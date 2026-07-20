import unittest
from unittest.mock import patch

from views.raid_builder.raid_builder_helpers import build_signup_from_raid_data


class RaidBuilderSchedulingSyncTests(unittest.TestCase):
    @patch("views.raid_builder.raid_builder_helpers.apply_scheduled_absences_to_signup")
    @patch("views.raid_builder.raid_builder_helpers.build_signup_payload")
    def test_newly_posted_raid_applies_matching_scheduling_absences(
        self,
        build_signup_payload_mock,
        apply_absences_mock,
    ):
        signup = {
            "guild_id": 123,
            "start_ts": 0,
            "users": {},
        }
        build_signup_payload_mock.return_value = signup
        apply_absences_mock.return_value = 1

        ok, result, error = build_signup_from_raid_data(
            123,
            {
                "title": "HC SoO",
                "description": "Raid",
                "leader": "Leader",
                "date": "2026-07-22",
                "time": "19:30",
                "channel_id": 456,
                "is_recurring": False,
                "recurring_interval_days": None,
            },
        )

        self.assertTrue(ok)
        self.assertIs(result, signup)
        self.assertIsNone(error)
        apply_absences_mock.assert_called_once_with(signup)

    @patch("views.raid_builder.raid_builder_helpers.apply_scheduled_absences_to_signup")
    @patch("views.raid_builder.raid_builder_helpers.build_signup_payload")
    def test_initial_recurring_raid_also_applies_scheduling_absences(
        self,
        build_signup_payload_mock,
        apply_absences_mock,
    ):
        signup = {
            "guild_id": 123,
            "start_ts": 0,
            "users": {},
        }
        build_signup_payload_mock.return_value = signup

        ok, result, error = build_signup_from_raid_data(
            123,
            {
                "title": "HC SoO",
                "description": "Raid",
                "leader": "Leader",
                "date": "2026-07-22",
                "time": "19:30",
                "channel_id": 456,
                "is_recurring": True,
                "recurring_interval_days": 7,
            },
        )

        self.assertTrue(ok)
        self.assertIs(result, signup)
        self.assertIsNone(error)
        self.assertTrue(signup["is_recurring"])
        apply_absences_mock.assert_called_once_with(signup)


if __name__ == "__main__":
    unittest.main()
