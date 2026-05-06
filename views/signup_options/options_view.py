import asyncio
import discord
import config

from services.signup.signup_service import remove_user_signup
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.ui_timing import SHORT_CONFIRMATION_DELETE_SECONDS
from utils.discord_utils import delete_interaction_after

from .helpers import get_signup_entry
from .modals import EditNameModal, EditNoteModal
from .spec_edit_view import EditSpecView


class EditNameButton(discord.ui.Button):
    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__(
            label="Edit Name",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            EditNameModal(self.guild_id, self.raid_id, self.user_id)
        )


class EditSpecButton(discord.ui.Button):
    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__(
            label="Edit Spec",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        entry = get_signup_entry(self.raid_id, str(self.user_id))
        if not entry:
            await interaction.response.send_message("Signup not found.", ephemeral=True)
            return

        selected_class = entry.get("class")
        if not selected_class or selected_class not in config.CLASS_SPECS:
            await interaction.response.send_message(
                "Class not found for this signup.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content="Choose a new spec:",
            embed=None,
            view=EditSpecView(self.guild_id, self.raid_id, self.user_id, selected_class),
        )


class EditNoteButton(discord.ui.Button):
    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__(
            label="Edit Note",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            EditNoteModal(self.guild_id, self.raid_id, self.user_id)
        )


class RemoveSignupButton(discord.ui.Button):
    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__(
            label="Remove Signup",
            style=discord.ButtonStyle.danger,
            row=1,
        )
        self.guild_id = guild_id
        self.raid_id = raid_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        removed = remove_user_signup(
            raid_id=self.raid_id,
            user_id=str(self.user_id),
        )

        if not removed:
            await interaction.response.edit_message(
                content="⚠ Signup not found or already removed.",
                embed=None,
                view=None,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, SHORT_CONFIRMATION_DELETE_SECONDS)
            )
            return

        try:
            await refresh_signup_message_by_id(interaction.channel, self.raid_id)
        except Exception:
            pass

        await interaction.response.edit_message(
            content="❌ Signup removed.",
            embed=None,
            view=None,
        )

        asyncio.create_task(
            delete_interaction_after(interaction, SHORT_CONFIRMATION_DELETE_SECONDS)
        )


class SignupOptionsView(discord.ui.View):
    def __init__(self, guild_id: int, raid_id: int, user_id: int):
        super().__init__(timeout=90)
        self.add_item(EditNameButton(guild_id, raid_id, user_id))
        self.add_item(EditSpecButton(guild_id, raid_id, user_id))
        self.add_item(EditNoteButton(guild_id, raid_id, user_id))
        self.add_item(RemoveSignupButton(guild_id, raid_id, user_id))