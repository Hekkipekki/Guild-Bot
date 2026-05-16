from __future__ import annotations

import asyncio
import traceback

import discord

from utils.permissions import can_manage_raid_tools

from utils.ui_timing import (
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)

from utils.emoji_helpers import (
    parse_button_emoji,
)

from utils.discord_utils import (
    delete_interaction_after,
)

from utils.panel_helpers import (
    send_panel_error,
)

from views.signup.raid_control.raid_control_view import (
    RaidControlView,
)
from views.signup.raid_control.raid_control_notes import (
    OpenNotesButton,
)


class RaidControlButton(discord.ui.Button):
    def __init__(self, raid_id: str, row: int = 1):
        super().__init__(
            label="Raid Control",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id=f"raid_control:{raid_id}",
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        try:
            if not can_manage_raid_tools(interaction):
                await send_panel_error(
                    interaction,
                    "⛔ You do not have access to raid control.",
                )
                return

            view = RaidControlView(self.raid_id)

            await interaction.response.send_message(
                "Raid control panel",
                view=view,
                ephemeral=True,
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction,
                    RAID_CONTROL_AUTO_DELETE_SECONDS,
                )
            )

        except Exception as e:
            print("\n[RaidControlButton] Failed to open raid control")
            print(f"Raid ID: {self.raid_id}")
            print(f"Exception: {type(e).__name__}: {e}")
            traceback.print_exc()

            await send_panel_error(
                interaction,
                f"⚠ Raid Control failed: `{type(e).__name__}: {e}`",
            )
