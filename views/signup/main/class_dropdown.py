from __future__ import annotations

import asyncio

import discord
import config

from services.signup.signup_ui_service import (
    refresh_and_show_signup_options_from_interaction,
)

from services.signup.signup_service import (
    set_user_spec,
)

from utils.emoji_helpers import (
    parse_class_emoji,
)

from utils.ui_timing import (
    CHARACTER_MENU_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
)

from utils.discord_utils import (
    delete_interaction_after,
)

from utils.panel_helpers import (
    send_panel_error,
)


class ClassDropdown(discord.ui.Select):
    def __init__(self, raid_id: str):
        self.raid_id = raid_id

        options = [
            discord.SelectOption(
                label=cls,
                value=cls,
                emoji=parse_class_emoji(cls),
            )
            for cls in config.CLASSES
        ]

        super().__init__(
            placeholder="Select your class...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"signup:classdropdown:{raid_id}",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_class = self.values[0]

            from services.character.character_service import (
                get_user_characters,
            )

            from views.signup.character.character_add_view import (
                AddCharacterSpecView,
            )

            guild = interaction.guild

            if guild is None:
                await send_panel_error(
                    interaction,
                    "⚠ This action can only be used inside a server.",
                    delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                )
                return

            characters = get_user_characters(
                guild.id,
                interaction.user.id,
            )

            saved_char = None

            for char in characters:
                if char.get("class") == selected_class:
                    saved_char = char
                    break

            # ------------------------------------------------
            # Auto-sign existing character
            # ------------------------------------------------

            if saved_char:
                ok = set_user_spec(
                    raid_id=int(self.raid_id),
                    user_id=str(interaction.user.id),
                    selected_class=saved_char["class"],
                    selected_spec=saved_char["spec"],
                    role=saved_char["role"],
                    character_name=saved_char["name"],
                    auto_sign=True,
                    display_name=interaction.user.display_name,
                )

                if not ok:
                    await send_panel_error(
                        interaction,
                        "⚠ Raid signup no longer exists.",
                        delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                    )
                    return

                await interaction.response.defer()

                await refresh_and_show_signup_options_from_interaction(
                    interaction,
                    int(self.raid_id),
                    interaction.user.id,
                    delete_after=CHARACTER_MENU_AUTO_DELETE_SECONDS,
                )

                return

            # ------------------------------------------------
            # New character flow
            # ------------------------------------------------

            await interaction.response.send_message(
                f"Select your specialization for **{selected_class}**:",
                ephemeral=True,
                view=AddCharacterSpecView(
                    guild_id=guild.id,
                    user_id=interaction.user.id,
                    parent_message_id=int(self.raid_id),
                    selected_class=selected_class,
                    filter_class=selected_class,
                ),
            )

            asyncio.create_task(
                delete_interaction_after(
                    interaction,
                    CHARACTER_MENU_AUTO_DELETE_SECONDS,
                )
            )

        except Exception as e:
            await send_panel_error(
                interaction,
                f"⚠ Class select failed: `{type(e).__name__}: {e}`",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
