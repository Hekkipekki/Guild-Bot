import asyncio
import traceback

import discord

from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)
from utils.emoji_helpers import parse_button_emoji
from views.signup.raid_control.raid_control_view import RaidControlView
from utils.discord_utils import delete_interaction_after, delete_message_after


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
                await interaction.response.send_message(
                    "⛔ You do not have access to raid control.",
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(
                        interaction,
                        ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                    )
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

            message = f"⚠ Raid Control failed: `{type(e).__name__}: {e}`"

            if interaction.response.is_done():
                msg = await interaction.followup.send(
                    message,
                    ephemeral=True,
                    wait=True,
                )
                asyncio.create_task(
                    delete_message_after(msg, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(
                        interaction,
                        ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                    )
                )