import asyncio
import discord
from discord import File

from services.attendance.attendance_image_service import (
    render_attendance_report_image,
)
from services.attendance.attendance_service import (
    get_attendance_record,
    summarize_attendance_record,
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


def _build_summary_text(record: dict | None) -> str:
    if not record:
        return "No attendance record found for this raid."

    summary = summarize_attendance_record(record)

    title = record.get("title") or "Raid"
    finalized = bool(record.get("finalized"))
    finalized_text = "Yes" if finalized else "No"

    lines = [
        f"**Attendance Panel**",
        f"**Raid:** {title}",
        f"**Official Snapshot:** {finalized_text}",
        "",
        f"Attending: **{summary.get('attending', 0)}**",
        f"Benched: **{summary.get('benched', 0)}**",
        f"Late: **{summary.get('late', 0)}**",
        f"Tentative: **{summary.get('tentative', 0)}**",
        f"Absent: **{summary.get('absent', 0)}**",
        f"No Sign: **{summary.get('no_sign', 0) + summary.get('not_selected', 0)}**",
    ]

    return "\n".join(lines)


def _build_selection_text(
    record: dict | None,
    selected_user_id: str | None,
    selected_action: str | None,
) -> str:
    if not record:
        return ""

    players = record.get("players", {})
    selected_player = players.get(str(selected_user_id)) if selected_user_id else None

    player_text = "None selected"
    if selected_player:
        player_name = _get_player_display_name(selected_player)
        current_status = selected_player.get("attendance_status", "unknown")
        auto_status = selected_player.get("auto_status", "unknown")
        source = selected_player.get("status_source", "auto")

        player_text = (
            f"{player_name} "
            f"(current: {current_status}, auto: {auto_status}, source: {source})"
        )

    action_text = STATUS_LABELS.get(selected_action, "None selected")

    return (
        "\n\n"
        f"**Selected Player:** {player_text}\n"
        f"**Selected Action:** {action_text}"
    )


def build_attendance_panel_content(
    raid_id: str,
    *,
    selected_user_id: str | None = None,
    selected_action: str | None = None,
) -> str:
    record = get_attendance_record(raid_id)
    summary_text = _build_summary_text(record)
    selection_text = _build_selection_text(record, selected_user_id, selected_action)
    return summary_text + selection_text


def _build_player_options(raid_id: str) -> list[discord.SelectOption]:
    record = get_attendance_record(raid_id)
    if not record:
        return [
            discord.SelectOption(
                label="No attendance record found",
                value="__none__",
                description="Post a comp first to create attendance.",
            )
        ]

    players = record.get("players", {})
    sortable = []

    for user_id, player in players.items():
        sortable.append(
            (
                STATUS_ORDER.index(player.get("attendance_status"))
                if player.get("attendance_status") in STATUS_ORDER
                else 999,
                _get_player_display_name(player).lower(),
                str(user_id),
                player,
            )
        )

    sortable.sort(key=lambda item: (item[0], item[1]))

    options: list[discord.SelectOption] = []
    for _, __, user_id, player in sortable[:25]:
        name = _get_player_display_name(player)
        wow_class = player.get("class") or "Unknown"
        spec = player.get("spec") or "Unknown"
        attendance_status = player.get("attendance_status") or "Unknown"

        options.append(
            discord.SelectOption(
                label=name[:100],
                value=str(user_id),
                description=f"{wow_class} • {spec} • {attendance_status}"[:100],
            )
        )

    if not options:
        options.append(
            discord.SelectOption(
                label="No attendance players",
                value="__none__",
                description="There are no attendance players for this raid.",
            )
        )

    return options


class AttendancePlayerSelect(discord.ui.Select):
    def __init__(self, raid_id: str):
        self.raid_id = raid_id

        super().__init__(
            placeholder="Select attendance player...",
            min_values=1,
            max_values=1,
            options=_build_player_options(raid_id),
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
        view.selected_user_id = self.values[0]

        await interaction.response.edit_message(
            content=build_attendance_panel_content(
                view.raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
            view=view,
        )


class AttendanceActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Attending", value="attending"),
            discord.SelectOption(label="Benched", value="benched"),
            discord.SelectOption(label="Late", value="late"),
            discord.SelectOption(label="Tentative", value="tentative"),
            discord.SelectOption(label="Absent", value="absent"),
            discord.SelectOption(label="No Sign", value="no_sign"),
        ]

        super().__init__(
            placeholder="Select attendance status...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
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
            content=build_attendance_panel_content(
                view.raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
            view=view,
        )


class ApplyAttendanceActionButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Apply",
            style=discord.ButtonStyle.success,
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
        record = get_attendance_record(view.raid_id)

        if not record:
            await _send_attendance_error(
                interaction,
                "No attendance record found for this raid.",
            )
            return

        if not view.selected_user_id or not view.selected_action:
            await _send_attendance_error(
                interaction,
                "Select both a player and an attendance status first.",
            )
            return

        ok, message = set_manual_attendance_status(
            raid_id=view.raid_id,
            user_id=view.selected_user_id,
            attendance_status=view.selected_action,
            edited_by_user_id=interaction.user.id,
        )

        if not ok:
            await _send_attendance_error(interaction, message)
            return

        view.selected_action = None

        await interaction.response.edit_message(
            content=build_attendance_panel_content(
                view.raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=view.selected_action,
            ),
            view=AttendanceView(view.raid_id, selected_user_id=view.selected_user_id),
        )


class ResetAttendancePlayerButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Reset to Auto",
            style=discord.ButtonStyle.secondary,
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

        if not view.selected_user_id:
            await _send_attendance_error(
                interaction,
                "Select a player first.",
            )
            return

        ok, message = reset_player_to_auto_status(
            raid_id=view.raid_id,
            user_id=view.selected_user_id,
            edited_by_user_id=interaction.user.id,
        )

        if not ok:
            await _send_attendance_error(interaction, message)
            return

        await interaction.response.edit_message(
            content=build_attendance_panel_content(
                view.raid_id,
                selected_user_id=view.selected_user_id,
                selected_action=None,
            ),
            view=AttendanceView(view.raid_id, selected_user_id=view.selected_user_id),
        )


class ShowAttendanceReportButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Show Report",
            style=discord.ButtonStyle.primary,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await _send_attendance_error(
                interaction,
                "This can only be used inside a server.",
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            buffer = render_attendance_report_image(
                guild_id=guild.id,
                finalized_only=True,
                limit_raids=12,
                title=f"{guild.name} Attendance",
            )

            file = File(fp=buffer, filename="attendance_report.png")

            await interaction.followup.send(
                file=file,
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"⚠ Failed to generate attendance report: {type(e).__name__}: {e}",
                ephemeral=True,
            )


class BackToRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Back",
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

        from views.signup.raid_control.raid_control_view import RaidControlView

        view = self.view

        await interaction.response.edit_message(
            content="Raid control panel",
            view=RaidControlView(view.raid_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CloseAttendanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            row=3,
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
        raid_id: str,
        *,
        selected_user_id: str | None = None,
        selected_action: str | None = None,
    ):
        super().__init__(timeout=120)
        self.raid_id = str(raid_id)
        self.selected_user_id = selected_user_id
        self.selected_action = selected_action

        self.add_item(AttendancePlayerSelect(self.raid_id))
        self.add_item(AttendanceActionSelect())
        self.add_item(ApplyAttendanceActionButton())
        self.add_item(ResetAttendancePlayerButton())
        self.add_item(ShowAttendanceReportButton())
        self.add_item(BackToRaidControlButton())
        self.add_item(CloseAttendanceButton())