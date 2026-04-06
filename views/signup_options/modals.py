import asyncio
import discord

from services.character.character_service import update_character_name
from services.signup.signup_service import (
    update_user_name,
    update_user_note,
)
from services.signup.signup_ui_service import (
    refresh_main_signup_from_channel,
    replace_signup_options_panel,
)
from utils.ui_timing import (
    SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from .helpers import get_signup_entry
from utils.discord_utils import delete_interaction_after


async def _show_modal_error(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        return

    await interaction.response.send_message(message, ephemeral=True)
    asyncio.create_task(
        delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
    )


class EditNameModal(discord.ui.Modal, title="Edit Character Name"):
    new_name = discord.ui.TextInput(
        label="Character Name",
        placeholder="Enter your in-game name",
        max_length=32,
    )

    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        entry = get_signup_entry(self.raid_id, str(self.user_id))
        if not entry:
            await _show_modal_error(interaction, "Signup not found.")
            return

        new_name = str(self.new_name).strip()
        class_name = entry.get("class")

        ok = update_user_name(
            raid_id=self.raid_id,
            user_id=str(self.user_id),
            new_name=new_name,
        )

        if not ok:
            await _show_modal_error(interaction, "Signup not found.")
            return

        if class_name:
            update_character_name(
                self.guild_id,
                self.user_id,
                class_name,
                new_name,
            )

        refreshed = await refresh_main_signup_from_channel(interaction, self.raid_id)
        if not refreshed:
            return

        replaced = await replace_signup_options_panel(
            interaction,
            self.raid_id,
            self.user_id,
            delete_after=SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
        )
        if not replaced:
            await _show_modal_error(
                interaction,
                "⚠ Name updated, but could not refresh signup options.",
            )


class EditNoteModal(discord.ui.Modal, title="Edit Note"):
    new_note = discord.ui.TextInput(
        label="Note",
        placeholder="Optional note for raid leader",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200,
    )

    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        ok = update_user_note(
            raid_id=self.raid_id,
            user_id=str(self.user_id),
            note=str(self.new_note).strip(),
        )

        if not ok:
            await _show_modal_error(interaction, "Signup not found.")
            return

        refreshed = await refresh_main_signup_from_channel(interaction, self.raid_id)
        if not refreshed:
            return

        replaced = await replace_signup_options_panel(
            interaction,
            self.raid_id,
            self.user_id,
            delete_after=SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
        )
        if not replaced:
            await _show_modal_error(
                interaction,
                "⚠ Note updated, but could not refresh signup options.",
            )