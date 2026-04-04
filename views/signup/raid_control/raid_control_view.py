import asyncio
import discord

from services.comp.roster_comp_service import analyze_roster_comp
from services.comp.comp_message_service import post_comp_message
from services.raid.raid_control_service import (
    set_player_status,
    remove_player_signup,
)
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from views.signup.comp.comp_choice_view import CompChoiceView
from views.signup.raid_control.raid_control_components import (
    RaidControlPlayerSelect,
    RaidControlActionSelect,
)
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


async def _send_raid_control_error(
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


async def _refresh_signup_or_error(
    interaction: discord.Interaction,
    raid_id: str,
) -> bool:
    refreshed = await refresh_signup_message_by_id(interaction.channel, int(raid_id))
    if refreshed:
        return True

    await _send_raid_control_error(
        interaction,
        "Player updated, but the raid signup no longer exists.",
    )
    return False


class ChangeSpecRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Change Spec",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            from views.signup.raid_control.raid_control_spec_view import (
                RaidControlSpecPlayerView,
            )

            view = self.view

            await interaction.response.edit_message(
                content="Select a player to change spec for this raid only.",
                view=RaidControlSpecPlayerView(view.raid_id),
            )

        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Change Spec failed: {type(e).__name__}: {e}",
            )


class RaidSettingsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Raid Settings",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            from views.signup.settings.raid_settings_view import RaidSettingsView

            view = self.view

            await interaction.response.edit_message(
                content="Raid settings panel",
                view=RaidSettingsView(view.raid_id),
            )

        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Raid Settings failed: {type(e).__name__}: {e}",
            )


class AttendanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Attendance",
            style=discord.ButtonStyle.primary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            from views.signup.raid_control.attendance_view import (
                AttendanceView,
                build_attendance_panel_content,
            )

            view = self.view

            await interaction.response.edit_message(
                content=build_attendance_panel_content(view.raid_id),
                view=AttendanceView(view.raid_id),
            )

        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Attendance panel failed: {type(e).__name__}: {e}",
            )


class BuildCompButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Build Comp",
            style=discord.ButtonStyle.success,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view

            state, payload = analyze_roster_comp(view.raid_id)

            if state == "error" or not payload:
                await _send_raid_control_error(
                    interaction,
                    "Could not build comp. The raid may no longer exist.",
                )
                return

            if state == "ambiguous":
                await interaction.response.edit_message(
                    content="Two valid 10-man comps were found. Choose which one to continue with.",
                    view=CompChoiceView(
                        payload["option_226"],
                        payload["option_235"],
                    ),
                )
                return

            comp_data = payload["comp_data"]
            steps = comp_data.get("bench_choice_steps", [])

            if steps:
                from views.signup.comp.comp_bench_view import CompBenchView

                first_step = steps[0]
                count = int(first_step.get("count_to_bench", 0) or 0)
                role = first_step.get("role") or "player"
                player_word = "player" if count == 1 else "players"

                await interaction.response.edit_message(
                    content=f"Select {count} {role} {player_word} to bench.",
                    view=CompBenchView(comp_data),
                )
                return

            ok, message = await post_comp_message(
                interaction.channel,
                comp_data,
            )

            if not ok:
                await interaction.response.edit_message(
                    content=message,
                    view=None,
                )
                asyncio.create_task(
                    delete_interaction_after(
                        interaction,
                        ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                    )
                )
                return

            await interaction.response.edit_message(
                content="Comp message posted.",
                view=None,
            )
            asyncio.create_task(
                delete_interaction_after(
                    interaction,
                    RAID_CONTROL_AUTO_DELETE_SECONDS,
                )
            )

        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Build Comp failed: {type(e).__name__}: {e}",
            )


class CloseRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Raid control closed.",
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidControlView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)
        self.raid_id = raid_id
        self.selected_user_id = None
        self.selected_action = None

        # Row 0
        self.add_item(RaidControlPlayerSelect(raid_id))

        # Row 1
        self.add_item(RaidControlActionSelect())

        # Row 2
        self.add_item(ChangeSpecRaidControlButton())
        self.add_item(RaidSettingsButton())
        self.add_item(AttendanceButton())
        self.add_item(BuildCompButton())
        self.add_item(CloseRaidControlButton())

    async def try_apply_action(self, interaction: discord.Interaction):
        try:
            if not self.selected_user_id or not self.selected_action:
                await interaction.response.defer()
                return

            if self.selected_action == "remove":
                ok = remove_player_signup(self.raid_id, self.selected_user_id)
                action_text = "removed"
            else:
                ok = set_player_status(
                    self.raid_id,
                    self.selected_user_id,
                    self.selected_action,
                )
                action_text = f"set to {self.selected_action}"

            if not ok:
                await _send_raid_control_error(
                    interaction,
                    "Could not update that player. The raid or signup may no longer exist.",
                )
                return

            refreshed = await _refresh_signup_or_error(interaction, self.raid_id)
            if not refreshed:
                return

            self.selected_user_id = None
            self.selected_action = None

            await interaction.response.edit_message(
                content=f"Player {action_text}.",
                view=RaidControlView(self.raid_id),
            )
            asyncio.create_task(
                delete_interaction_after(
                    interaction,
                    RAID_CONTROL_AUTO_DELETE_SECONDS,
                )
            )

        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Raid control failed: {type(e).__name__}: {e}",
            )