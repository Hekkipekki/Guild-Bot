from __future__ import annotations

import discord

from services.guild.guild_settings_service import (
    get_scheduling_channel_id,
    get_scheduling_message_id,
    set_scheduling_message_id,
)

from services.scheduling.scheduling_service import (
    create_scheduling_panel,
    set_panel_message_id,
    build_scheduling_content,
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

    # Stable panel id: one scheduling panel per guild
    panel_id = str(guild.id)

    # Ensure scheduling.json has a panel block for this guild
    create_scheduling_panel(
        guild.id,
        channel.id,
    )

    message_id = get_scheduling_message_id(guild.id)

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)

            await msg.edit(
                content=build_scheduling_content(guild.id, panel_id),
                view=SchedulingMessageView(panel_id),
            )

            set_panel_message_id(guild.id, panel_id, msg.id)

            return True, "Scheduling panel updated."

        except discord.NotFound:
            set_scheduling_message_id(guild.id, None)

        except Exception as e:
            return False, f"Failed to update existing Scheduling panel: {e}"

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