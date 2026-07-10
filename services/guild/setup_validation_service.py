from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import discord

from services.guild.guild_settings_service import (
    get_scheduling_channel_id,
    get_scheduling_message_id,
    get_weakauras_channel_id,
    get_weakauras_message_id,
)


class ValidationState(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ValidationItem:
    key: str
    label: str
    state: ValidationState
    detail: str


@dataclass(frozen=True)
class SetupValidationReport:
    guild_id: int
    items: tuple[ValidationItem, ...]

    @property
    def is_healthy(self) -> bool:
        return all(item.state is ValidationState.OK for item in self.items)

    @property
    def error_count(self) -> int:
        return sum(item.state is ValidationState.ERROR for item in self.items)

    @property
    def warning_count(self) -> int:
        return sum(item.state is ValidationState.WARNING for item in self.items)


_REQUIRED_CHANNEL_PERMISSIONS = (
    "view_channel",
    "send_messages",
    "embed_links",
    "read_message_history",
)

_PERMISSION_LABELS = {
    "view_channel": "View Channel",
    "send_messages": "Send Messages",
    "embed_links": "Embed Links",
    "read_message_history": "Read Message History",
}


def _channel_from_id(
    guild: discord.Guild,
    channel_id: int | None,
) -> discord.TextChannel | None:
    if channel_id is None:
        return None
    channel = guild.get_channel(channel_id)
    return channel if isinstance(channel, discord.TextChannel) else None


def _validate_channel(
    guild: discord.Guild,
    *,
    key: str,
    label: str,
    channel_id: int | None,
) -> tuple[ValidationItem, discord.TextChannel | None]:
    if channel_id is None:
        return (
            ValidationItem(key, label, ValidationState.ERROR, "No channel configured."),
            None,
        )

    channel = _channel_from_id(guild, channel_id)
    if channel is None:
        return (
            ValidationItem(
                key,
                label,
                ValidationState.ERROR,
                "Configured channel no longer exists or is not a text channel.",
            ),
            None,
        )

    bot_member = guild.me
    if bot_member is None:
        return (
            ValidationItem(
                key,
                label,
                ValidationState.WARNING,
                f"Channel is {channel.mention}, but bot permissions could not be resolved.",
            ),
            channel,
        )

    permissions = channel.permissions_for(bot_member)
    missing = [
        _PERMISSION_LABELS[name]
        for name in _REQUIRED_CHANNEL_PERMISSIONS
        if not getattr(permissions, name, False)
    ]
    if missing:
        return (
            ValidationItem(
                key,
                label,
                ValidationState.ERROR,
                f"{channel.mention} is missing: {', '.join(missing)}.",
            ),
            channel,
        )

    return (
        ValidationItem(
            key,
            label,
            ValidationState.OK,
            f"{channel.mention} is configured and accessible.",
        ),
        channel,
    )


async def _validate_panel_message(
    *,
    key: str,
    label: str,
    channel: discord.TextChannel | None,
    message_id: int | None,
) -> ValidationItem:
    if channel is None:
        return ValidationItem(
            key,
            label,
            ValidationState.ERROR,
            "Cannot validate the panel until its channel is valid.",
        )

    if message_id is None:
        return ValidationItem(
            key,
            label,
            ValidationState.WARNING,
            "No stored panel message ID. The panel can be repaired.",
        )

    try:
        await channel.fetch_message(message_id)
    except discord.NotFound:
        return ValidationItem(
            key,
            label,
            ValidationState.WARNING,
            "Stored panel message was not found. The panel can be repaired.",
        )
    except discord.Forbidden:
        return ValidationItem(
            key,
            label,
            ValidationState.ERROR,
            "The bot cannot read the configured panel message.",
        )
    except discord.HTTPException:
        return ValidationItem(
            key,
            label,
            ValidationState.WARNING,
            "Discord could not verify the panel message right now.",
        )

    return ValidationItem(
        key,
        label,
        ValidationState.OK,
        f"Panel message `{message_id}` exists.",
    )


async def validate_guild_setup(guild: discord.Guild) -> SetupValidationReport:
    weakauras_channel_item, weakauras_channel = _validate_channel(
        guild,
        key="weakauras_channel",
        label="WeakAuras Channel",
        channel_id=get_weakauras_channel_id(guild.id),
    )
    scheduling_channel_item, scheduling_channel = _validate_channel(
        guild,
        key="scheduling_channel",
        label="Scheduling Channel",
        channel_id=get_scheduling_channel_id(guild.id),
    )

    weakauras_panel_item = await _validate_panel_message(
        key="weakauras_panel",
        label="WeakAuras Panel",
        channel=weakauras_channel,
        message_id=get_weakauras_message_id(guild.id),
    )
    scheduling_panel_item = await _validate_panel_message(
        key="scheduling_panel",
        label="Scheduling Panel",
        channel=scheduling_channel,
        message_id=get_scheduling_message_id(guild.id),
    )

    return SetupValidationReport(
        guild_id=guild.id,
        items=(
            weakauras_channel_item,
            weakauras_panel_item,
            scheduling_channel_item,
            scheduling_panel_item,
        ),
    )


async def repair_weakauras_panel(
    bot: discord.Client,
    guild: discord.Guild,
) -> tuple[bool, str]:
    from services.guild.weakauras_panel_service import ensure_weakauras_panel_for_guild

    return await ensure_weakauras_panel_for_guild(bot, guild)


async def repair_scheduling_panel(
    bot: discord.Client,
    guild: discord.Guild,
) -> tuple[bool, str]:
    from services.scheduling.scheduling_panel_service import ensure_scheduling_panel_for_guild

    return await ensure_scheduling_panel_for_guild(bot, guild)


async def repair_all_panels(
    bot: discord.Client,
    guild: discord.Guild,
) -> list[str]:
    results: list[str] = []
    for repair in (repair_weakauras_panel, repair_scheduling_panel):
        _, message = await repair(bot, guild)
        results.append(message)
    return results
