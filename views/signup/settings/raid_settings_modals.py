import asyncio
import discord

from services.raid.raid_admin_service import (
    update_raid_title,
    update_raid_description,
    update_raid_leader,
    update_raid_time_only,
    update_raid_date_only,
)
from services.comp.comp_message_service import refresh_existing_comp_message
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)
from utils.discord_utils import delete_interaction_after


async def _refresh_signup_or_fail(
    interaction: discord.Interaction,
    raid_id: int,
) -> tuple[bool, str | None]:
    try:
        refreshed = await refresh_signup_message_by_id(interaction.channel, raid_id)
        if not refreshed:
            return False, "Raid updated, but the signup message no longer exists."
        return True, None
    except Exception as e:
        return False, f"Raid updated, but failed to refresh signup: {e}"


class EditRaidTitleModal(discord.ui.Modal, title="Edit Raid Title"):
    new_title = discord.ui.TextInput(
        label="Raid Title",
        placeholder="Enter new raid title",
        max_length=100,
    )

    def __init__(self, raid_id: int):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):
        ok = update_raid_title(self.raid_id, str(self.new_title).strip())

        if not ok:
            await interaction.response.send_message(
                "⚠ Raid signup not found.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        refreshed_ok, error_message = await _refresh_signup_or_fail(interaction, self.raid_id)
        await refresh_existing_comp_message(interaction.channel, self.raid_id)

        from views.signup.settings.raid_settings_view import RaidSettingsView

        if not refreshed_ok:
            await interaction.response.edit_message(
                content=f"⚠ {error_message}",
                view=RaidSettingsView(str(self.raid_id)),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content="Raid title updated.",
            view=RaidSettingsView(str(self.raid_id)),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class EditRaidDescriptionModal(discord.ui.Modal, title="Edit Raid Description"):
    new_description = discord.ui.TextInput(
        label="Raid Description",
        placeholder="Enter new description",
        style=discord.TextStyle.paragraph,
        max_length=300,
        required=False,
    )

    def __init__(self, raid_id: int):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):
        ok = update_raid_description(self.raid_id, str(self.new_description).strip())

        if not ok:
            await interaction.response.send_message(
                "⚠ Raid signup not found.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        refreshed_ok, error_message = await _refresh_signup_or_fail(interaction, self.raid_id)
        await refresh_existing_comp_message(interaction.channel, self.raid_id)

        from views.signup.settings.raid_settings_view import RaidSettingsView

        if not refreshed_ok:
            await interaction.response.edit_message(
                content=f"⚠ {error_message}",
                view=RaidSettingsView(str(self.raid_id)),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content="Raid description updated.",
            view=RaidSettingsView(str(self.raid_id)),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class EditRaidLeaderModal(discord.ui.Modal, title="Edit Raid Leader"):
    new_leader = discord.ui.TextInput(
        label="Raid Leader",
        placeholder="Enter new raid leader text",
        max_length=100,
    )

    def __init__(self, raid_id: int):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):
        ok = update_raid_leader(self.raid_id, str(self.new_leader).strip())

        if not ok:
            await interaction.response.send_message(
                "⚠ Raid signup not found.",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        refreshed_ok, error_message = await _refresh_signup_or_fail(interaction, self.raid_id)
        await refresh_existing_comp_message(interaction.channel, self.raid_id)

        from views.signup.settings.raid_settings_view import RaidSettingsView

        if not refreshed_ok:
            await interaction.response.edit_message(
                content=f"⚠ {error_message}",
                view=RaidSettingsView(str(self.raid_id)),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content="Raid leader updated.",
            view=RaidSettingsView(str(self.raid_id)),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class EditRaidDateModal(discord.ui.Modal, title="Edit Raid Date"):
    new_date = discord.ui.TextInput(
        label="Raid Date",
        placeholder="YYYY-MM-DD",
        max_length=10,
    )

    def __init__(self, raid_id: int):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):
        ok, updated_ts, error_message = update_raid_date_only(
            self.raid_id,
            str(self.new_date).strip(),
        )

        if not ok:
            await interaction.response.send_message(
                f"⚠ {error_message}",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        refreshed_ok, refresh_error = await _refresh_signup_or_fail(interaction, self.raid_id)
        await refresh_existing_comp_message(interaction.channel, self.raid_id)

        from views.signup.settings.raid_settings_view import RaidSettingsView

        if not refreshed_ok:
            await interaction.response.edit_message(
                content=f"⚠ {refresh_error}",
                view=RaidSettingsView(str(self.raid_id)),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"Raid date updated to <t:{updated_ts}:D>.",
            view=RaidSettingsView(str(self.raid_id)),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class EditRaidTimeModal(discord.ui.Modal, title="Edit Raid Time"):
    new_time = discord.ui.TextInput(
        label="Raid Time",
        placeholder="HH:MM",
        max_length=5,
    )

    def __init__(self, raid_id: int):
        super().__init__()
        self.raid_id = raid_id

    async def on_submit(self, interaction: discord.Interaction):
        ok, updated_ts, error_message = update_raid_time_only(
            self.raid_id,
            str(self.new_time).strip(),
        )

        if not ok:
            await interaction.response.send_message(
                f"⚠ {error_message}",
                ephemeral=True,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        refreshed_ok, refresh_error = await _refresh_signup_or_fail(interaction, self.raid_id)
        await refresh_existing_comp_message(interaction.channel, self.raid_id)
        
        from views.signup.settings.raid_settings_view import RaidSettingsView

        if not refreshed_ok:
            await interaction.response.edit_message(
                content=f"⚠ {refresh_error}",
                view=RaidSettingsView(str(self.raid_id)),
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )
            return

        await interaction.response.edit_message(
            content=f"Raid time updated to <t:{updated_ts}:t>.",
            view=RaidSettingsView(str(self.raid_id)),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )