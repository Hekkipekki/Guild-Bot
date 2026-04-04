import discord
import config


def _player_line(user_id: str, entry: dict) -> str:
    name = (entry.get("name") or "").strip()
    if not name:
        name = (entry.get("display_name") or "").strip()

    if not name:
        name = f"<@{user_id}>"

    spec = entry.get("spec", "")
    emoji = config.SPEC_EMOJIS.get(spec, "")

    return f"{emoji} {name}".strip() if emoji else name


def _group_value(players: list[tuple[str, dict]]) -> str:
    if not players:
        return "-"

    return "\n".join(_player_line(user_id, entry) for user_id, entry in players)


def _add_status_section(
    embed: discord.Embed,
    *,
    icon: str,
    label: str,
    players: list[tuple[str, dict]],
) -> None:
    if not players:
        return

    embed.add_field(
        name=f"{icon} {label} ({len(players)})",
        value=_group_value(players),
        inline=False,
    )


def build_comp_embed(comp_data: dict) -> discord.Embed:
    title = comp_data.get("title", "Raid Comp")
    description = comp_data.get("description", "")
    leader = comp_data.get("leader", "")
    start_ts = comp_data.get("start_ts")

    summary_emojis = getattr(config, "SUMMARY_EMOJIS", {})
    bench_icon = summary_emojis.get("Bench", "🪑")
    late_icon = summary_emojis.get("Late", "⏰")
    tentative_icon = summary_emojis.get("Tentative", "❔")
    absence_icon = summary_emojis.get("Absence", "❌")

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.purple(),
    )

    if leader:
        embed.add_field(name="Leader", value=f"🏳️ {leader}", inline=False)

    if start_ts:
        embed.add_field(name="Date", value=f"<t:{start_ts}:D>", inline=True)
        embed.add_field(name="Time", value=f"<t:{start_ts}:t>", inline=True)
        embed.add_field(name="Countdown", value=f"<t:{start_ts}:R>", inline=True)

    group_1 = comp_data.get("group_1", [])
    group_2 = comp_data.get("group_2", [])

    embed.add_field(
        name="Group 1",
        value=_group_value(group_1),
        inline=True,
    )
    embed.add_field(
        name="Group 2",
        value=_group_value(group_2),
        inline=True,
    )

    bench_players = comp_data.get("bench_players", [])
    late_players = comp_data.get("late_players", [])
    tentative_players = comp_data.get("tentative_players", [])
    absence_players = comp_data.get("absence_players", [])

    has_extra_sections = any(
        [bench_players, late_players, tentative_players, absence_players]
    )

    if has_extra_sections:
        embed.add_field(name="\u200b", value="\u200b", inline=False)

    _add_status_section(
        embed,
        icon=bench_icon,
        label="Bench",
        players=bench_players,
    )
    _add_status_section(
        embed,
        icon=late_icon,
        label="Late",
        players=late_players,
    )
    _add_status_section(
        embed,
        icon=tentative_icon,
        label="Tentative",
        players=tentative_players,
    )
    _add_status_section(
        embed,
        icon=absence_icon,
        label="Absence",
        players=absence_players,
    )

    embed.set_footer(text="Composition Tool")
    return embed