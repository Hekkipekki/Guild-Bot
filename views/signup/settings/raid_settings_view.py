import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from utils.discord_utils import delete_interaction_after
from utils.panel_helpers import safe_panel_edit
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS

from views.signup.settings.raid_settings_modals import (
    EditRaidTitleModal,
    EditRaidDescriptionModal,
    EditRaidLeaderModal,
    EditRaidDateModal,
    EditRaidTimeModal,
)


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def _format_pause_until(pause_until_ts: int | None) -> str | None:
    if not isinstance(pause_until_ts, int):
        return None

    dt = datetime.fromtimestamp(pause_until_ts, tz=SWEDEN_TZ)
    return dt.strftime("%a %d/%m")


def build_recurring_options_content(raid_id: str) -> str:
    from services.raid.raid_control_service import get_recurring_settings

    settings = get_recurring_settings(raid_id)
    enabled = bool(settings.get("enabled"))
    interval = settings.get("interval")
    pause_until = _format_pause_until(settings.get("pause_until_ts"))

    status_text = "✅ Enabled" if enabled else "❌ Disabled"
    interval_text = f"{interval} days" if interval else "Not set"

    lines = [
        "**Recurring raid settings**",
        "",
        f"Status: {status_text}",
        f"Interval: {interval_text}",
    ]

    if pause_until:
        lines.append(f"Paused until: {pause_until}")

    return "\n".join(lines)


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


class RecurringOptionsButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Recurring Options",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringOptionsView(self.raid_id),
        )


class ToggleRecurringButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        from services.raid.raid_control_service import get_recurring_settings

        settings = get_recurring_settings(raid_id)
        enabled = bool(settings.get("enabled"))

        super().__init__(
            label="Disable Recurring" if enabled else "Enable Recurring",
            style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
            row=0,
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

        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
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

        if days <= 0:
            await interaction.response.send_message(
                "Interval must be at least 1 day.",
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

        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringOptionsView(self.raid_id),
        )


class SetRecurringIntervalButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Set Interval",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            RecurringIntervalModal(self.raid_id)
        )


class OpenRecurringPauseButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Pause Recurring",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringPauseView(self.raid_id),
        )


class PauseRecurringForButton(discord.ui.Button):
    def __init__(self, raid_id: str, weeks: int):
        super().__init__(
            label=f"Pause {weeks} week{'s' if weeks != 1 else ''}",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.raid_id = raid_id
        self.weeks = weeks

    async def callback(self, interaction: discord.Interaction):
        from services.raid.raid_control_service import set_recurring_pause
        from services.signup.signup_refresh_service import refresh_signup_message_by_id

        ok = set_recurring_pause(self.raid_id, self.weeks)

        if not ok:
            await interaction.response.send_message(
                "Failed to pause recurring raid.",
                ephemeral=True,
            )
            return

        await refresh_signup_message_by_id(interaction.channel, int(self.raid_id))

        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringOptionsView(self.raid_id),
        )


class ResumeRecurringButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Resume",
            style=discord.ButtonStyle.success,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        from services.raid.raid_control_service import clear_recurring_pause
        from services.signup.signup_refresh_service import refresh_signup_message_by_id

        ok = clear_recurring_pause(self.raid_id)

        if not ok:
            await interaction.response.send_message(
                "Failed to resume recurring raid.",
                ephemeral=True,
            )
            return

        await refresh_signup_message_by_id(interaction.channel, int(self.raid_id))

        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringOptionsView(self.raid_id),
        )


class BackToRecurringOptionsButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content=build_recurring_options_content(self.raid_id),
            view=RecurringOptionsView(self.raid_id),
        )


class BackToRaidSettingsButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.raid_id = raid_id

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Raid settings",
            view=RaidSettingsView(self.raid_id),
        )


class RecurringOptionsView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.add_item(ToggleRecurringButton(raid_id))
        self.add_item(SetRecurringIntervalButton(raid_id))
        self.add_item(OpenRecurringPauseButton(raid_id))
        self.add_item(BackToRaidSettingsButton(raid_id))


class RecurringPauseView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.add_item(PauseRecurringForButton(raid_id, 1))
        self.add_item(PauseRecurringForButton(raid_id, 2))
        self.add_item(PauseRecurringForButton(raid_id, 3))
        self.add_item(ResumeRecurringButton(raid_id))
        self.add_item(BackToRecurringOptionsButton(raid_id))


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

        await safe_panel_edit(
            interaction,
            content="Raid control panel",
            view=RaidControlView(self.raid_id),
        )

        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidSettingsView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.add_item(EditRaidTitleButton(raid_id))
        self.add_item(EditRaidDescriptionButton(raid_id))
        self.add_item(EditRaidLeaderButton(raid_id))
        self.add_item(EditRaidDateButton(raid_id))
        self.add_item(EditRaidTimeButton(raid_id))
        self.add_item(RecurringOptionsButton(raid_id))
        self.add_item(BackToRaidControlButton(raid_id))
