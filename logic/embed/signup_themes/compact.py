import discord
import config
from datetime import datetime

from logic.roster_builder import rebuild_roster
from logic.embed.player_formatting import (
    NOTE_MARKER,
    get_player_display_text,
)


def _chip(text: str) -> str:
    return f"`{text}`"


def _summary_icon(key: str, fallback: str = "") -> str:
    return getattr(config, "SUMMARY_EMOJIS", {}).get(key, fallback)


def _spec_icon(spec: str) -> str:
    return getattr(config, "SPEC_EMOJIS", {}).get(spec, "")


def _has_note(info: dict) -> bool:
    return bool((info.get("note") or "").strip())


def _format_date(start_ts: int | None) -> str:
    if not start_ts:
        return "-"

    try:
        return datetime.fromtimestamp(int(start_ts)).strftime("%d %b %Y")
    except Exception:
        return "-"


def _format_time(start_ts: int | None) -> str:
    if not start_ts:
        return "-"

    try:
        return datetime.fromtimestamp(int(start_ts)).strftime("%H:%M")
    except Exception:
        return "-"


def _player_line(user_id: str, info: dict) -> str:
    spec = info.get("spec", "Unknown")
    spec_icon = _spec_icon(spec)

    name = get_player_display_text(user_id, info)
    if _has_note(info):
        name = f"{name}{NOTE_MARKER}"

    if spec_icon:
        return f"{spec_icon} {name}"

    return name


def _player_lines(entries: list[tuple[str, dict]]) -> str:
    if not entries:
        return "-"

    return "\n".join(
        _player_line(user_id, info)
        for user_id, info in entries
    )


def _add_info_field(
    embed: discord.Embed,
    *,
    icon: str,
    text: str,
    inline: bool = True,
) -> None:
    embed.add_field(
        name="\u200b",
        value=f"{icon} {_chip(text)}",
        inline=inline,
    )


def _add_roster_field(
    embed: discord.Embed,
    *,
    icon: str,
    title: str,
    entries: list[tuple[str, dict]],
    inline: bool = True,
) -> None:
    embed.add_field(
        name=f"{icon} {_chip(title)}",
        value=_player_lines(entries),
        inline=inline,
    )


def _add_spacer(embed: discord.Embed) -> None:
    embed.add_field(
        name="\u200b",
        value="\u200b",
        inline=False,
    )


def build_compact_signup_embed(
    title: str,
    description: str,
    signup: dict,
) -> discord.Embed:
    users = signup.get("users", {})
    roster = rebuild_roster(users)

    leader_text = signup.get("leader", "Raid Leader")
    start_ts = signup.get("start_ts")

    tanks = roster["roles"]["Tank"]
    healers = roster["roles"]["Healer"]
    dps = roster["roles"]["DPS"]

    melee_count = sum(
        1
        for _, info in dps
        if info.get("role") == "Melee"
    )
    ranged_count = sum(
        1
        for _, info in dps
        if info.get("role") == "Ranged"
    )

    total_signed = len(tanks) + len(healers) + len(dps)

    leader_icon = "🏳️"
    clock_icon = "🕒"

    signup_icon = _summary_icon("Signups", "👥")
    calendar_icon = _summary_icon("Calendar", "📅")
    countdown_icon = _summary_icon("Countdown", "⏳")
    dps_icon = _summary_icon("DPS", "⚔️")
    tank_icon = _summary_icon("Tank", "🛡️")
    healer_icon = _summary_icon("Healer", "➕")
    late_icon = _summary_icon("Late", "⏰")
    tentative_icon = _summary_icon("Tentative", "❔")
    absence_icon = _summary_icon("Absence", "❌")
    bench_icon = _summary_icon("Bench", "🪑")

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.purple(),
    )

    # Row 1
    embed.add_field(
        name=f"{leader_icon} {_chip(leader_text)}",
        value="",
        inline=True,
    )

    embed.add_field(
        name=f"{signup_icon} {_chip(str(total_signed))}",
        value="",
        inline=True,
    )

    embed.add_field(
        name="",
        value="",
        inline=True,
    )

    # Row 2
    embed.add_field(
        name=f"{calendar_icon} {_chip(_format_date(start_ts))}",
        value="",
        inline=True,
    )

    embed.add_field(
        name=f"{clock_icon} {_chip(_format_time(start_ts))}",
        value="",
        inline=True,
    )

    countdown_text = f"<t:{int(start_ts)}:R>" if start_ts else "-"

    embed.add_field(
        name=f"{countdown_icon} {countdown_text}",
        value="",
        inline=True,
    )

    _add_spacer(embed)

    # Row 3
    _add_roster_field(
        embed,
        icon=dps_icon,
        title=f"DPS ({melee_count}M - {ranged_count}R)",
        entries=dps,
        inline=True,
    )

    _add_roster_field(
        embed,
        icon=tank_icon,
        title=f"Tanks ({len(tanks)})",
        entries=tanks,
        inline=True,
    )

    _add_roster_field(
        embed,
        icon=healer_icon,
        title=f"Healers ({len(healers)})",
        entries=healers,
        inline=True,
    )

    _add_spacer(embed)

    # Row 4 priority: Late > Tentative > Absence > Bench
    _add_roster_field(
        embed,
        icon=late_icon,
        title=f"Late ({len(roster['late'])})",
        entries=roster["late"],
        inline=True,
    )

    _add_roster_field(
        embed,
        icon=tentative_icon,
        title=f"Tentative ({len(roster['tentative'])})",
        entries=roster["tentative"],
        inline=True,
    )

    _add_roster_field(
        embed,
        icon=absence_icon,
        title=f"Absence ({len(roster['absence'])})",
        entries=roster["absence"],
        inline=True,
    )

    if roster["bench"]:
        _add_roster_field(
            embed,
            icon=bench_icon,
            title=f"Bench ({len(roster['bench'])})",
            entries=roster["bench"],
            inline=False,
        )

    embed.set_footer(text="Signup theme: Compact")
    return embed