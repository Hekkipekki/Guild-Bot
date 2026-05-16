# ================================================
# FILE: utils/panel_helpers.py
# ================================================

import asyncio
import discord

from utils.discord_utils import (
    delete_interaction_after,
    delete_message_after,
)

from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)


async def send_panel_error(
    interaction: discord.Interaction,
    message: str,
    *,
    delete_after: int = ERROR_MESSAGE_AUTO_DELETE_SECONDS,
):
    """
    Safely send an ephemeral error regardless of interaction state.
    """

    if interaction.response.is_done():
        msg = await interaction.followup.send(
            message,
            ephemeral=True,
            wait=True,
        )

        if delete_after:
            asyncio.create_task(
                delete_message_after(msg, delete_after)
            )

        return msg

    await interaction.response.send_message(
        message,
        ephemeral=True,
    )

    if delete_after:
        asyncio.create_task(
            delete_interaction_after(interaction, delete_after)
        )

    return None


async def safe_defer(interaction: discord.Interaction):
    """
    Safely defer an interaction if not already handled.
    """

    if not interaction.response.is_done():
        await interaction.response.defer()


async def safe_panel_edit(
    interaction: discord.Interaction,
    *,
    content=None,
    embed=None,
    view=None,
):
    """
    Safely edit the interaction panel regardless of response state.
    """

    if interaction.response.is_done():
        return await interaction.edit_original_response(
            content=content,
            embed=embed,
            view=view,
        )

    return await interaction.response.edit_message(
        content=content,
        embed=embed,
        view=view,
    )


async def close_panel(
    interaction: discord.Interaction,
    *,
    message: str = "Panel closed.",
    delete_after: int = 1,
):
    """
    Close and auto-delete a panel.
    """

    await safe_panel_edit(
        interaction,
        content=message,
        embed=None,
        view=None,
    )

    if delete_after:
        asyncio.create_task(
            delete_interaction_after(interaction, delete_after)
        )