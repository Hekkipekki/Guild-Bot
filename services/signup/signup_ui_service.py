import asyncio
import discord

from services.signup.signup_refresh_service import (
    refresh_signup_message,
    refresh_signup_message_by_id,
)
from views.signup_options.embeds import build_signup_options_embed
from views.signup_options.helpers import get_signup_entry
from utils.discord_utils import delete_interaction_after, delete_message_after
from utils.ui_timing import (
    SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)

# Tracks the latest signup-options ephemeral message for each (raid_id, user_id)
# so a new main-signup interaction can replace the old ephemeral instead of stacking.
_ACTIVE_SIGNUP_OPTION_MESSAGES: dict[tuple[int, int], discord.WebhookMessage] = {}


def _panel_key(raid_id: int, user_id: int) -> tuple[int, int]:
    return (int(raid_id), int(user_id))


def _forget_panel(raid_id: int, user_id: int) -> None:
    _ACTIVE_SIGNUP_OPTION_MESSAGES.pop(_panel_key(raid_id, user_id), None)


async def _delete_tracked_panel(
    raid_id: int,
    user_id: int,
) -> None:
    key = _panel_key(raid_id, user_id)
    old_msg = _ACTIVE_SIGNUP_OPTION_MESSAGES.pop(key, None)

    if old_msg is None:
        return

    try:
        await old_msg.delete()
    except Exception:
        pass


async def _auto_delete_tracked_panel(
    raid_id: int,
    user_id: int,
    message: discord.WebhookMessage,
    seconds: int,
) -> None:
    try:
        await asyncio.sleep(seconds)
        await message.delete()
    except Exception:
        pass
    finally:
        key = _panel_key(raid_id, user_id)
        if _ACTIVE_SIGNUP_OPTION_MESSAGES.get(key) is message:
            _ACTIVE_SIGNUP_OPTION_MESSAGES.pop(key, None)


async def _send_error_response(
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


async def refresh_main_signup_from_interaction(
    interaction: discord.Interaction,
    raid_id: int,
) -> bool:
    try:
        ok = await refresh_signup_message(interaction, raid_id)
        if not ok:
            await _send_error_response(
                interaction,
                "⚠ Raid signup no longer exists.",
            )
            return False
        return True

    except discord.NotFound:
        await _send_error_response(
            interaction,
            "⚠ Could not find the signup message.",
        )
        return False

    except Exception as e:
        await _send_error_response(
            interaction,
            f"⚠ Could not refresh signup message: {e}",
        )
        return False


async def refresh_main_signup_from_channel(
    interaction: discord.Interaction,
    raid_id: int,
) -> bool:
    try:
        ok = await refresh_signup_message_by_id(interaction.channel, raid_id)
        if not ok:
            await _send_error_response(
                interaction,
                "⚠ Raid signup no longer exists.",
            )
            return False
        return True

    except discord.NotFound:
        await _send_error_response(
            interaction,
            "⚠ Could not find the signup message.",
        )
        return False

    except Exception as e:
        await _send_error_response(
            interaction,
            f"⚠ Could not refresh signup message: {e}",
        )
        return False


async def show_signup_options_panel(
    interaction: discord.Interaction,
    raid_id: int,
    user_id: int,
    *,
    delete_after: int = SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
) -> bool:
    from views.signup_options.options_view import SignupOptionsView

    entry = get_signup_entry(raid_id, str(user_id))
    if not entry:
        await _send_error_response(
            interaction,
            "⚠ Could not load signup options.",
        )
        return False

    guild = interaction.guild
    if guild is None:
        await _send_error_response(
            interaction,
            "⚠ This action can only be used inside a server.",
        )
        return False

    embed = build_signup_options_embed(entry)
    view = SignupOptionsView(guild.id, raid_id, user_id)

    # Always remove the previous tracked signup-options panel first,
    # so the user only sees one active ephemeral panel at a time.
    await _delete_tracked_panel(raid_id, user_id)

    try:
        if interaction.response.is_done():
            msg = await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True,
                wait=True,
            )
        else:
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True,
            )
            msg = await interaction.original_response()

        _ACTIVE_SIGNUP_OPTION_MESSAGES[_panel_key(raid_id, user_id)] = msg
        asyncio.create_task(
            _auto_delete_tracked_panel(raid_id, user_id, msg, delete_after)
        )
        return True

    except Exception as e:
        await _send_error_response(
            interaction,
            f"⚠ Could not open signup options: {e}",
        )
        return False


async def replace_signup_options_panel(
    interaction: discord.Interaction,
    raid_id: int,
    user_id: int,
    *,
    delete_after: int = SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
) -> bool:
    """
    Use this only when the interaction already comes from the signup-options
    ephemeral panel itself and should replace that exact panel.
    """
    from views.signup_options.options_view import SignupOptionsView

    entry = get_signup_entry(raid_id, str(user_id))
    if not entry:
        await _send_error_response(
            interaction,
            "⚠ Could not load signup options.",
        )
        return False

    guild = interaction.guild
    if guild is None:
        await _send_error_response(
            interaction,
            "⚠ This action can only be used inside a server.",
        )
        return False

    embed = build_signup_options_embed(entry)
    view = SignupOptionsView(guild.id, raid_id, user_id)

    try:
        if interaction.response.is_done():
            await interaction.edit_original_response(
                content=None,
                embed=embed,
                view=view,
            )
            msg = await interaction.original_response()
        else:
            await interaction.response.edit_message(
                content=None,
                embed=embed,
                view=view,
            )
            msg = await interaction.original_response()

        _ACTIVE_SIGNUP_OPTION_MESSAGES[_panel_key(raid_id, user_id)] = msg
        asyncio.create_task(
            _auto_delete_tracked_panel(raid_id, user_id, msg, delete_after)
        )
        return True

    except Exception as e:
        await _send_error_response(
            interaction,
            f"⚠ Could not replace signup options: {e}",
        )
        return False


async def refresh_and_show_signup_options_from_interaction(
    interaction: discord.Interaction,
    raid_id: int,
    user_id: int,
    *,
    delete_after: int = SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
) -> bool:
    refreshed = await refresh_main_signup_from_interaction(interaction, raid_id)
    if not refreshed:
        return False

    return await show_signup_options_panel(
        interaction,
        raid_id,
        user_id,
        delete_after=delete_after,
    )


async def refresh_and_show_signup_options_from_channel(
    interaction: discord.Interaction,
    raid_id: int,
    user_id: int,
    *,
    delete_after: int = SIGNUP_OPTIONS_AUTO_DELETE_SECONDS,
) -> bool:
    refreshed = await refresh_main_signup_from_channel(interaction, raid_id)
    if not refreshed:
        return False

    return await show_signup_options_panel(
        interaction,
        raid_id,
        user_id,
        delete_after=delete_after,
    )