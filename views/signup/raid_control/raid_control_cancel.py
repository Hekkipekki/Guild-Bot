from __future__ import annotations

import traceback

import discord

from data.signup_store import find_message_signup, load_signups
from services.raid.raid_cancel_guard_service import cancel_signup_raid_with_guard
from services.raid.raid_lifecycle_service import is_recurring_signup

from utils.panel_helpers import send_panel_error, close_panel, safe_panel_edit
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS


class CancelRaidConfirmationView(discord.ui.View):
    def __init__(self, raid_id: str, *, is_recurring: bool):
        super().__init__(timeout=120)
        self.raid_id = str(raid_id)

        if is_recurring:
            self.add_item(CancelAndPlanNextButton(self.raid_id))

        self.add_item(CancelSeriesButton(self.raid_id, is_recurring=is_recurring))
        self.add_item(KeepRaidButton(self.raid_id))


class CancelAndPlanNextButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Cancel This Raid + Plan Next",
            style=discord.ButtonStyle.danger,
        )
        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await _perform_cancel(
            interaction,
            raid_id=self.raid_id,
            plan_next_occurrence=True,
        )


class CancelSeriesButton(discord.ui.Button):
    def __init__(self, raid_id: str, *, is_recurring: bool):
        super().__init__(
            label="Cancel Series" if is_recurring else "Cancel Raid",
            style=discord.ButtonStyle.secondary if is_recurring else discord.ButtonStyle.danger,
        )
        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        await _perform_cancel(
            interaction,
            raid_id=self.raid_id,
            plan_next_occurrence=False,
        )


class KeepRaidButton(discord.ui.Button):
    def __init__(self, raid_id: str):
        super().__init__(
            label="Keep Raid",
            style=discord.ButtonStyle.success,
        )
        self.raid_id = str(raid_id)

    async def callback(self, interaction: discord.Interaction):
        from views.signup.raid_control.raid_control_view import RaidControlView

        await safe_panel_edit(
            interaction,
            content="Raid cancellation aborted.",
            view=RaidControlView(self.raid_id),
        )


async def _perform_cancel(
    interaction: discord.Interaction,
    *,
    raid_id: str,
    plan_next_occurrence: bool,
):
    try:
        ok, message = await cancel_signup_raid_with_guard(
            bot=interaction.client,
            raid_id=str(raid_id),
            cancel_message="Raid has been cancelled.",
            plan_next_occurrence=plan_next_occurrence,
        )

        if not ok:
            await send_panel_error(
                interaction,
                message or "Failed to cancel raid.",
            )
            return False

        result_text = (
            "✅ Raid cancelled. The next recurring raid has been posted."
            if plan_next_occurrence
            else "✅ Raid cancelled. The recurring series has ended."
        )

        await close_panel(
            interaction,
            message=result_text,
            delete_after=RAID_CONTROL_AUTO_DELETE_SECONDS,
        )
        return True

    except Exception as e:
        print("\n[CancelRaidButton] Failed")
        print(f"Raid ID: {raid_id}")
        print(f"Exception: {type(e).__name__}: {e}")
        traceback.print_exc()

        await send_panel_error(
            interaction,
            f"⚠ Cancel raid failed: `{type(e).__name__}: {e}`",
        )
        return False


async def handle_cancel_raid(
    interaction: discord.Interaction,
    *,
    raid_id: str,
):
    data = load_signups()
    signup = find_message_signup(data, str(raid_id))

    if not signup:
        await send_panel_error(interaction, "Raid signup not found.")
        return False

    recurring = is_recurring_signup(signup)
    prompt = (
        "Cancel this raid. Do you still want to plan the next recurring raid?"
        if recurring
        else "Are you sure you want to cancel this raid?"
    )

    await safe_panel_edit(
        interaction,
        content=prompt,
        view=CancelRaidConfirmationView(str(raid_id), is_recurring=recurring),
    )
    return True
