from __future__ import annotations

import discord

from utils.panel_helpers import (
    safe_panel_edit,
    close_panel,
)

from utils.emoji_helpers import parse_button_emoji

from views.ui_style import get_button_style


class CloseRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            emoji=parse_button_emoji("cancel_raid"),
            style=get_button_style("common.close"),
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        await close_panel(
            interaction,
            message="Raid control closed.",
        )


class BackToRaidControlMainButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Back",
            emoji=parse_button_emoji("leave"),
            style=get_button_style("common.back"),
            row=3,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        from views.signup.raid_control.raid_control_view import (
            RaidControlView,
        )

        await safe_panel_edit(
            interaction,
            content="Raid control panel",
            view=RaidControlView(self.raid_id),
        )