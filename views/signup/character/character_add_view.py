import asyncio
import discord
import config

from services.character.character_service import add_user_character
from services.signup.signup_service import set_user_spec
from services.signup.signup_ui_service import (
    refresh_and_show_signup_options_from_channel,
)
from utils.ui_timing import (
    CHARACTER_MENU_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from utils.discord_utils import delete_interaction_after
from views.signup.main.shared import (
    parse_spec_emoji,
    parse_class_emoji,
    BackToCharacterMenuButton,
)


def prettify_character_name(spec: str, wow_class: str) -> str:
    pretty_spec = {
        "ProtectionWarrior": "Protection",
        "HolyPaladin": "Holy",
        "ProtectionPaladin": "Protection",
        "RestorationDruid": "Restoration",
        "HolyPriest": "Holy",
        "RestorationShaman": "Restoration",
        "FrostDK": "Frost",
    }.get(spec, spec)

    return f"{pretty_spec} {wow_class}"


class NewCharacterNameModal(discord.ui.Modal):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        selected_class: str,
        selected_spec: str,
        role: str,
        filter_class: str | None = None,
    ):
        super().__init__(title="Set Character Name")

        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_message_id = parent_message_id
        self.selected_class = selected_class
        self.selected_spec = selected_spec
        self.role = role
        self.filter_class = filter_class

        default_name = prettify_character_name(selected_spec, selected_class)

        self.name_input = discord.ui.TextInput(
            label="Character Name",
            placeholder="Enter your character name",
            default=default_name,
            max_length=32,
            required=True,
        )

        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        character_name = str(self.name_input).strip()

        char = {
            "name": character_name,
            "class": self.selected_class,
            "spec": self.selected_spec,
            "role": self.role,
        }

        added = add_user_character(self.guild_id, interaction.user.id, char)

        if not added:
            from views.signup.character.character_select_view import CharacterView

            await interaction.response.send_message(
                f"⚠ **{char['name']}** is already saved.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        ok = set_user_spec(
            raid_id=self.parent_message_id,
            user_id=str(interaction.user.id),
            selected_class=self.selected_class,
            selected_spec=self.selected_spec,
            role=self.role,
            character_name=character_name,
            auto_sign=True,
            display_name=interaction.user.display_name,
        )

        if not ok:
            await interaction.response.send_message(
                "⚠ Raid signup no longer exists.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await refresh_and_show_signup_options_from_channel(
            interaction,
            self.parent_message_id,
            interaction.user.id,
        )


class AddCharacterClassSelect(discord.ui.Select):
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

        options = [
            discord.SelectOption(
                label=class_name,
                value=class_name,
                emoji=parse_class_emoji(class_name),
            )
            for class_name in config.CLASSES
        ]

        super().__init__(
            placeholder="Select class to add",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_class = self.values[0]

        await safe_panel_edit(
            content=f"Choose a spec for **{selected_class}**:",
            view=AddCharacterSpecView(
                self.guild_id,
                self.user_id,
                self.parent_message_id,
                selected_class,
                filter_class=selected_class,
            ),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, CHARACTER_MENU_AUTO_DELETE_SECONDS)
        )


class AddCharacterSpecSelect(discord.ui.Select):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        selected_class: str,
        filter_class: str | None = None,
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.parent_message_id = parent_message_id
        self.selected_class = selected_class
        self.filter_class = filter_class

        options = [
            discord.SelectOption(
                label=spec,
                value=spec,
                description=f"Role: {role}",
                emoji=parse_spec_emoji(spec),
            )
            for spec, role in config.CLASS_SPECS[selected_class].items()
        ]

        super().__init__(
            placeholder=f"Select spec for {selected_class}",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_spec = self.values[0]
        role = config.CLASS_SPECS[self.selected_class][selected_spec]

        await interaction.response.send_modal(
            NewCharacterNameModal(
                self.guild_id,
                self.user_id,
                self.parent_message_id,
                self.selected_class,
                selected_spec,
                role,
                filter_class=self.filter_class,
            )
        )


class AddCharacterClassView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        preselected_class: str | None = None,
    ):
        super().__init__(timeout=60)

        if preselected_class:
            self.add_item(
                AddCharacterSpecSelect(
                    guild_id=guild_id,
                    user_id=user_id,
                    parent_message_id=parent_message_id,
                    selected_class=preselected_class,
                    filter_class=preselected_class,
                )
            )
        else:
            self.add_item(
                AddCharacterClassSelect(
                    guild_id,
                    user_id,
                    parent_message_id,
                )
            )

        self.add_item(
            BackToCharacterMenuButton(
                guild_id,
                user_id,
                parent_message_id,
                filter_class=preselected_class,
            )
        )


class AddCharacterSpecView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        user_id: int,
        parent_message_id: int,
        selected_class: str,
        filter_class: str | None = None,
    ):
        super().__init__(timeout=60)

        self.add_item(
            AddCharacterSpecSelect(
                guild_id,
                user_id,
                parent_message_id,
                selected_class,
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