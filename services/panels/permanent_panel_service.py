from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable

import discord


PanelPrepareHook = Callable[[discord.Guild, discord.abc.Messageable], Awaitable[None]]
PanelPayloadBuilder = Callable[[discord.Guild], dict]
PanelIdGetter = Callable[[int], Iterable[int | str | None]]
PanelIdSetter = Callable[[int, int | None], None]
ChannelIdGetter = Callable[[int], int | None]


@dataclass(frozen=True)
class PermanentPanelDefinition:
    key: str
    label: str
    get_channel_id: ChannelIdGetter
    get_message_ids: PanelIdGetter
    set_message_id: PanelIdSetter
    build_payload: PanelPayloadBuilder
    prepare: PanelPrepareHook | None = None
    suppress_embeds: bool = False


def _candidate_message_ids(values: Iterable[int | str | None]) -> list[int]:
    result: list[int] = []
    for value in values:
        if value in (None, "", 0):
            continue
        try:
            message_id = int(value)
        except (TypeError, ValueError):
            continue
        if message_id not in result:
            result.append(message_id)
    return result


async def _resolve_channel(
    guild: discord.Guild,
    channel_id: int,
) -> discord.abc.Messageable | None:
    channel = guild.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def ensure_permanent_panel(
    bot: discord.Client,
    guild: discord.Guild,
    definition: PermanentPanelDefinition,
) -> tuple[bool, str]:
    del bot  # Reserved for future shared lifecycle hooks.

    channel_id = definition.get_channel_id(guild.id)
    if not channel_id:
        return False, f"No {definition.label} channel configured."

    channel = await _resolve_channel(guild, channel_id)
    if channel is None or not hasattr(channel, "fetch_message") or not hasattr(channel, "send"):
        return False, f"Configured {definition.label} channel not found."

    if definition.prepare is not None:
        try:
            await definition.prepare(guild, channel)
        except Exception as exc:
            return False, f"Failed to prepare {definition.label} panel: {exc}"

    payload = definition.build_payload(guild)
    edit_payload = dict(payload)
    send_payload = dict(payload)
    if definition.suppress_embeds:
        edit_payload["suppress"] = True
        send_payload["suppress_embeds"] = True

    for message_id in _candidate_message_ids(definition.get_message_ids(guild.id)):
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(**edit_payload)
            definition.set_message_id(guild.id, message.id)
            return True, f"{definition.label} panel updated."
        except discord.NotFound:
            continue
        except discord.Forbidden:
            return False, f"Failed to update existing {definition.label} panel: missing permissions."
        except discord.HTTPException as exc:
            return False, f"Failed to update existing {definition.label} panel: {exc}"
        except Exception as exc:
            return False, f"Failed to update existing {definition.label} panel: {exc}"

    definition.set_message_id(guild.id, None)

    try:
        message = await channel.send(**send_payload)
        definition.set_message_id(guild.id, message.id)
        return True, f"{definition.label} panel posted."
    except discord.Forbidden:
        return False, f"Failed to post {definition.label} panel: missing permissions."
    except discord.HTTPException as exc:
        return False, f"Failed to post {definition.label} panel: {exc}"
    except Exception as exc:
        return False, f"Failed to post {definition.label} panel: {exc}"
