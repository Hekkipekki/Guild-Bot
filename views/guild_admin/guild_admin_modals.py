import asyncio
import discord

from services.guild.guild_settings_service import set_default_description
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    RAID_CONTROL_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from views.guild_admin.guild_admin_helpers import build_guild_config_embed


class EditDefaultDescriptionModal(discord.ui.Modal, title="Edit Raid Description Template"):
    new_description = discord.ui.TextInput(
        label="Raid Description Template",
        placeholder="Example: Be online 10 minutes early, flasks and food required.",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        set_default_description(self.guild_id, str(self.new_description).strip())

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        from views.guild_admin.guild_admin_view import GuildAdminView

        await interaction.response.edit_message(
            content=None,
            embed=build_guild_config_embed(guild),
            view=GuildAdminView(),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )