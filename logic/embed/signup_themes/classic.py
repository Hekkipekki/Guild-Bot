import discord

from logic.roster_builder import rebuild_roster
from logic.unassigned import get_unassigned_players
from logic.embed.player_formatting import (
    format_player_line,
    format_unassigned_player,
)
from logic.embed.summary_helpers import (
    get_summary_icons,
    count_signed_melee_and_ranged,
    build_time_fields,
)


def build_classic_signup_embed(title: str, description: str, signup: dict) -> discord.Embed:
    users = signup.get("users", {})
    roster = rebuild_roster(users)

    embed = discord.Embed(
        title=title,
        color=discord.Color.purple(),
    )

    leader_text = signup.get("leader", "Hekkipekki / Rhegaran")
    start_ts = signup.get("start_ts")

    tanks = roster["roles"]["Tank"]
    healers = roster["roles"]["Healer"]
    dps = roster["roles"]["DPS"]

    melee_count, ranged_count = count_signed_melee_and_ranged(users)
    total_signed = len(tanks) + len(healers) + len(dps)

    tank_value = "\n".join(
        format_player_line(user_id, info) for user_id, info in tanks
    ) if tanks else "-"

    healer_value = "\n".join(
        format_player_line(user_id, info) for user_id, info in healers
    ) if healers else "-"

    dps_value = "\n".join(
        format_player_line(user_id, info) for user_id, info in dps
    ) if dps else "-"

    icons = get_summary_icons()

    embed.description = description

    embed.add_field(name="Leader", value=f"🏳️ {leader_text}", inline=True)
    embed.add_field(name="Signups", value=f"{icons['signups']} {total_signed}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    date_value, time_value, countdown_value = build_time_fields(
        start_ts,
        icons["calendar"],
        icons["countdown"],
    )

    embed.add_field(name="Date", value=date_value, inline=True)
    embed.add_field(name="Time", value=time_value, inline=True)
    embed.add_field(name="Countdown", value=countdown_value, inline=True)

    embed.add_field(name="\u200b", value="\u200b", inline=False)

    embed.add_field(
        name=f"{icons['tank']} Tanks ({len(tanks)})",
        value=tank_value,
        inline=True,
    )
    embed.add_field(
        name=f"{icons['healer']} Healers ({len(healers)})",
        value=healer_value,
        inline=True,
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.add_field(
        name=f"{icons['dps']} DPS ({len(dps)}) — Melee {melee_count} / Ranged {ranged_count}",
        value=dps_value,
        inline=False,
    )

    # visual spacer between signed roster and optional statuses
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    def add_optional_line(label: str, entries: list, icon: str) -> None:
        if not entries:
            return

        value = "\n".join(
            format_player_line(user_id, info) for user_id, info in entries
        )

        embed.add_field(
            name=f"{icon} {label} ({len(entries)})",
            value=value,
            inline=False,
        )

    add_optional_line("Late", roster["late"], icons["late"])
    add_optional_line("Tentative", roster["tentative"], icons["tentative"])
    add_optional_line("Bench", roster["bench"], icons["bench"])
    add_optional_line("Absence", roster["absence"], icons["absence"])

    unassigned_players = get_unassigned_players(signup)

    if unassigned_players:
        embed.add_field(
            name=f"📌 Unassigned Players ({len(unassigned_players)})",
            value=" ".join(format_unassigned_player(user_id) for user_id in unassigned_players),
            inline=False,
        )

    return embed