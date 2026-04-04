from __future__ import annotations

import asyncio

import discord

from services.attendance.attendance_service import (
    reset_player_to_auto_status,
    set_manual_attendance_status,
)
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)
from views.signup.raid_control.attendance_view_helpers import (
    build_action_options,
    build_attendance_panel_content,
    build_panel_content,
    build_player_options,
    build_raid_options,
)


async def _send_attendance_error(
    interaction: discord.Interaction,
    message: str,
) -> None:
    if interaction.response.is_done():
        msg = await interaction.followup.send(
            message,
            ephemeral=True,
            wait=True,
        )
        asyncio.create_task(
            delete_message_after(msg, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )


class AttendanceRaidSelect(discord.ui.Select):
    def __init__(
        self,
        current_raid_id: str,
        *,
        selected_raid_id: str | None = None,
    ):
        self.current_raid_id = str(current_raid_id)

        super().__init__(
            placeholder="Select raid...",
            min_values=1,
            max_values=1,
            options=build_raid_options(
                self.current_raid_id,
                selected_raid_id=selected_raid_id,
            ),
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        if self.values[0] == "__none__":
            await interaction.response.defer()
            return

        view = self.view
        selected_raid_id = str(self.values[0])

        await interaction.response.edit_message(
            content=build_panel_content(
                selected_raid_id=selected_raid_id,
                selected_user_id=None,
                selected_action=None,
            ),
            view=AttendanceView(
                current_raid_id=view.current_raid_id,
                selected_raid_id=selected_raid_id,
                selected_user_id=None,
                selected_action=None,
            ),
        )


class AttendancePlayerSelect(discord.ui.Select):
    def __init__(
        self,
        selected_raid_id: str,
        *,
        selected_user_id: str | None = None,
    ):
        self.selected_raid_id = str(selected_raid_id)

        super().__init__(
            placeholder="Select player...",
            min_values=1,
            max_values=1,
            options=build_player_options(
                self.selected_raid_id,
                selected_user_id=selected_user_id,
            ),
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        if self.values[0] == "__none__":
            await interaction.response.defer()
            return

        view = self.view
        view.selected_user_id = str(self.values[0])

        await interaction.response.edit_message(
            content=build_panel_content(
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
            view=AttendanceView(
                current_raid_id=view.current_raid_id,
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
        )


class AttendanceActionSelect(discord.ui.Select):
    def __init__(self, *, selected_action: str | None = None):
        super().__init__(
            placeholder="Select attendance status...",
            min_values=1,
            max_values=1,
            options=build_action_options(selected_action),
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        view = self.view
        view.selected_action = self.values[0]

        await interaction.response.edit_message(
            content=build_panel_content(
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
            view=AttendanceView(
                current_raid_id=view.current_raid_id,
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
        )


class ApplyAttendanceActionButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Apply",
            style=discord.ButtonStyle.success,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        view = self.view

        if not view.selected_user_id or not view.selected_action:
            await _send_attendance_error(
                interaction,
                "Select a raid, player, and attendance status first.",
            )
            return

        ok, message = set_manual_attendance_status(
            raid_id=view.selected_raid_id,
            user_id=view.selected_user_id,
            attendance_status=view.selected_action,
            edited_by_user_id=interaction.user.id,
        )

        if not ok:
            await _send_attendance_error(interaction, message)
            return

        await interaction.response.edit_message(
            content=build_panel_content(
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=None,
            ),
            view=AttendanceView(
                current_raid_id=view.current_raid_id,
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=None,
            ),
        )


class ResetAttendancePlayerButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Reset to Auto",
            style=discord.ButtonStyle.secondary,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        view = self.view

        if not view.selected_user_id:
            await _send_attendance_error(
                interaction,
                "Select a player first.",
            )
            return

        ok, message = reset_player_to_auto_status(
            raid_id=view.selected_raid_id,
            user_id=view.selected_user_id,
            edited_by_user_id=interaction.user.id,
        )

        if not ok:
            await _send_attendance_error(interaction, message)
            return

        await interaction.response.edit_message(
            content=build_panel_content(
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=None,
            ),
            view=AttendanceView(
                current_raid_id=view.current_raid_id,
                selected_raid_id=view.selected_raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=None,
            ),
        )


class BackToRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_attendance_error(
                interaction,
                "You do not have access to attendance controls.",
            )
            return

        from views.signup.raid_control.raid_control_view import RaidControlView

        view = self.view

        await interaction.response.edit_message(
            content="Raid control panel",
            view=RaidControlView(view.current_raid_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CloseAttendanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Attendance control closed.",
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class AttendanceView(discord.ui.View):
    def __init__(
        self,
        current_raid_id: str,
        *,
        selected_raid_id: str | None = None,
        selected_user_id: str | None = None,
        selected_action: str | None = None,
    ):
        super().__init__(timeout=120)

        self.current_raid_id = str(current_raid_id)
        self.selected_raid_id = str(selected_raid_id or current_raid_id)
        self.selected_user_id = selected_user_id
        self.selected_action = selected_action

        self.add_item(
            AttendanceRaidSelect(
                self.current_raid_id,
                selected_raid_id=self.selected_raid_id,
            )
        )
        self.add_item(
            AttendancePlayerSelect(
                self.selected_raid_id,
                selected_user_id=self.selected_user_id,
            )
        )
        self.add_item(
            AttendanceActionSelect(
                selected_action=self.selected_action,
            )
        )
        self.add_item(ApplyAttendanceActionButton())
        self.add_item(ResetAttendancePlayerButton())
        self.add_item(BackToRaidControlButton())
        self.add_item(CloseAttendanceButton())