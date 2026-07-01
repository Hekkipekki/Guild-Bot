from __future__ import annotations

from datetime import date, timedelta

import discord

from data.scheduling_store import load_scheduling, save_scheduling, get_panel


RAID_WEEKDAYS = {
    2: "Wed",  # Wednesday
    6: "Sun",  # Sunday
}


def get_raid_dates_ahead(weeks: int = 4) -> list[date]:
    today = date.today()
    end_date = today + timedelta(weeks=weeks)

    days: list[date] = []
    current = today

    while current <= end_date:
        if current.weekday() in RAID_WEEKDAYS:
            days.append(current)
        current += timedelta(days=1)

    return days


def build_absence_options(
    guild_id: int | str | None = None,
    panel_id: str | None = None,
    user_id: int | str | None = None,
) -> list[discord.SelectOption]:
    selected_dates = set()

    if guild_id is not None and panel_id is not None and user_id is not None:
        data = load_scheduling(guild_id)
        panel = get_panel(data, panel_id)

        if panel:
            absences = panel.get("absences", {})
            user_id = str(user_id)

            for date_iso, players in absences.items():
                if user_id in players:
                    selected_dates.add(date_iso)

    options: list[discord.SelectOption] = []

    for raid_date in get_raid_dates_ahead():
        weekday = RAID_WEEKDAYS[raid_date.weekday()]
        iso_week = raid_date.isocalendar().week
        value = raid_date.isoformat()

        options.append(
            discord.SelectOption(
                label=f"W.{iso_week} {weekday} {raid_date.strftime('%d/%m')}",
                value=value,
                default=value in selected_dates,
            )
        )

    return options


def create_scheduling_panel(
    guild_id: int | str,
    channel_id: int | str,
) -> str:
    data = load_scheduling(guild_id)

    panel_id = str(guild_id)

    existing_panel = data.setdefault("panels", {}).get(panel_id, {})

    data["panels"][panel_id] = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "message_id": existing_panel.get("message_id"),
        "absences": existing_panel.get("absences", {}),
    }

    save_scheduling(guild_id, data)
    return panel_id


def set_panel_message_id(
    guild_id: int | str,
    panel_id: str,
    message_id: int | str,
) -> None:
    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return

    panel["message_id"] = str(message_id)
    save_scheduling(guild_id, data)


def add_absence(
    guild_id: int | str,
    panel_id: str,
    *,
    user_id: int | str,
    display_name: str,
    dates: list[str],
    reason: str = "",
) -> bool:
    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return False

    absences = panel.setdefault("absences", {})
    user_id = str(user_id)
    reason = reason.strip()

    visible_dates = {d.isoformat() for d in get_raid_dates_ahead()}

    for date_iso in list(absences.keys()):
        if date_iso in visible_dates:
            absences[date_iso].pop(user_id, None)

            if not absences[date_iso]:
                del absences[date_iso]

    for date_iso in dates:
        absences.setdefault(date_iso, {})[user_id] = {
            "user_id": user_id,
            "name": display_name,
            "reason": reason,
        }

    save_scheduling(guild_id, data)
    return True


def clear_old_absences(guild_id: int | str, panel_id: str) -> int:
    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return 0

    absences = panel.setdefault("absences", {})
    today_iso = date.today().isoformat()

    removed = 0

    for date_iso in list(absences.keys()):
        if date_iso < today_iso:
            del absences[date_iso]
            removed += 1

    save_scheduling(guild_id, data)
    return removed


def build_scheduling_content(guild_id: int | str, panel_id: str) -> str:
    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return "Scheduling panel not found."

    absences = panel.get("absences", {})

    lines = [
        "## 🗓️ Raid Scheduling",
        "",
        "Use **Absent** if you already know you will miss a raid.",
        "",
        "━━━━━━━━━━━━━━━━━━",
    ]

    current_week = None

    for raid_date in get_raid_dates_ahead():
        date_iso = raid_date.isoformat()
        weekday = RAID_WEEKDAYS[raid_date.weekday()]
        iso_week = raid_date.isocalendar().week

        if iso_week != current_week:
            current_week = iso_week
            lines.append("")
            lines.append(f"### W.{iso_week}")

        players = absences.get(date_iso, {})
        names = sorted(
            entry.get("name", user_id)
            for user_id, entry in players.items()
        )

        if names:
            lines.append(
                f"**{weekday} {raid_date.strftime('%d/%m')}** — {len(names)} missing"
            )
            lines.append("• " + "\n• ".join(names))
        else:
            lines.append(
                f"**{weekday} {raid_date.strftime('%d/%m')}** — ✅ Full roster"
            )

    return "\n".join(lines)


async def refresh_scheduling_message(
    client,
    guild_id: int | str,
    panel_id: str,
) -> tuple[bool, str]:
    from views.scheduling.scheduling_message_view import SchedulingMessageView

    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return False, "Scheduling panel not found."

    clear_old_absences(guild_id, panel_id)

    data = load_scheduling(guild_id)
    panel = get_panel(data, panel_id)

    if not panel:
        return False, "Scheduling panel not found."

    channel_id = panel.get("channel_id")
    message_id = panel.get("message_id")

    if not channel_id or not message_id:
        return False, "Scheduling message missing channel or message id."

    channel = client.get_channel(int(channel_id)) or await client.fetch_channel(int(channel_id))
    message = await channel.fetch_message(int(message_id))

    await message.edit(
        content=build_scheduling_content(guild_id, panel_id),
        view=SchedulingMessageView(panel_id),
    )

    return True, "Scheduling updated."