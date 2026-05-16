from __future__ import annotations

import asyncio

import discord


async def delete_message_after(
    message: discord.Message,
    delay: int,
):
    """
    Safely delete a Discord message after a delay.
    """

    await asyncio.sleep(delay)

    try:
        await message.delete()
    except Exception:
        pass


async def delete_interaction_after(
    interaction: discord.Interaction,
    delay: int,
):
    """
    Safely delete the original interaction response after a delay.
    """

    await asyncio.sleep(delay)

    try:
        await interaction.delete_original_response()
    except Exception:
        pass


async def send_ephemeral_error(
    interaction: discord.Interaction,
    message: str,
    *,
    delete_after: int | None = None,
):
    """
    Legacy helper kept for backwards compatibility.
    """

    try:
        if interaction.response.is_done():
            msg = await interaction.followup.send(
                message,
                ephemeral=True,
                wait=True,
            )

            if delete_after:
                asyncio.create_task(
                    delete_message_after(
                        msg,
                        delete_after,
                    )
                )

        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )

            if delete_after:
                asyncio.create_task(
                    delete_interaction_after(
                        interaction,
                        delete_after,
                    )
                )

    except Exception:
        pass