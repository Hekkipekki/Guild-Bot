import asyncio
import discord

from services.attendance.attendance_report_service import (
    get_guild_attendance_records,
)
from services.attendance.attendance_service import (
    get_attendance_record,
    set_manual_attendance_status,
    reset_player_to_auto_status,
)
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


STATUS_LABELS = {
    "attending": "Attending",
    "benched": "Benched",
    "late": "Late",
    "tentative": "Tentative",
    "absent": "Absent",
    "not_selected": "No Sign",
    "no_sign": "No Sign",
    "unknown": "Unknown",
}

STATUS_ORDER = [
    "attending",
    "benched",
    "late",
    "tentative",
    "absent",
    "not_selected",
    "no_sign",
]


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


def _get_player_display_name(player: dict) -> str:
    return player.get("name") or player.get("display_name") or "Unknown"


def _get_status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "unknown", "Unknown")


def _format_raid_label(record: dict) -> str:
    title = (record.get("title") or "Raid").strip()
    start_ts = record.get("start_ts")

    if start_ts:
        return f"{title} • <t:{int(start_ts)}:d>"[:100]

    return title[:100]


def _build_panel_content(
    *,
    selected_raid_id: str,
    selected_user_id: str | None = None,
    selected_action: str | None = None,
) -> str:
    record = get_attendance_record(selected_raid_id)

    if not record:
        return "No attendance record found."

    title = record.get("title") or "Raid"
    finalized = "Yes" if record.get("finalized") else "No"
    start_ts = record.get("start_ts")

    raid_line = f"**Raid:** {title}"
    if start_ts:
        raid_line += f"\n**Date:** <t:{int(start_ts)}:F>"

    selected_player_text = "None selected"
    if selected_user_id:
        player = record.get("players", {}).get(str(selected_user_id))
        if player:
            selected_player_text = (
                f"{_get_player_display_name(player)} "
                f"({_get_status_label(player.get('attendance_status'))})"
            )

    selected_action_text = (
        _get_status_label(selected_action) if selected_action else "None selected"
    )

    return (
        "**Attendance Edit**\n"
        f"{raid_line}\n"
        f"**Official Snapshot:** {finalized}\n\n"
        f"**Selected Player:** {selected_player_text}\n"
        f"**Selected Action:** {selected_action_text}"
    )


def build_attendance_panel_content(
    raid_id: str,
    *,
    selected_user_id: str | None = None,
    selected_action: str | None = None,
) -> str:
    return _build_panel_content(
        selected_raid_id=str(raid_id),
        selected_user_id=selected_user_id,
        selected_action=selected_action,
    )

def _build_raid_options(
    current_raid_id: str,
    *,
    selected_raid_id: str | None = None,
) -> list[discord.SelectOption]:
    current_record = get_attendance_record(current_raid_id)

    if not current_record:
        return [
            discord.SelectOption(
                label="No attendance records found",
                value="__none__",
                description="No attendance data is available.",
            )
        ]

    guild_id = current_record.get("guild_id")
    if not guild_id:
        return [
            discord.SelectOption(
                label="No guild attendance records found",
                value="__none__",
                description="Missing guild_id on attendance record.",
            )
        ]

    records = get_guild_attendance_records(guild_id, finalized_only=False) or []

    # newest first
    records = sorted(
        records,
        key=lambda r: int(r.get("start_ts") or 0),
        reverse=True,
    )

    seen: set[str] = set()
    options: list[discord.SelectOption] = []

    for record in records:
        raid_id = str(record.get("raid_id") or "")
        if not raid_id or raid_id in seen:
            continue

        seen.add(raid_id)

        title = (record.get("title") or "Raid").strip()
        start_ts = record.get("start_ts")
        desc = "Select this raid to edit attendance"
        if start_ts:
            desc = f"Date: <t:{int(start_ts)}:d>"

        options.append(
            discord.SelectOption(
                label=_format_raid_label(record),
                value=raid_id,
                description=desc[:100],
                default=raid_id == str(selected_raid_id or current_raid_id),
            )
        )

        if len(options) >= 25:
            break

    if not options:
        options.append(
            discord.SelectOption(
                label="No attendance records found",
                value="__none__",
                description="No attendance data is available.",
            )
        )

    return options


def _build_player_options(
    selected_raid_id: str,
    *,
    selected_user_id: str | None = None,
) -> list[discord.SelectOption]:
    record = get_attendance_record(selected_raid_id)

    if not record:
        return [
            discord.SelectOption(
                label="No attendance record found",
                value="__none__",
                description="This raid has no attendance record.",
            )
        ]

    players = record.get("players", {})
    sortable = []

    for user_id, player in players.items():
        status = player.get("attendance_status")
        status_index = STATUS_ORDER.index(status) if status in STATUS_ORDER else 999

        sortable.append(
            (
                status_index,
                _get_player_display_name(player).lower(),
                str(user_id),
                player,
            )
        )

    sortable.sort(key=lambda item: (item[0], item[1]))

    options: list[discord.SelectOption] = []
    for _, __, user_id, player in sortable[:25]:
        name = _get_player_display_name(player)
        status = _get_status_label(player.get("attendance_status"))
        wow_class = player.get("class") or "Unknown"

        options.append(
            discord.SelectOption(
                label=name[:100],
                value=str(user_id),
                description=f"{wow_class} • {status}"[:100],
                default=str(user_id) == str(selected_user_id),
            )
        )

    if not options:
        options.append(
            discord.SelectOption(
                label="No players found",
                value="__none__",
                description="This raid has no attendance players.",
            )
        )

    return options


def _build_action_options(
    selected_action: str | None = None,
) -> list[discord.SelectOption]:
    statuses = [
        "attending",
        "benched",
        "late",
        "tentative",
        "absent",
        "no_sign",
    ]

    return [
        discord.SelectOption(
            label=_get_status_label(status),
            value=status,
            default=status == selected_action,
        )
        for status in statuses
    ]


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
            options=_build_raid_options(
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
            content=_build_panel_content(
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
            options=_build_player_options(
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
            content=_build_panel_content(
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
            options=_build_action_options(selected_action),
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
            content=_build_panel_content(
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
            content=_build_panel_content(
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
            content=_build_panel_content(
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