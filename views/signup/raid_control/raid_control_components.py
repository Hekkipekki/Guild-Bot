from __future__ import annotations

import discord

from services.raid.raid_control_service import get_players

from constants.statuses import (
    SIGNUP_STATUS_SIGN,
    SIGNUP_STATUS_BENCH,
    SIGNUP_STATUS_LATE,
    SIGNUP_STATUS_TENTATIVE,
    SIGNUP_STATUS_ABSENCE,
    STATUS_LABELS,
)


ACTION_VALUES = {
    SIGNUP_STATUS_SIGN: STATUS_LABELS[SIGNUP_STATUS_SIGN],
    SIGNUP_STATUS_BENCH: STATUS_LABELS[SIGNUP_STATUS_BENCH],
    SIGNUP_STATUS_LATE: STATUS_LABELS[SIGNUP_STATUS_LATE],
    SIGNUP_STATUS_TENTATIVE: STATUS_LABELS[SIGNUP_STATUS_TENTATIVE],
    SIGNUP_STATUS_ABSENCE: STATUS_LABELS[SIGNUP_STATUS_ABSENCE],
    "remove": "Remove Signup",
}


def _get_player_display_name(player: dict) -> str:
    return (
        (player.get("name") or "").strip()
        or (player.get("display_name") or "").strip()
        or "Unknown"
    )


def _build_player_description(player: dict) -> str:
    wow_class = player.get("class") or "Unknown"
    spec = player.get("spec") or "Unknown"
    status = player.get("status") or "Unknown"

    return f"{wow_class} • {spec} • {status}"[:100]


def build_raid_control_player_options(
    raid_id: str,
    *,
    selected_user_id: str | None = None,
) -> list[discord.SelectOption]:
    players = get_players(raid_id)
    options: list[discord.SelectOption] = []

    for player in players[:25]:
        user_id = str(player.get("user_id"))

        options.append(
            discord.SelectOption(
                label=_get_player_display_name(player)[:100],
                value=user_id,
                description=_build_player_description(player),
                default=user_id == str(selected_user_id),
            )
        )

    if not options:
        options.append(
            discord.SelectOption(
                label="No players found",
                value="__none__",
                description="There are no signups to manage.",
            )
        )

    return options


def build_raid_control_action_options(
    *,
    selected_action: str | None = None,
) -> list[discord.SelectOption]:
    return [
        discord.SelectOption(
            label=label,
            value=value,
            default=value == str(selected_action),
        )
        for value, label in ACTION_VALUES.items()
    ]


class RaidControlPlayerSelect(discord.ui.Select):
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
            options=build_raid_control_player_options(
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

        if not self.view.selected_action:
            await interaction.response.defer()
            return

        await self.view.try_apply_action(interaction)


class RaidControlActionSelect(discord.ui.Select):
    def __init__(self, *, selected_action: str | None = None):
        super().__init__(
            placeholder="Select action...",
            min_values=1,
            max_values=1,
            options=build_raid_control_action_options(
                selected_action=selected_action,
            ),
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_action = self.values[0]

        if not self.view.selected_user_id:
            await interaction.response.defer()
            return

        await self.view.try_apply_action(interaction)