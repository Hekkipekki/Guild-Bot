from __future__ import annotations

import asyncio

import discord

from services.comp.comp_message_service import post_comp_message
from services.comp.roster_comp_service import analyze_roster_comp
from services.raid.raid_control_service import (
    get_player_entry,
    remove_player_signup,
    set_player_status,
)
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)
from views.signup.comp.comp_choice_view import CompChoiceView
from views.signup.raid_control.raid_control_components import (
    RaidControlActionSelect,
    RaidControlPlayerSelect,
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


async def _edit_panel(
    interaction: discord.Interaction,
    *,
    content: str,
    view: discord.ui.View | None,
) -> None:
    await interaction.response.edit_message(
        content=content,
        view=view,
    )


async def _close_panel(
    interaction: discord.Interaction,
    *,
    content: str,
    delete_after_seconds: int = RAID_CONTROL_AUTO_DELETE_SECONDS,
) -> None:
    await interaction.response.edit_message(
        content=content,
        view=None,
    )
    asyncio.create_task(
        delete_interaction_after(interaction, delete_after_seconds)
    )


async def _refresh_signup_or_error(
    interaction: discord.Interaction,
    raid_id: str,
) -> bool:
    try:
        refreshed = await refresh_signup_message_by_id(interaction.channel, int(raid_id))
        if not refreshed:
            await _send_raid_control_error(
                interaction,
                "Raid updated, but the signup message no longer exists.",
            )
            return False
        return True
    except Exception as e:
        await _send_raid_control_error(
            interaction,
            f"Raid updated, but failed to refresh signup: {e}",
        )
        return False


async def _open_change_spec_panel(
    interaction: discord.Interaction,
    raid_id: str,
) -> None:
    from views.signup.raid_control.raid_control_spec_view import RaidControlSpecPlayerView

    await _edit_panel(
        interaction,
        content="Select a player to change spec.",
        view=RaidControlSpecPlayerView(raid_id),
    )


async def _open_raid_settings_panel(
    interaction: discord.Interaction,
    raid_id: str,
) -> None:
    from views.signup.settings.raid_settings_view import RaidSettingsView

    await _edit_panel(
        interaction,
        content="Raid settings",
        view=RaidSettingsView(raid_id),
    )


async def _open_attendance_panel(
    interaction: discord.Interaction,
    raid_id: str,
) -> None:
    from views.signup.raid_control.attendance_view import (
        AttendanceView,
        build_attendance_panel_content,
    )

    await _edit_panel(
        interaction,
        content=build_attendance_panel_content(raid_id),
        view=AttendanceView(raid_id),
    )


async def _handle_build_comp(
    interaction: discord.Interaction,
    raid_id: str,
) -> None:
    state, payload = analyze_roster_comp(raid_id)

    if state == "error" or payload is None:
        await _send_raid_control_error(
            interaction,
            "Could not build comp. The raid may no longer exist.",
        )
        return

    if state == "ambiguous":
        await _edit_panel(
            interaction,
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

        await _edit_panel(
            interaction,
            content=f"Select {count} {role} {player_word} to bench.",
            view=CompBenchView(comp_data),
        )
        return

    ok, message = await post_comp_message(
        interaction.channel,
        comp_data,
    )

    if not ok:
        await _close_panel(
            interaction,
            content=message,
            delete_after_seconds=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
        )
        return

    await _close_panel(
        interaction,
        content="Comp message posted.",
        delete_after_seconds=RAID_CONTROL_AUTO_DELETE_SECONDS,
    )


class ChangeSpecRaidControlButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Change Spec",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            await _open_change_spec_panel(interaction, view.raid_id)
        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Change Spec failed: {type(e).__name__}: {e}",
            )


class RaidSettingsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Raid Settings",
            emoji=parse_button_emoji("config"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            await _open_raid_settings_panel(interaction, view.raid_id)
        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Raid Settings failed: {type(e).__name__}: {e}",
            )


class AttendanceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Attendance",
            emoji=parse_button_emoji("create_template"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            await _open_attendance_panel(interaction, view.raid_id)
        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Attendance panel failed: {type(e).__name__}: {e}",
            )


class BuildCompButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Build Comp",
            emoji=parse_button_emoji("create_raid"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            await _handle_build_comp(interaction, view.raid_id)
        except Exception as e:
            await _send_raid_control_error(
                interaction,
                f"Build Comp failed: {type(e).__name__}: {e}",
            )


class PlayerNoteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Note",
            emoji=parse_button_emoji("note"),
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        selected_user_id = view.selected_user_id

        if not selected_user_id:
            await _send_raid_control_error(
                interaction,
                "Select a player first.",
            )
            return

        entry = get_player_entry(view.raid_id, selected_user_id)
        if not entry:
            await _send_raid_control_error(
                interaction,
                "Could not load that player's signup entry.",
            )
            return

        player_name = (
            (entry.get("name") or "").strip()
            or (entry.get("display_name") or "").strip()
            or f"<@{selected_user_id}>"
        )
        status = entry.get("status") or "Unknown"
        note = (entry.get("note") or "").strip()

        await interaction.response.send_message(
            (
                f"**Player:** {player_name}\n"
                f"**Status:** {status}\n"
                f"**Note:** {note or '-'}"
            ),
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class RaidControlView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)
        self.raid_id = str(raid_id)
        self.selected_user_id: str | None = None
        self.selected_action: str | None = None

        self.add_item(RaidControlPlayerSelect(self.raid_id))
        self.add_item(RaidControlActionSelect())

        self.add_item(ChangeSpecRaidControlButton())
        self.add_item(RaidSettingsButton())
        self.add_item(AttendanceButton())
        self.add_item(BuildCompButton())
        self.add_item(PlayerNoteButton())

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

            await _edit_panel(
                interaction,
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