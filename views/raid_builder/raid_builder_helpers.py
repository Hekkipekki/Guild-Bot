from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from services.guild.guild_settings_service import (
    get_default_leader,
    get_default_description,
)
from services.signup.signup_preset_service import build_signup_payload


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def default_raid_data(guild_id: int, channel_id: int) -> dict:
    now = datetime.now(SWEDEN_TZ)

    return {
        "title": "New Raid Signup",
        "description": get_default_description(guild_id) or "Raid signup",
        "leader": get_default_leader(guild_id) or "Raid Leader",
        "date": now.strftime("%Y-%m-%d"),
        "time": "19:30",
        "channel_id": channel_id,
        "is_recurring": False,
        "recurring_interval_days": None,
    }


def recurring_text(raid_data: dict) -> str:
    is_recurring = bool(raid_data.get("is_recurring", False))
    interval = raid_data.get("recurring_interval_days")

    if not is_recurring:
        return "No"

    if interval:
        return f"Yes — every {interval} day(s)"

    return "Yes"


def build_preview_embed(guild: discord.Guild, raid_data: dict) -> discord.Embed:
    title = raid_data.get("title", "New Raid Signup")
    description = raid_data.get("description", "") or "-"
    leader = raid_data.get("leader", "") or "-"
    date_str = raid_data.get("date", "-")
    time_str = raid_data.get("time", "-")
    channel_id = raid_data.get("channel_id")

    channel_text = f"<#{channel_id}>" if channel_id else "-"

    embed = discord.Embed(
        title=f"Raid Builder — {guild.name}",
        description="Configure a new raid signup.",
        color=discord.Color.purple(),
    )
    embed.add_field(name="Title", value=title, inline=False)
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="Leader", value=leader, inline=False)
    embed.add_field(name="Date", value=date_str, inline=True)
    embed.add_field(name="Time", value=time_str, inline=True)
    embed.add_field(name="Channel", value=channel_text, inline=True)
    embed.add_field(name="Recurring", value=recurring_text(raid_data), inline=False)
    embed.set_footer(text="Use the buttons below to edit and post the raid.")

    return embed


def build_signup_from_raid_data(
    guild_id: int,
    raid_data: dict,
) -> tuple[bool, dict | None, str | None]:
    date_str = (raid_data.get("date") or "").strip()
    time_str = (raid_data.get("time") or "").strip()

    try:
        year, month, day = [int(x) for x in date_str.split("-")]
    except ValueError:
        return False, None, "Date must be in YYYY-MM-DD format."

    try:
        hour, minute = [int(x) for x in time_str.split(":")]
    except ValueError:
        return False, None, "Time must be in HH:MM format."

    try:
        dt = datetime(year, month, day, hour, minute, tzinfo=SWEDEN_TZ)
    except ValueError as e:
        return False, None, f"Invalid date/time: {e}"

    start_ts = int(dt.timestamp())

    signup = build_signup_payload(
        guild_id=guild_id,
        title=raid_data.get("title", "New Raid Signup"),
        description=raid_data.get("description", ""),
        leader=raid_data.get("leader", ""),
        start_ts=start_ts,
        channel_id=raid_data.get("channel_id"),
    )

    signup["is_recurring"] = bool(raid_data.get("is_recurring", False))
    signup["recurring_interval_days"] = raid_data.get("recurring_interval_days")
    signup["recurring_created_next"] = False

    return True, signup, None