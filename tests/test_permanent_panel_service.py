import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from services.panels.permanent_panel_service import (
    PermanentPanelDefinition,
    _candidate_message_ids,
    ensure_permanent_panel,
)


class PermanentPanelHelpersTests(unittest.TestCase):
    def test_candidate_message_ids_normalizes_and_deduplicates(self):
        self.assertEqual(
            _candidate_message_ids([None, "", 0, "42", 42, "bad", 99]),
            [42, 99],
        )


class PermanentPanelLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock()
        self.guild.id = 123
        self.channel = Mock()
        self.channel.id = 456
        self.channel.fetch_message = AsyncMock()
        self.channel.send = AsyncMock()
        self.saved_ids = []

    def definition(self, **overrides):
        values = {
            "key": "test",
            "label": "Test",
            "get_channel_id": lambda guild_id: 456,
            "get_message_ids": lambda guild_id: (789,),
            "set_message_id": lambda guild_id, message_id: self.saved_ids.append(message_id),
            "build_payload": lambda guild: {"content": "hello", "view": None},
        }
        values.update(overrides)
        return PermanentPanelDefinition(**values)

    async def test_updates_existing_message(self):
        message = Mock()
        message.id = 789
        message.edit = AsyncMock()
        self.channel.fetch_message.return_value = message

        with patch(
            "services.panels.permanent_panel_service._resolve_channel",
            new=AsyncMock(return_value=self.channel),
        ):
            ok, detail = await ensure_permanent_panel(Mock(), self.guild, self.definition())

        self.assertTrue(ok)
        self.assertEqual(detail, "Test panel updated.")
        message.edit.assert_awaited_once_with(content="hello", view=None)
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.saved_ids, [789])

    async def test_uses_secondary_message_id_before_creating(self):
        message = Mock()
        message.id = 222
        message.edit = AsyncMock()
        not_found = discord.NotFound(Mock(status=404, reason="Not Found"), "missing")
        self.channel.fetch_message.side_effect = [not_found, message]
        definition = self.definition(get_message_ids=lambda guild_id: (111, 222))

        with patch(
            "services.panels.permanent_panel_service._resolve_channel",
            new=AsyncMock(return_value=self.channel),
        ):
            ok, _ = await ensure_permanent_panel(Mock(), self.guild, definition)

        self.assertTrue(ok)
        self.assertEqual(self.channel.fetch_message.await_count, 2)
        self.assertEqual(self.saved_ids, [222])

    async def test_creates_panel_when_stored_message_is_missing(self):
        not_found = discord.NotFound(Mock(status=404, reason="Not Found"), "missing")
        self.channel.fetch_message.side_effect = not_found
        posted = Mock()
        posted.id = 999
        self.channel.send.return_value = posted

        with patch(
            "services.panels.permanent_panel_service._resolve_channel",
            new=AsyncMock(return_value=self.channel),
        ):
            ok, detail = await ensure_permanent_panel(Mock(), self.guild, self.definition())

        self.assertTrue(ok)
        self.assertEqual(detail, "Test panel posted.")
        self.channel.send.assert_awaited_once_with(content="hello", view=None)
        self.assertEqual(self.saved_ids, [None, 999])

    async def test_runs_prepare_hook_before_building_payload(self):
        calls = []

        async def prepare(guild, channel):
            calls.append("prepare")

        def build_payload(guild):
            calls.append("build")
            return {"content": "hello"}

        message = Mock()
        message.id = 789
        message.edit = AsyncMock()
        self.channel.fetch_message.return_value = message
        definition = self.definition(prepare=prepare, build_payload=build_payload)

        with patch(
            "services.panels.permanent_panel_service._resolve_channel",
            new=AsyncMock(return_value=self.channel),
        ):
            await ensure_permanent_panel(Mock(), self.guild, definition)

        self.assertEqual(calls, ["prepare", "build"])

    async def test_applies_suppress_flags_for_edit_and_send(self):
        message = Mock()
        message.id = 789
        message.edit = AsyncMock()
        self.channel.fetch_message.return_value = message
        definition = self.definition(suppress_embeds=True)

        with patch(
            "services.panels.permanent_panel_service._resolve_channel",
            new=AsyncMock(return_value=self.channel),
        ):
            await ensure_permanent_panel(Mock(), self.guild, definition)

        message.edit.assert_awaited_once_with(content="hello", view=None, suppress=True)


if __name__ == "__main__":
    unittest.main()
