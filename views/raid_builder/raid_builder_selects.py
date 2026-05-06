import asyncio
import discord

from services.raid.raid_template_service import (
    list_templates,
    build_raid_data_from_template,
    delete_template,
)
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    RAID_CONTROL_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from views.raid_builder.raid_builder_helpers import build_preview_embed


class RaidChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, raid_data: dict):
        self.raid_data = dict(raid_data)

        super().__init__(
            placeholder="Select channel to post the raid in...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        channel = self.values[0]
        self.raid_data["channel_id"] = channel.id

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidTemplateSelect(discord.ui.Select):
    def __init__(self, guild_id: int, channel_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.templates = list_templates(guild_id)

        options = []
        for template in self.templates[:25]:
            options.append(
                discord.SelectOption(
                    label=template.get("name", "Unnamed Template")[:100],
                    description=template.get("title", "Raid Template")[:100],
                    value=template.get("name", ""),
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No saved templates",
                    description="Save a template first in the raid builder.",
                    value="__none__",
                )
            )

        super().__init__(
            placeholder="Select a saved template...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import TemplateDateModal

        selected_name = self.values[0]

        if selected_name == "__none__":
            await interaction.response.send_message(
                "⚠ No templates are saved for this server yet.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.send_modal(
            TemplateDateModal(self.guild_id, self.channel_id, selected_name)
        )


class DeleteTemplateSelect(discord.ui.Select):
    def __init__(self, guild_id: int, channel_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.templates = list_templates(guild_id)

        options = []
        for template in self.templates[:25]:
            options.append(
                discord.SelectOption(
                    label=template.get("name", "Unnamed Template")[:100],
                    description=template.get("title", "Raid Template")[:100],
                    value=template.get("name", ""),
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No saved templates",
                    description="Nothing to delete.",
                    value="__none__",
                )
            )

        super().__init__(
            placeholder="Select a template to delete...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidTemplateView

        selected_name = self.values[0]

        if selected_name == "__none__":
            await interaction.response.send_message(
                "⚠ No templates are saved for this server yet.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        ok = delete_template(self.guild_id, selected_name)
        if not ok:
            await interaction.response.send_message(
                "⚠ Could not delete that template.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"✅ Deleted template **{selected_name}**.",
            embed=None,
            view=RaidTemplateView(self.guild_id, self.channel_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )