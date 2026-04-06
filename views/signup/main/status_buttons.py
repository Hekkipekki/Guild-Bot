import asyncio
import discord

from services.signup.signup_service import set_user_status
from services.signup.signup_refresh_service import refresh_signup_message
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import ERROR_MESSAGE_AUTO_DELETE_SECONDS
from utils.discord_utils import delete_interaction_after, delete_message_after


NOTE_REQUIRED_STATUSES = {"late", "tentative", "absence"}


class SignupStatusButton(discord.ui.Button):
    def __init__(
        self,
        *,
        raid_id: str,
        status: str,
        label: str,
        emoji_name: str,
        style: discord.ButtonStyle,
        row: int,
    ):
        super().__init__(
            label=label,
            emoji=parse_button_emoji(emoji_name),
            style=style,
            custom_id=f"signup:{status}:{raid_id}",
            row=row,
        )
        self.raid_id = raid_id
        self.status = status

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This action can only be used inside a server.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        if self.status in NOTE_REQUIRED_STATUSES:
            from views.signup.main.status_note_modal import RequiredStatusNoteModal

            await interaction.response.send_modal(
                RequiredStatusNoteModal(
                    raid_id=int(self.raid_id),
                    guild_id=guild.id,
                    user_id=interaction.user.id,
                    status=self.status,
                )
            )
            return

        ok, error_message = set_user_status(
            raid_id=int(self.raid_id),
            user_id=str(interaction.user.id),
            status=self.status,
            display_name=interaction.user.display_name,
        )

        if not ok:
            await interaction.response.send_message(
                error_message or "⚠ Could not update signup status.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.defer()

        refreshed = await refresh_signup_message(interaction, int(self.raid_id))
        if not refreshed:
            msg = await interaction.followup.send(
                "⚠ Status updated, but the raid signup could not be refreshed.",
                ephemeral=True,
                wait=True,
            )
            asyncio.create_task(
                delete_message_after(msg, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )