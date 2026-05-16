from __future__ import annotations

from data.signup_store import (
    find_message_signup,
    load_signups,
)

import discord

from services.attendance.attendance_queries import (
    get_reference_guild_id,
    get_sorted_attendance_players,
)

from services.attendance.attendance_report_service import (
    get_guild_attendance_records,
)

from services.attendance.attendance_rules import (
    get_attendance_status_label,
    normalize_attendance_status,
)

from services.attendance.attendance_service import (
    get_attendance_record,
    summarize_attendance_record,
)

from constants.statuses import (
    ATTENDANCE_STATUS_ATTENDING,
    ATTENDANCE_STATUS_BENCHED,
    ATTENDANCE_STATUS_LATE,
    ATTENDANCE_STATUS_TENTATIVE,
    ATTENDANCE_STATUS_ABSENT,
    ATTENDANCE_STATUS_NO_SIGN,
)


def get_player_display_name(player: dict) -> str:
    return (
        (player.get("name") or "").strip()
        or (player.get("display_name") or "").strip()
        or "Unknown"
    )


def format_raid_label(record: dict) -> str:
    title = (record.get("title") or "Raid").strip()

    start_ts = record.get("start_ts")

    if start_ts:
        return f"{title} • <t:{int(start_ts)}:d>"[:100]

    return title[:100]


def build_panel_content(
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

    summary = summarize_attendance_record(record)

    total_players = len(record.get("players", {}))

    lines = [
        f"**Raid:** {title}",
        f"**Finalized:** {finalized}",
        f"**Players:** {total_players}",
    ]

    if start_ts:
        lines.insert(
            1,
            f"**Date:** <t:{int(start_ts)}:F>",
        )

    lines.append("")

    lines.append(
        (
            f"**Summary:** "
            f"Attending {summary['attending']} • "
            f"Bench {summary['benched']} • "
            f"Late {summary['late']} • "
            f"Tentative {summary['tentative']} • "
            f"Absent {summary['absent']} • "
            f"No Sign {summary['not_selected'] + summary['no_sign']}"
        )
    )

    if selected_user_id:
        player = record.get("players", {}).get(str(selected_user_id))

        if player:
            lines.append("")
            lines.append(
                f"**Selected Player:** {get_player_display_name(player)}"
            )

            lines.append(
                f"**Class:** {player.get('class') or 'Unknown'}"
            )

            lines.append(
                f"**Current Status:** "
                f"{get_attendance_status_label(player.get('attendance_status'))}"
            )

            lines.append(
                f"**Auto Status:** "
                f"{get_attendance_status_label(player.get('auto_status'))}"
            )

            lines.append(
                f"**Manual Override:** "
                f"{'Yes' if player.get('manual_override') else 'No'}"
            )

    if selected_action:
        lines.append("")
        lines.append(
            f"**Pending Action:** "
            f"{get_attendance_status_label(selected_action)}"
        )

    return "\n".join(lines)


def build_attendance_panel_content(
    raid_id: str,
    *,
    selected_user_id: str | None = None,
    selected_action: str | None = None,
) -> str:
    return build_panel_content(
        selected_raid_id=str(raid_id),
        selected_user_id=selected_user_id,
        selected_action=selected_action,
    )


def build_raid_options(
    current_raid_id: str,
    *,
    selected_raid_id: str | None = None,
) -> list[discord.SelectOption]:
    signups = load_signups()

    guild_id = get_reference_guild_id(
        get_attendance_record,
        current_raid_id,
        signup_record_getter=lambda raid_id: find_message_signup(
            signups,
            raid_id,
        ),
    )

    if guild_id is None:
        return [
            discord.SelectOption(
                label="No attendance raids found",
                value="__none__",
                description="Could not resolve guild for attendance records.",
            )
        ]

    records = get_guild_attendance_records(
        guild_id,
        finalized_only=False,
    )

    if not records:
        return [
            discord.SelectOption(
                label="No attendance raids found",
                value="__none__",
                description="No attendance records exist for this guild.",
            )
        ]

    options: list[discord.SelectOption] = []

    for record in records[:25]:
        raid_id = str(record.get("raid_id"))

        options.append(
            discord.SelectOption(
                label=format_raid_label(record),
                value=raid_id,
                description=(
                    f"Finalized: "
                    f"{'Yes' if record.get('finalized') else 'No'}"
                )[:100],
                default=raid_id == str(selected_raid_id or current_raid_id),
            )
        )

    return options


def build_player_options(
    selected_raid_id: str,
    *,
    selected_user_id: str | None = None,
) -> list[discord.SelectOption]:
    record = get_attendance_record(selected_raid_id)

    if not record:
        return [
            discord.SelectOption(
                label="No players found",
                value="__none__",
                description="Attendance record missing.",
            )
        ]

    sorted_players = get_sorted_attendance_players(record)

    options: list[discord.SelectOption] = []

    for user_id, player in sorted_players[:25]:
        name = get_player_display_name(player)

        status = get_attendance_status_label(
            player.get("attendance_status")
        )

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


def build_action_options(
    selected_action: str | None = None,
) -> list[discord.SelectOption]:
    statuses = [
        ATTENDANCE_STATUS_ATTENDING,
        ATTENDANCE_STATUS_BENCHED,
        ATTENDANCE_STATUS_LATE,
        ATTENDANCE_STATUS_TENTATIVE,
        ATTENDANCE_STATUS_ABSENT,
        ATTENDANCE_STATUS_NO_SIGN,
    ]

    return [
        discord.SelectOption(
            label=get_attendance_status_label(status),
            value=status,
            default=normalize_attendance_status(selected_action) == status,
        )
        for status in statuses
    ]