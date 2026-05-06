import asyncio
import discord

from services.raid.raid_template_service import overwrite_template
from services.signup.signup_message_service import send_signup_message
from utils.emoji_helpers import parse_button_emoji
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    RAID_CONTROL_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from views.raid_builder.raid_builder_helpers import (
    default_raid_data,
    build_preview_embed,
    build_signup_from_raid_data,
)


class EditTitleButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Edit Title", style=discord.ButtonStyle.secondary, row=0)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RaidTitleModal
        await interaction.response.send_modal(RaidTitleModal(self.raid_data))


class EditDescriptionButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Edit Description", style=discord.ButtonStyle.secondary, row=0)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RaidDescriptionModal
        await interaction.response.send_modal(RaidDescriptionModal(self.raid_data))


class EditLeaderButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Edit Leader", style=discord.ButtonStyle.secondary, row=0)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RaidLeaderModal
        await interaction.response.send_modal(RaidLeaderModal(self.raid_data))


class EditDateButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Edit Date", style=discord.ButtonStyle.secondary, row=1)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RaidDateModal
        await interaction.response.send_modal(RaidDateModal(self.raid_data))


class EditTimeButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Edit Time", style=discord.ButtonStyle.secondary, row=1)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RaidTimeModal
        await interaction.response.send_modal(RaidTimeModal(self.raid_data))


class RecurringRaidButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(label="Recurring Raid", style=discord.ButtonStyle.secondary, row=1)
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import RecurringRaidModal
        await interaction.response.send_modal(RecurringRaidModal(self.raid_data))


class SaveTemplateButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(
            label="Save Template",
            emoji=parse_button_emoji("create_template"),
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_modals import SaveTemplateModal

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            SaveTemplateModal(guild.id, self.raid_data)
        )


class OverwriteTemplateButton(discord.ui.Button):
    def __init__(self, raid_data: dict, template_name: str):
        super().__init__(
            label=f"Overwrite: {template_name[:40]}",
            emoji=parse_button_emoji("submit_raid"),
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        self.raid_data = dict(raid_data)
        self.template_name = template_name

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        ok = overwrite_template(guild.id, self.template_name, self.raid_data)

        if not ok:
            await interaction.response.send_message(
                "⚠ Could not overwrite template.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"✅ Template **{self.template_name}** overwritten.",
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class PostRaidButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(
            label="Post Raid",
            emoji=parse_button_emoji("submit_raid"),
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        ok, signup, error = build_signup_from_raid_data(guild.id, self.raid_data)
        if not ok or signup is None:
            await interaction.response.send_message(
                f"⚠ {error or 'Could not build raid signup.'}",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        channel_id = self.raid_data.get("channel_id")
        target_channel = guild.get_channel(channel_id)
        if target_channel is None:
            try:
                target_channel = await guild.fetch_channel(channel_id)
            except Exception:
                target_channel = None

        if target_channel is None:
            await interaction.response.send_message(
                "⚠ Could not find the selected channel.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        class _ChannelCtx:
            def __init__(self, channel):
                self.channel = channel

            async def send(self, *args, **kwargs):
                return await self.channel.send(*args, **kwargs)

        ok = await send_signup_message(_ChannelCtx(target_channel), signup)

        if not ok:
            await interaction.response.send_message(
                "⚠ Failed to create signup message.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content="✅ Raid signup posted.",
            embed=None,
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class BackToRaidStartButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidStartView

        guild = interaction.guild
        channel = interaction.channel

        if guild is None or channel is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content="Raid setup",
            embed=None,
            view=RaidStartView(guild.id, channel.id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CancelRaidBuilderButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Cancel",
            emoji=parse_button_emoji("cancel_raid"),
            style=discord.ButtonStyle.secondary,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Raid creation cancelled.",
            embed=None,
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CreateNewRaidButton(discord.ui.Button):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(
            label="Create New Raid",
            emoji=parse_button_emoji("create_raid"),
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        raid_data = default_raid_data(self.guild_id, self.channel_id)

        await interaction.response.edit_message(
            content=None,
            embed=build_preview_embed(guild, raid_data),
            view=RaidBuilderView(raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class UseTemplateButton(discord.ui.Button):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(
            label="Use Template",
            emoji=parse_button_emoji("create_template"),
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidTemplateView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await interaction.response.edit_message(
            content=None,
            embed=None,
            view=RaidTemplateView(self.guild_id, self.channel_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class DeleteTemplateButton(discord.ui.Button):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(
            label="Delete a Template",
            emoji=parse_button_emoji("cancel_raid"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import DeleteTemplateView

        await interaction.response.edit_message(
            content="Select a template to delete:",
            embed=None,
            view=DeleteTemplateView(self.guild_id, self.channel_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CancelRaidStartButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Cancel",
            emoji=parse_button_emoji("cancel_raid"),
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Raid setup cancelled.",
            embed=None,
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class BackFromTemplateButton(discord.ui.Button):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(label="Back", style=discord.ButtonStyle.secondary, row=1)
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidStartView

        await interaction.response.edit_message(
            content="Raid setup",
            embed=None,
            view=RaidStartView(self.guild_id, self.channel_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )