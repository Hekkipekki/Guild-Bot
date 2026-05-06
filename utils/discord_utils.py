import asyncio
import discord


async def delete_interaction_after(
    interaction: discord.Interaction,
    seconds: int,
):
    try:
        await asyncio.sleep(seconds)
        await interaction.delete_original_response()
    except Exception:
        pass


async def delete_message_after(
    message,
    seconds: int,
):
    try:
        await asyncio.sleep(seconds)
        await message.delete()
    except Exception:
        pass


async def send_ephemeral_message(
    interaction: discord.Interaction,
    message: str,
    *,
    delete_after: int | None = None,
):
    if interaction.response.is_done():
        msg = await interaction.followup.send(
            message,
            ephemeral=True,
            wait=True,
        )

        if delete_after:
            asyncio.create_task(delete_message_after(msg, delete_after))
        return msg

    await interaction.response.send_message(
        message,
        ephemeral=True,
    )

    if delete_after:
        asyncio.create_task(delete_interaction_after(interaction, delete_after))

    return None


async def send_ephemeral_error(
    interaction: discord.Interaction,
    message: str,
    delete_after: int | None = None,
):
    return await send_ephemeral_message(
        interaction,
        message,
        delete_after=delete_after,
    )


async def send_ephemeral_success(
    interaction: discord.Interaction,
    message: str,
    delete_after: int | None = None,
):
    return await send_ephemeral_message(
        interaction,
        message,
        delete_after=delete_after,
    )