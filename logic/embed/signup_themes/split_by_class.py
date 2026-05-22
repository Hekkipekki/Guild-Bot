import discord
import config

from logic.roster_builder import rebuild_roster
from logic.unassigned import get_unassigned_players
from logic.embed.player_formatting import format_player_line, format_unassigned_player
from logic.embed.summary_helpers import (
    get_summary_icons,
    count_signed_melee_and_ranged,
    build_time_fields,
)


def _class_icon(class_name: str) -> str:
    return config.CLASS_EMOJIS.get(class_name, "")


def _group_signed_by_class(users: dict) -> dict[str, list[tuple[str, dict]]]:
    grouped = {class_name: [] for class_name in config.CLASSES}

    sorted_users = sorted(
        users.items(),
        key=lambda item: item[1].get("timestamp", 0),
    )

    for user_id, info in sorted_users:
        if info.get("status") != "sign":
            continue

        class_name = info.get("class")
        if class_name not in grouped:
            continue

        grouped[class_name].append((user_id, info))

    return grouped


def _lines(entries: list[tuple[str, dict]]) -> str:
    if not entries:
        return "-"

    return "\n".join(format_player_line(user_id, info) for user_id, info in entries)


def _status_block(label: str, entries: list[tuple[str, dict]], icon: str) -> str:
    if not entries:
        return ""

    return f"{icon} **{label} ({len(entries)})**\n{_lines(entries)}"


def build_split_by_class_signup_embed(title: str, description: str, signup: dict) -> discord.Embed:
    users = signup.get("users", {})
    roster = rebuild_roster(users)
    icons = get_summary_icons()

    leader_text = signup.get("leader", "Raid Leader")
    start_ts = signup.get("start_ts")

    tanks = roster["roles"]["Tank"]
    healers = roster["roles"]["Healer"]
    dps = roster["roles"]["DPS"]

    melee_count, ranged_count = count_signed_melee_and_ranged(users)
    total_signed = len(tanks) + len(healers) + len(dps)

    date_value, time_value, countdown_value = build_time_fields(
        start_ts,
        icons["calendar"],
        icons["countdown"],
    )

    embed = discord.Embed(
        title=title,
        color=discord.Color.purple(),
    )

    embed.description = (
        f"{description}\n\n"
        f"🏳️ **Leader:** {leader_text}\n"
        f"{date_value} • {time_value} • {countdown_value}\n\n"
        f"{icons['signups']} **{total_signed} signed**  "
        f"{icons['tank']} {len(tanks)}/2  "
        f"{icons['healer']} {len(healers)}/3  "
        f"{icons['dps']} {len(dps)}/9  "
        f"⚔️ M {melee_count} / 🏹 R {ranged_count}"
    )

    grouped = _group_signed_by_class(users)

    for class_name in config.CLASSES:
        entries = grouped.get(class_name, [])
        if not entries:
            continue

        icon = _class_icon(class_name)
        embed.add_field(
            name=f"{icon} {class_name} ({len(entries)})".strip(),
            value=_lines(entries),
            inline=True,
        )

    status_blocks = [
        _status_block("Late", roster["late"], icons["late"]),
        _status_block("Tentative", roster["tentative"], icons["tentative"]),
        _status_block("Bench", roster["bench"], icons["bench"]),
        _status_block("Absence", roster["absence"], icons["absence"]),
    ]
    status_blocks = [block for block in status_blocks if block]

    if status_blocks:
        embed.add_field(
            name="Other Statuses",
            value="\n\n".join(status_blocks),
            inline=False,
        )

    unassigned_players = get_unassigned_players(signup)
    if unassigned_players:
        embed.add_field(
            name=f"📌 Unassigned ({len(unassigned_players)})",
            value=" ".join(format_unassigned_player(user_id) for user_id in unassigned_players),
            inline=False,
        )

    embed.set_footer(text="Signup theme: Split by Class")
    return embed