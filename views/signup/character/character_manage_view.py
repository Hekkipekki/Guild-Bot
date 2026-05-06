import asyncio
import discord

from services.character.character_service import (
    get_user_characters,
    remove_user_character,
)
from utils.ui_timing import (
    CHARACTER_MENU_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    SHORT_CONFIRMATION_DELETE_SECONDS,
)
from utils.discord_utils import delete_interaction_after
from views.signup.main.shared import parse_spec_emoji, BackToCharacterMenuButton


class RemoveCharacterSelect(discord.ui.Select):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        filter_class: str | None = None,
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_message_id = parent_message_id
        self.filter_class = filter_class

        characters = get_user_characters(guild_id, user_id)

        if filter_class:
            characters = [c for c in characters if c["class"] == filter_class]

        self.filtered_characters = characters
        options = []

        for i, char in enumerate(characters):
            options.append(
                discord.SelectOption(
                    label=char["name"],
                    description=f"{char['class']} • {char['spec']}",
                    value=str(i),
                    emoji=parse_spec_emoji(char["spec"]),
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No saved characters",
                    value="none",
                    emoji="📭",
                )
            )

        super().__init__(
            placeholder="Select character to remove",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "none":
            await interaction.response.defer()
            asyncio.create_task(
                delete_interaction_after(interaction, SHORT_CONFIRMATION_DELETE_SECONDS)
            )
            return

        try:
            selected_index = int(value)
        except ValueError:
            await interaction.response.edit_message(
                content="⚠ Invalid character selection.",
                view=ManageCharactersView(
                    self.guild_id,
                    self.user_id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        if not (0 <= selected_index < len(self.filtered_characters)):
            await interaction.response.edit_message(
                content="⚠ Character not found.",
                view=ManageCharactersView(
                    self.guild_id,
                    self.user_id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        char_to_remove = self.filtered_characters[selected_index]

        all_characters = get_user_characters(self.guild_id, self.user_id)
        real_index = next(
            (i for i, c in enumerate(all_characters) if c == char_to_remove),
            None,
        )

        if real_index is None:
            await interaction.response.edit_message(
                content="⚠ Character not found.",
                view=ManageCharactersView(
                    self.guild_id,
                    self.user_id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        removed = remove_user_character(self.guild_id, self.user_id, real_index)
        if not removed:
            await interaction.response.edit_message(
                content="⚠ Could not remove character.",
                view=ManageCharactersView(
                    self.guild_id,
                    self.user_id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"🗑 Removed **{char_to_remove['name']}**",
            view=ManageCharactersView(
                self.guild_id,
                self.user_id,
                self.parent_message_id,
                filter_class=self.filter_class,
            ),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, CHARACTER_MENU_AUTO_DELETE_SECONDS)
        )


class ManageCharactersView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        filter_class: str | None = None,
    ):
        super().__init__(timeout=60)
        self.add_item(
            RemoveCharacterSelect(
                guild_id,
                user_id,
                parent_message_id,
                filter_class=filter_class,
            )
        )
        self.add_item(
            BackToCharacterMenuButton(
                guild_id,
                user_id,
                parent_message_id,
                filter_class=filter_class,
            )
        )