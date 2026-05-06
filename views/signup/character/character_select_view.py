import asyncio
import discord

from services.character.character_service import get_user_characters
from services.signup.signup_service import set_user_spec
from services.signup.signup_ui_service import (
    refresh_and_show_signup_options_from_channel,
)
from utils.ui_timing import (
    CHARACTER_MENU_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from utils.discord_utils import delete_interaction_after
from views.signup.main.shared import parse_spec_emoji
from views.signup.character.character_add_view import AddCharacterClassView
from views.signup.character.character_manage_view import ManageCharactersView


class CharacterSelect(discord.ui.Select):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        filter_class: str | None = None,
    ):
        self.guild_id = guild_id
        self.parent_message_id = parent_message_id
        self.user_id = user_id
        self.filter_class = filter_class

        characters = get_user_characters(guild_id, user_id)

        if filter_class:
            characters = [c for c in characters if c["class"] == filter_class]

        self.filtered_characters = characters
        options = []

        for i, char in enumerate(characters):
            emoji = parse_spec_emoji(char["spec"])

            options.append(
                discord.SelectOption(
                    label=char["name"],
                    description=f"{char['class']} • {char['spec']}",
                    value=str(i),
                    emoji=emoji,
                )
            )

        options.append(
            discord.SelectOption(
                label="Add Character",
                value="add",
                emoji="➕",
            )
        )

        options.append(
            discord.SelectOption(
                label="Manage Characters",
                value="manage",
                emoji="⚙️",
            )
        )

        placeholder = "Select your saved character"
        if filter_class:
            placeholder = f"Select your {filter_class} character"

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        # ADD CHARACTER
        if value == "add":
            await interaction.response.edit_message(
                content="Choose a class to save as a character:",
                view=AddCharacterClassView(
                    self.guild_id,
                    interaction.user.id,
                    self.parent_message_id,
                    preselected_class=self.filter_class,
                ),
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction, CHARACTER_MENU_AUTO_DELETE_SECONDS
                )
            )
            return

        # MANAGE CHARACTERS
        if value == "manage":
            await interaction.response.edit_message(
                content="Manage your saved characters:",
                view=ManageCharactersView(
                    self.guild_id,
                    interaction.user.id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction, CHARACTER_MENU_AUTO_DELETE_SECONDS
                )
            )
            return

        # SELECT CHARACTER
        try:
            index = int(value)
        except ValueError:
            await interaction.response.edit_message(
                content="⚠ Invalid selection.",
                view=CharacterView(
                    self.guild_id,
                    interaction.user.id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS
                )
            )
            return

        if index >= len(self.filtered_characters):
            await interaction.response.edit_message(
                content="⚠ Character not found.",
                view=CharacterView(
                    self.guild_id,
                    interaction.user.id,
                    self.parent_message_id,
                    filter_class=self.filter_class,
                ),
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS
                )
            )
            return

        char = self.filtered_characters[index]

        ok = set_user_spec(
            raid_id=self.parent_message_id,
            user_id=str(interaction.user.id),
            selected_class=char["class"],
            selected_spec=char["spec"],
            role=char["role"],
            character_name=char["name"],
            auto_sign=True,
        )

        if not ok:
            await interaction.response.edit_message(
                content="⚠ Raid signup no longer exists.",
                view=None,
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS
                )
            )
            return

        await refresh_and_show_signup_options_from_channel(
            interaction,
            self.parent_message_id,
            interaction.user.id,
        )


class CharacterView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        filter_class: str | None = None,
    ):
        super().__init__(timeout=60)

        self.add_item(
            CharacterSelect(
                guild_id,
                user_id,
                parent_message_id,
                filter_class=filter_class,
            )
        )