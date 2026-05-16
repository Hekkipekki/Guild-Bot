from __future__ import annotations

import traceback

import discord

from services.comp.comp_message_service import post_comp_message
from services.comp.roster_comp_service import analyze_roster_comp

from utils.panel_helpers import send_panel_error, close_panel
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS


async def handle_post_comp(
    interaction: discord.Interaction,
    *,
    raid_id: str,
):
    try:
        state, payload = analyze_roster_comp(raid_id)

        if state == "error" or payload is None:
            await send_panel_error(
                interaction,
                "Could not build comp. The raid may no longer exist.",
            )
            return False

        if state == "ambiguous":
            await send_panel_error(
                interaction,
                "Two valid comps were found. The compact refactor flow does not support comp choice yet.",
            )
            return False

        comp_data = payload.get("comp_data")

        if not comp_data:
            await send_panel_error(
                interaction,
                "Could not build comp data.",
            )
            return False

        if interaction.channel is None:
            await send_panel_error(
                interaction,
                "Could not find this channel.",
            )
            return False

        ok, message = await post_comp_message(
            interaction.channel,
            comp_data,
        )

        if not ok:
            await send_panel_error(
                interaction,
                message or "Failed to post comp message.",
            )
            return False

        await close_panel(
            interaction,
            message=message or "Comp message posted.",
            delete_after=RAID_CONTROL_AUTO_DELETE_SECONDS,
        )

        return True

    except Exception as e:
        print("\n[PostCompButton] Failed")
        print(f"Raid ID: {raid_id}")
        print(f"Exception: {type(e).__name__}: {e}")
        traceback.print_exc()

        await send_panel_error(
            interaction,
            f"⚠ Post comp failed: `{type(e).__name__}: {e}`",
        )

        return False