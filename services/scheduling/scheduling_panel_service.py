from __future__ import annotations

import discord

from data.scheduling_store import get_panel, load_scheduling
from services.guild.guild_settings_service import (
    get_scheduling_channel_id,
    get_scheduling_message_id,
    set_scheduling_message_id,
)
from services.scheduling.scheduling_service import (
    build_scheduling_content,
    clear_old_absences,
    create_scheduling_panel,
    set_panel_message_id,
)
from views.scheduling.scheduling_message_view import SchedulingMessageView


async def ensure_scheduling_panel_for_guild(
    bot,
    guild: discord.Guild,
) -> tuple[bool, str]:
    channel_id = get_scheduling_channel_id(guild.id)

    if not channel_id:
        return False, "No Scheduling channel configured."

    channel = guild.get_channel(channel_id)

    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except Exception:
            return False, "Configured Scheduling channel not found."

    panel_id = str(guild.id)

    create_scheduling_panel(
        guild.id,
        channel.id,
    )

    clear_old_absences(
        guild.id,
        panel_id,
    )

    # Keep compatibility with both places where the permanent panel message ID
    # has historically been stored. This prevents weekday changes from posting
    # a replacement panel while leaving the original message unchanged.
    data = load_scheduling(guild.id)
    panel = get_panel(data, panel_id) or {}

    candidate_message_ids: list[int] = []

    settings_message_id = get_scheduling_message_id(guild.id)
    panel_message_id = panel.get("message_id")

    for value in (settings_message_id, panel_message_id):
        if value in (None, "", 0):
            continue
        try:
            message_id = int(value)
        except (TypeError, ValueError):
            continue
        if message_id not in candidate_message_ids:
            candidate_message_ids.append(message_id)

    for message_id in candidate_message_ids:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(
                content=build_scheduling_content(guild.id, panel_id),
                view=SchedulingMessageView(panel_id),
            )

            set_panel_message_id(guild.id, panel_id, msg.id)
            set_scheduling_message_id(guild.id, msg.id)

            return True, "Scheduling panel updated."

        except discord.NotFound:
            continue
        except Exception as e:
            return False, f"Failed to update existing Scheduling panel: {e}"

    # Neither stored message ID resolved in the configured channel. Clear the
    # settings copy before creating a single new permanent panel.
    set_scheduling_message_id(guild.id, None)

    try:
        msg = await channel.send(
            content=build_scheduling_content(guild.id, panel_id),
            view=SchedulingMessageView(panel_id),
        )

        set_panel_message_id(guild.id, panel_id, msg.id)
        set_scheduling_message_id(guild.id, msg.id)

        return True, "Scheduling panel posted."
    except Exception as e:
        return False, f"Failed to post Scheduling panel: {e}"
