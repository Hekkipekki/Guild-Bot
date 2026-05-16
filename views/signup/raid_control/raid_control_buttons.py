from __future__ import annotations

import discord

from utils.emoji_helpers import parse_button_emoji
from utils.panel_helpers import safe_panel_edit

from views.ui_style import get_button_style

from views.signup.raid_control.attendance_view import AttendanceView

from views.signup.raid_control.raid_control_spec_view import (
    RaidControlSpecPlayerView,
)

from views.signup.raid_control.raid_control_comp import (
    handle_post_comp,
)

from views.signup.raid_control.raid_control_cancel import (
    handle_cancel_raid,
)

from views.signup.settings.raid_settings_view import (
    RaidSettingsView,
)


class OpenAttendanceButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Attendance",
            emoji=parse_button_emoji("attendance"),
            style=get_button_style("raid_control.attendance"),
            row=2,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Attendance control panel",
            view=AttendanceView(self.raid_id),
        )


class OpenSpecManagementButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Change Spec",
            emoji=parse_button_emoji("spec"),
            style=get_button_style("raid_control.change_spec"),
            row=2,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Select a player to change spec.",
            view=RaidControlSpecPlayerView(self.raid_id),
        )


class OpenRaidSettingsButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Raid Settings",
            emoji=parse_button_emoji("config"),
            style=get_button_style("raid_control.raid_settings"),
            row=2,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Raid settings",
            view=RaidSettingsView(self.raid_id),
        )


class PostCompButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Build Comp",
            emoji=parse_button_emoji("comp"),
            style=get_button_style("raid_control.build_comp"),
            row=2,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await handle_post_comp(
            interaction,
            raid_id=self.raid_id,
        )


class CancelRaidButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Cancel Raid",
            emoji=parse_button_emoji("cancel_raid"),
            style=get_button_style("raid_control.cancel_raid"),
            row=3,
        )

        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await handle_cancel_raid(
            interaction,
            raid_id=self.raid_id,
        )