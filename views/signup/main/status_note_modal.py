import asyncio
import discord

from services.signup.signup_service import (
    get_signup_user,
    set_user_status_with_note,
)
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
)
from views.signup_options.embeds import build_signup_options_embed
from views.signup_options.options_view import SignupOptionsView


class RequiredStatusNoteModal(discord.ui.Modal):
    def __init__(self, *, raid_id: int, guild_id: int, user_id: int, status: str):
        if status == "late":
            title = "Late Note"
        elif status == "tentative":
            title = "Tentative Note"
        else:
            title = "Absence Note"

        super().__init__(title=title)

        self.raid_id = raid_id
        self.guild_id = guild_id
        self.user_id = user_id
        self.status = status

        existing_entry = get_signup_user(self.raid_id, str(self.user_id)) or {}
        existing_note = (existing_entry.get("note") or "").strip()

        self.note_input = discord.ui.TextInput(
            label="Note",
            placeholder="Example: 10 min late, work, traffic, family, etc.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200,
            default=existing_note,
        )
        self.add_item(self.note_input)

    async def _send_error(self, interaction: discord.Interaction, message: str) -> None:
        if interaction.response.is_done():
            return

        await interaction.response.send_message(message, ephemeral=True)
        asyncio.create_task(
            delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )

    async def on_submit(self, interaction: discord.Interaction):
        ok, error_message = set_user_status_with_note(
            raid_id=self.raid_id,
            user_id=str(self.user_id),
            status=self.status,
            note=str(self.note_input).strip(),
        )

        if not ok:
            await self._send_error(
                interaction,
                error_message or "⚠ Could not update signup status.",
            )
            return

        refreshed = await refresh_signup_message_by_id(interaction.channel, self.raid_id)
        if not refreshed:
            await self._send_error(
                interaction,
                "⚠ Status updated, but the raid signup could not be refreshed.",
            )
            return

        updated_entry = get_signup_user(self.raid_id, str(self.user_id))
        if not updated_entry:
            await self._send_error(interaction, "⚠ Signup not found.")
            return

        await interaction.response.send_message(
            embed=build_signup_options_embed(updated_entry),
            view=SignupOptionsView(self.guild_id, self.raid_id, self.user_id),
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SIGNUP_OPTIONS_AUTO_DELETE_SECONDS)
        )