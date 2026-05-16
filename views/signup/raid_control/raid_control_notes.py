from __future__ import annotations

import discord

from services.raid.raid_control_service import get_players

from utils.panel_helpers import safe_panel_edit
from utils.emoji_helpers import parse_button_emoji

from views.ui_style import get_button_style
from views.signup.raid_control.raid_control_navigation import (
    BackToRaidControlMainButton,
)


def build_notes_content(raid_id: str) -> str:
    players = get_players(raid_id)

    lines: list[str] = ["**Raid Notes**\n"]

    found_note = False

    for player in players:
        note = (player.get("note") or "").strip()

        if not note:
            continue

        found_note = True

        name = (
            (player.get("name") or "").strip()
            or (player.get("display_name") or "").strip()
            or "Unknown"
        )

        status = player.get("status") or "Unknown"

        lines.append(
            f"**{name}** — `{status}`\n"
            f"> {note}"
        )

    if not found_note:
        lines.append("No player notes for this raid.")

    return "\n\n".join(lines)


class RaidControlNotesView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.raid_id = str(raid_id)

        self.add_item(
            BackToRaidControlMainButton(self.raid_id)
        )


class OpenNotesButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Note",
            emoji=parse_button_emoji("note"),
            style=get_button_style("raid_control.note"),
            row=2,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content=build_notes_content(self.raid_id),
            view=RaidControlNotesView(self.raid_id),
        )