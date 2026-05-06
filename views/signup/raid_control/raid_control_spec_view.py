import asyncio
import discord
import config

from services.raid.raid_control_service import (
    get_players,
    get_valid_specs_for_player,
    change_player_spec,
)
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


async def _send_spec_error(
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
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )


class RaidControlSpecPlayerSelect(discord.ui.Select):
    def __init__(self, raid_id: str):
        self.raid_id = raid_id

        players = get_players(raid_id)
        options = []

        for player in players[:25]:
            name = player.get("name") or "Unknown"
            wow_class = player.get("class") or "Unknown"
            spec = player.get("spec") or "Unknown"
            status = player.get("status") or "Unknown"

            options.append(
                discord.SelectOption(
                    label=name[:100],
                    value=str(player["user_id"]),
                    description=f"{wow_class} • {spec} • {status}"[:100],
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

        super().__init__(
            placeholder="Select player...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]

        if selected_value == "__none__":
            await interaction.response.edit_message(
                content="No players found.",
                view=None,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content="Select a new spec for this player:",
            view=RaidControlSpecSelectView(self.view.raid_id, selected_value),
        )


class RaidControlSpecSelect(discord.ui.Select):
    def __init__(self, raid_id: str, user_id: str):
        self.raid_id = raid_id
        self.user_id = user_id

        options = []

        valid_specs = get_valid_specs_for_player(raid_id, user_id)

        for item in valid_specs:
            spec_name = item["spec"]
            role_name = item["role"]
            emoji = None

            raw = config.SPEC_EMOJIS.get(spec_name)
            if raw:
                try:
                    emoji = discord.PartialEmoji.from_str(raw)
                except Exception:
                    emoji = None

            options.append(
                discord.SelectOption(
                    label=spec_name[:100],
                    value=spec_name,
                    description=f"Role: {role_name}"[:100],
                    emoji=emoji,
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No spec choices available",
                    value="__none__",
                    description="This player has no valid specs.",
                )
            )

        super().__init__(
            placeholder="Select new spec...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]

        if selected_value == "__none__":
            await _send_spec_error(interaction, "No valid spec choices available.")
            return

        ok = change_player_spec(
            self.raid_id,
            self.user_id,
            selected_value,
        )

        if not ok:
            await _send_spec_error(
                interaction,
                "Could not change that player's spec. The raid or signup may no longer exist.",
            )
            return

        try:
            refreshed = await refresh_signup_message_by_id(interaction.channel, int(self.raid_id))
            if not refreshed:
                await _send_spec_error(
                    interaction,
                    "Player spec updated, but the raid signup no longer exists.",
                )
                return
        except Exception as e:
            await _send_spec_error(
                interaction,
                f"Spec updated, but failed to refresh raid: {e}",
            )
            return

        from views.signup.raid_control.raid_control_view import RaidControlView

        await interaction.response.edit_message(
            content=f"Player spec changed to **{selected_value}**.",
            view=RaidControlView(self.raid_id),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidControlSpecPlayerView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)
        self.raid_id = raid_id
        self.add_item(RaidControlSpecPlayerSelect(raid_id))


class RaidControlSpecSelectView(discord.ui.View):
    def __init__(self, raid_id: str, user_id: str):
        super().__init__(timeout=120)
        self.raid_id = raid_id
        self.user_id = user_id
        self.add_item(RaidControlSpecSelect(raid_id, user_id))