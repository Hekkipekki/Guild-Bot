import asyncio
import discord

from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)
from utils.emoji_helpers import parse_button_emoji
from views.signup.raid_control.raid_control_view import RaidControlView
from utils.discord_utils import delete_interaction_after


class RaidControlButton(discord.ui.Button):
    def __init__(self, raid_id: str, row: int = 1):
        super().__init__(
            label="Raid Control",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id=f"raid_control:{raid_id}",
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await interaction.response.send_message(
                "You do not have access to raid controls.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        view = RaidControlView(self.raid_id)

        await interaction.response.send_message(
            "Raid control panel",
            view=view,
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )