from __future__ import annotations

import asyncio
import traceback

import discord

from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.emoji_helpers import parse_button_emoji
from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


class CompControlButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Comp Control",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            custom_id=f"comp_control:{raid_id}",
            row=0,
        )
        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        try:
            if not can_manage_raid_tools(interaction):
                await interaction.response.send_message(
                    "⛔ You do not have access to comp control.",
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )
                return

            from views.signup.comp.comp_control_view import CompControlView

            await interaction.response.send_message(
                "Comp control panel",
                view=CompControlView(self.raid_id),
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
            )

        except Exception as e:
            print("\n[CompControlButton] Failed to open comp control")
            print(f"Raid ID: {self.raid_id}")
            print(f"Exception: {type(e).__name__}: {e}")
            traceback.print_exc()

            message = f"⚠ Comp Control failed: `{type(e).__name__}: {e}`"

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
                await interaction.response.send_message(message, ephemeral=True)
                asyncio.create_task(
                    delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )


class CompMessageView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=None)
        self.raid_id = str(raid_id)
        self.add_item(CompControlButton(self.raid_id))