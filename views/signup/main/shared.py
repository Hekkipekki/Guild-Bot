import asyncio
import discord

from utils.emoji_helpers import parse_spec_emoji, parse_class_emoji
from utils.ui_timing import (
    CHARACTER_MENU_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from utils.discord_utils import delete_interaction_after


class BackToCharacterMenuButton(discord.ui.Button):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        filter_class: str | None = None,
    ):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="↩️",
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_message_id = parent_message_id
        self.filter_class = filter_class

    async def callback(self, interaction: discord.Interaction):
        from views.signup.character.character_select_view import CharacterView

        try:
            await interaction.response.edit_message(
                content="Select your saved character:",
                view=CharacterView(
                    self.guild_id,
                    self.user_id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )
            asyncio.create_task(
                delete_interaction_after(
                    interaction,
                    CHARACTER_MENU_AUTO_DELETE_SECONDS,
                )
            )
        except Exception:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠ Could not reopen character menu.",
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(
                        interaction,
                        ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                    )
                )