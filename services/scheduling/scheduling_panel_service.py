from __future__ import annotations

import discord

from data.scheduling_store import get_panel, load_scheduling
from services.guild.guild_settings_service import (
    get_scheduling_channel_id,
    get_scheduling_message_id,
    set_scheduling_message_id,
)
from services.panels.permanent_panel_service import (
    PermanentPanelDefinition,
    ensure_permanent_panel,
)
from services.scheduling.scheduling_service import (
    build_scheduling_content,
    clear_old_absences,
    create_scheduling_panel,
    set_panel_message_id,
)
from views.scheduling.scheduling_message_view import SchedulingMessageView


def _panel_id(guild_id: int) -> str:
    return str(guild_id)


def _get_scheduling_message_ids(guild_id: int):
    panel = get_panel(load_scheduling(guild_id), _panel_id(guild_id)) or {}
    return (
        get_scheduling_message_id(guild_id),
        panel.get("message_id"),
    )


def _set_scheduling_panel_message_id(guild_id: int, message_id: int | None) -> None:
    set_scheduling_message_id(guild_id, message_id)
    if message_id is not None:
        set_panel_message_id(guild_id, _panel_id(guild_id), message_id)


async def _prepare_scheduling_panel(
    guild: discord.Guild,
    channel: discord.abc.Messageable,
) -> None:
    create_scheduling_panel(guild.id, channel.id)
    clear_old_absences(guild.id, _panel_id(guild.id))


def _build_scheduling_payload(guild: discord.Guild) -> dict:
    panel_id = _panel_id(guild.id)
    return {
        "content": build_scheduling_content(guild.id, panel_id),
        "view": SchedulingMessageView(panel_id),
    }


SCHEDULING_PANEL = PermanentPanelDefinition(
    key="scheduling",
    label="Scheduling",
    get_channel_id=get_scheduling_channel_id,
    get_message_ids=_get_scheduling_message_ids,
    set_message_id=_set_scheduling_panel_message_id,
    build_payload=_build_scheduling_payload,
    prepare=_prepare_scheduling_panel,
)


async def ensure_scheduling_panel_for_guild(
    bot: discord.Client,
    guild: discord.Guild,
) -> tuple[bool, str]:
    return await ensure_permanent_panel(bot, guild, SCHEDULING_PANEL)
