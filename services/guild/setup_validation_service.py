from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import discord

from services.panels.panel_registry import PERMANENT_PANELS, PERMANENT_PANELS_BY_KEY
from services.panels.permanent_panel_service import (
    PermanentPanelDefinition,
    ensure_permanent_panel,
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
    panel: PermanentPanelDefinition,
) -> tuple[ValidationItem, discord.TextChannel | None]:
    key = f"{panel.key}_channel"
    label = f"{panel.label} Channel"
    channel_id = panel.get_channel_id(guild.id)

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


def _first_message_id(panel: PermanentPanelDefinition, guild_id: int) -> int | None:
    for value in panel.get_message_ids(guild_id):
        if value in (None, "", 0):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


async def _validate_panel_message(
    panel: PermanentPanelDefinition,
    guild_id: int,
    channel: discord.TextChannel | None,
) -> ValidationItem:
    key = f"{panel.key}_panel"
    label = f"{panel.label} Panel"

    if channel is None:
        return ValidationItem(
            key,
            label,
            ValidationState.ERROR,
            "Cannot validate the panel until its channel is valid.",
        )

    message_id = _first_message_id(panel, guild_id)
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
    items: list[ValidationItem] = []

    for panel in PERMANENT_PANELS:
        channel_item, channel = _validate_channel(guild, panel)
        panel_item = await _validate_panel_message(panel, guild.id, channel)
        items.extend((channel_item, panel_item))

    return SetupValidationReport(guild_id=guild.id, items=tuple(items))


async def repair_panel(
    bot: discord.Client,
    guild: discord.Guild,
    panel_key: str,
) -> tuple[bool, str]:
    panel = PERMANENT_PANELS_BY_KEY.get(panel_key)
    if panel is None:
        return False, f"Unknown permanent panel: {panel_key}."
    return await ensure_permanent_panel(bot, guild, panel)


async def repair_weakauras_panel(
    bot: discord.Client,
    guild: discord.Guild,
) -> tuple[bool, str]:
    return await repair_panel(bot, guild, "weakauras")


async def repair_scheduling_panel(
    bot: discord.Client,
    guild: discord.Guild,
) -> tuple[bool, str]:
    return await repair_panel(bot, guild, "scheduling")


async def repair_all_panels(
    bot: discord.Client,
    guild: discord.Guild,
) -> list[str]:
    results: list[str] = []
    for panel in PERMANENT_PANELS:
        _, message = await ensure_permanent_panel(bot, guild, panel)
        results.append(message)
    return results
