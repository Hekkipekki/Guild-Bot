import asyncio
import discord

from services.raid.raid_template_service import (
    save_template,
    build_raid_data_from_template,
)
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    RAID_CONTROL_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)
from views.raid_builder.raid_builder_helpers import build_preview_embed


class RaidTitleModal(discord.ui.Modal, title="Edit Raid Title"):
    new_title = discord.ui.TextInput(
        label="Raid Title",
        placeholder="Enter raid title",
        max_length=100,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        self.raid_data["title"] = str(self.new_title).strip()

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidDescriptionModal(discord.ui.Modal, title="Edit Raid Description"):
    new_description = discord.ui.TextInput(
        label="Raid Description",
        placeholder="Enter raid description",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        self.raid_data["description"] = str(self.new_description).strip()

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidLeaderModal(discord.ui.Modal, title="Edit Raid Leader"):
    new_leader = discord.ui.TextInput(
        label="Raid Leader",
        placeholder="Enter raid leader",
        max_length=100,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        self.raid_data["leader"] = str(self.new_leader).strip()

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidDateModal(discord.ui.Modal, title="Edit Raid Date"):
    new_date = discord.ui.TextInput(
        label="Raid Date",
        placeholder="YYYY-MM-DD",
        max_length=10,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        self.raid_data["date"] = str(self.new_date).strip()

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidTimeModal(discord.ui.Modal, title="Edit Raid Time"):
    new_time = discord.ui.TextInput(
        label="Raid Time",
        placeholder="HH:MM",
        max_length=5,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        self.raid_data["time"] = str(self.new_time).strip()

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RecurringRaidModal(discord.ui.Modal, title="Recurring Raid Settings"):
    interval_days = discord.ui.TextInput(
        label="Repeat every X days",
        placeholder="Example: 7 (leave blank to disable)",
        max_length=3,
        required=False,
    )

    def __init__(self, raid_data: dict):
        super().__init__()
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        raw = str(self.interval_days).strip()

        if not raw:
            self.raid_data["is_recurring"] = False
            self.raid_data["recurring_interval_days"] = None
        else:
            try:
                interval = int(raw)
            except ValueError:
                await interaction.response.send_message(
                    "⚠ Interval must be a whole number.",
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )
                return

            if interval <= 0:
                await interaction.response.send_message(
                    "⚠ Interval must be greater than 0.",
                    ephemeral=True,
                )
                asyncio.create_task(
                    delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )
                return

            self.raid_data["is_recurring"] = True
            self.raid_data["recurring_interval_days"] = interval

        await interaction.response.edit_message(
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class SaveTemplateModal(discord.ui.Modal, title="Save Raid Template"):
    template_name = discord.ui.TextInput(
        label="Template Name",
        placeholder="Example: Wednesday HC",
        max_length=50,
    )

    def __init__(self, guild_id: int, raid_data: dict):
        super().__init__()
        self.guild_id = guild_id
        self.raid_data = dict(raid_data)

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        name = str(self.template_name).strip()
        ok = save_template(self.guild_id, name, self.raid_data)

        if ok:
            await interaction.response.edit_message(
                content="✅ Template saved.",
                embed=build_preview_embed(guild, self.raid_data),
                view=RaidBuilderView(self.raid_data),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"⚠ A template named **{name}** already exists.",
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data, existing_template_name=name),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class TemplateDateModal(discord.ui.Modal, title="Set Raid Date from Template"):
    raid_date = discord.ui.TextInput(
        label="Raid Date",
        placeholder="YYYY-MM-DD",
        max_length=10,
    )

    def __init__(self, guild_id: int, channel_id: int, template_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.template_name = template_name

    async def on_submit(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        raid_data = build_raid_data_from_template(
            self.guild_id,
            self.channel_id,
            self.template_name,
            str(self.raid_date).strip(),
        )

        if not raid_data:
            await interaction.response.send_message(
                "⚠ Could not load that template.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=None,
            embed=build_preview_embed(guild, raid_data),
            view=RaidBuilderView(raid_data),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )