import asyncio
import discord

from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS
from utils.discord_utils import delete_interaction_after
from views.signup.settings.raid_settings_modals import (
    EditRaidTitleModal,
    EditRaidDescriptionModal,
    EditRaidLeaderModal,
    EditRaidDateModal,
    EditRaidTimeModal,
)


class EditRaidTitleButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Edit Title",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRaidTitleModal(int(self.raid_id)))


class EditRaidDescriptionButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Edit Description",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRaidDescriptionModal(int(self.raid_id)))


class EditRaidLeaderButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Edit Leader",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRaidLeaderModal(int(self.raid_id)))


class EditRaidDateButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Edit Date",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRaidDateModal(int(self.raid_id)))


class EditRaidTimeButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Edit Time",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditRaidTimeModal(int(self.raid_id)))


# -----------------------------
# RECURRING FLOW
# -----------------------------

class RecurringOptionsButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Recurring Options",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Recurring raid settings",
            view=RecurringOptionsView(self.raid_id),
        )


class ToggleRecurringButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Enable / Disable Recurring",
            style=discord.ButtonStyle.secondary,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):

        from services.raid.raid_control_service import toggle_recurring
        from services.signup.signup_refresh_service import refresh_signup_message_by_id

        ok = toggle_recurring(self.raid_id)

        if not ok:
            await interaction.response.send_message(
                "Failed to update recurring setting.",
                ephemeral=True,
            )
            return

        await refresh_signup_message_by_id(interaction.channel, int(self.raid_id))

        await interaction.response.edit_message(
            content="Recurring setting updated.",
            view=RecurringOptionsView(self.raid_id),
        )


class RecurringIntervalModal(discord.ui.Modal, title="Set Recurring Interval"):

    interval = discord.ui.TextInput(
        label="Interval (days)",
        placeholder="7",
        required=True,
    )

    def __init__(self, raid_id: str):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):

        from services.raid.raid_control_service import set_recurring_interval
        from services.signup.signup_refresh_service import refresh_signup_message_by_id

        try:
            days = int(self.interval.value)
        except ValueError:
            await interaction.response.send_message(
                "Interval must be a number.",
                ephemeral=True,
            )
            return

        ok = set_recurring_interval(self.raid_id, days)

        if not ok:
            await interaction.response.send_message(
                "Failed to set interval.",
                ephemeral=True,
            )
            return

        await refresh_signup_message_by_id(interaction.channel, int(self.raid_id))

        await interaction.response.send_message(
            f"Recurring interval set to {days} days.",
            ephemeral=True,
        )


class SetRecurringIntervalButton(discord.ui.Button):

    def __init__(self, raid_id: str):
        super().__init__(
            label="Set Interval",
            style=discord.ButtonStyle.secondary,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RecurringIntervalModal(self.raid_id)
        )


class RecurringOptionsView(discord.ui.View):

    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.add_item(ToggleRecurringButton(raid_id))
        self.add_item(SetRecurringIntervalButton(raid_id))
        self.add_item(BackToRaidSettingsButton(raid_id))


class BackToRaidSettingsButton(discord.ui.Button):

    def __init__(self, raid_id: str):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.edit_message(
            content="Raid settings",
            view=RaidSettingsView(self.raid_id),
        )


# -----------------------------
# MAIN SETTINGS VIEW
# -----------------------------

class BackToRaidControlButton(discord.ui.Button):

    def __init__(self, raid_id: str):
        super().__init__(
            label="Back to Raid Control",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):

        from views.signup.raid_control.raid_control_view import RaidControlView

        await interaction.response.edit_message(
            content="Raid control panel",
            view=RaidControlView(self.raid_id),
        )

        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidSettingsView(discord.ui.View):

    def __init__(self, raid_id: str):

        super().__init__(timeout=120)

        # Row 1
        self.add_item(EditRaidTitleButton(raid_id))
        self.add_item(EditRaidDescriptionButton(raid_id))
        self.add_item(EditRaidLeaderButton(raid_id))
        self.add_item(EditRaidDateButton(raid_id))
        self.add_item(EditRaidTimeButton(raid_id))

        # Row 2
        self.add_item(RecurringOptionsButton(raid_id))

        # Row 3
        self.add_item(BackToRaidControlButton(raid_id))