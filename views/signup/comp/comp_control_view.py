from __future__ import annotations

import asyncio

import discord

from services.comp.comp_control_service import (
    ACTION_LABELS,
    apply_comp_player_action,
    cancel_posted_comp,
    get_comp_control_players,
)
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.emoji_helpers import parse_button_emoji
from utils.permissions import can_manage_raid_tools
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


async def _send_comp_control_error(
    interaction: discord.Interaction,
    message: str,
) -> None:
    if interaction.response.is_done():
        msg = await interaction.followup.send(
            message,
            ephemeral=True,
            wait=True,
        )
        asyncio.create_task(
            delete_message_after(msg, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )
        return

    await interaction.response.send_message(message, ephemeral=True)
    asyncio.create_task(
        delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
    )


def _player_label(player: dict) -> str:
    return (
        (player.get("name") or "").strip()
        or (player.get("display_name") or "").strip()
        or str(player.get("user_id"))
    )


def _player_description(player: dict) -> str:
    wow_class = player.get("class") or "Unknown"
    spec = player.get("spec") or "Unknown"
    status = player.get("status") or "Unknown"
    return f"{wow_class} • {spec} • {status}"[:100]


def build_comp_player_options(
    raid_id: str,
    *,
    selected_user_id: str | None = None,
) -> list[discord.SelectOption]:
    players = get_comp_control_players(raid_id)
    options: list[discord.SelectOption] = []

    for player in players[:25]:
        user_id = str(player.get("user_id"))
        options.append(
            discord.SelectOption(
                label=_player_label(player)[:100],
                value=user_id,
                description=_player_description(player),
                default=user_id == str(selected_user_id),
            )
        )

    if not options:
        options.append(
            discord.SelectOption(
                label="No players found",
                value="__none__",
                description="This comp has no players to manage.",
            )
        )

    return options


def build_comp_action_options(
    *,
    selected_action: str | None = None,
) -> list[discord.SelectOption]:
    return [
        discord.SelectOption(
            label=label,
            value=value,
            default=value == str(selected_action),
        )
        for value, label in ACTION_LABELS.items()
    ]


class CompPlayerSelect(discord.ui.Select):
    def __init__(
        self,
        raid_id: str,
        *,
        selected_user_id: str | None = None,
    ):
        self.raid_id = str(raid_id)

        super().__init__(
            placeholder="Select player...",
            min_values=1,
            max_values=1,
            options=build_comp_player_options(
                self.raid_id,
                selected_user_id=selected_user_id,
            ),
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "__none__":
            await interaction.response.defer()
            return

        self.view.selected_user_id = self.values[0]
        await self.view.refresh_panel(interaction)


class CompActionSelect(discord.ui.Select):
    def __init__(self, *, selected_action: str | None = None):
        super().__init__(
            placeholder="Select comp action...",
            min_values=1,
            max_values=1,
            options=build_comp_action_options(selected_action=selected_action),
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_action = self.values[0]
        await self.view.refresh_panel(interaction)


class ApplyCompActionButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Apply",
            emoji=parse_button_emoji("sign"),
            style=discord.ButtonStyle.success,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_comp_control_error(
                interaction,
                "You do not have access to comp control.",
            )
            return

        view = self.view

        if not view.selected_user_id or not view.selected_action:
            await _send_comp_control_error(
                interaction,
                "Select a player and action first.",
            )
            return

        ok, message = await apply_comp_player_action(
            channel=interaction.channel,
            raid_id=view.raid_id,
            user_id=view.selected_user_id,
            action=view.selected_action,
        )

        if not ok:
            await _send_comp_control_error(interaction, f"⚠ {message}")
            return

        await interaction.response.edit_message(
            content=f"✅ {message}",
            view=CompControlView(view.raid_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class OpenRaidSettingsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Raid Settings",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_comp_control_error(
                interaction,
                "You do not have access to raid settings.",
            )
            return

        from views.signup.settings.raid_settings_view import RaidSettingsView

        await interaction.response.edit_message(
            content="Raid settings",
            view=RaidSettingsView(self.view.raid_id),
        )


class CloseCompControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            emoji=parse_button_emoji("leave"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Comp control closed.",
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CancelCompButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Cancel Comp",
            emoji=parse_button_emoji("cancel_raid"),
            style=discord.ButtonStyle.danger,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await _send_comp_control_error(
                interaction,
                "You do not have access to comp control.",
            )
            return

        view = self.view

        ok, message = await cancel_posted_comp(
            channel=interaction.channel,
            raid_id=view.raid_id,
        )

        if not ok:
            await _send_comp_control_error(interaction, f"⚠ {message}")
            return

        await interaction.response.edit_message(
            content=f"✅ {message}",
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CompControlView(discord.ui.View):
    def __init__(
        self,
        raid_id: str,
        *,
        selected_user_id: str | None = None,
        selected_action: str | None = None,
    ):
        super().__init__(timeout=120)
        self.raid_id = str(raid_id)
        self.selected_user_id = selected_user_id
        self.selected_action = selected_action

        self.add_item(
            CompPlayerSelect(
                self.raid_id,
                selected_user_id=self.selected_user_id,
            )
        )
        self.add_item(
            CompActionSelect(
                selected_action=self.selected_action,
            )
        )
        self.add_item(ApplyCompActionButton())
        self.add_item(OpenRaidSettingsButton())
        self.add_item(CloseCompControlButton())
        self.add_item(CancelCompButton())

    async def refresh_panel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Comp control panel",
            view=CompControlView(
                self.raid_id,
                selected_user_id=self.selected_user_id,
                selected_action=self.selected_action,
            ),
        )