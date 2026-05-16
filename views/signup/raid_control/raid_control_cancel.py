from __future__ import annotations

import traceback

import discord

from services.raid.raid_cancel_service import cancel_signup_raid

from utils.panel_helpers import send_panel_error, close_panel
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS


async def handle_cancel_raid(
    interaction: discord.Interaction,
    *,
    raid_id: str,
):
    try:
        ok, message = await cancel_signup_raid(
            bot=interaction.client,
            raid_id=str(raid_id),
            cancel_message="Raid has been cancelled.",
        )

        if not ok:
            await send_panel_error(
                interaction,
                message or "Failed to cancel raid.",
            )
            return False

        await close_panel(
            interaction,
            message=(
                "✅ Raid cancelled. Signup message, comp message, reminders, "
                "attendance record, and JSON entry removed."
            ),
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