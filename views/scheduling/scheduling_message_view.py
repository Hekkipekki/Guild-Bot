from __future__ import annotations

import discord

from services.scheduling.scheduling_absence_service import remove_user_absences
from services.scheduling.scheduling_service import (
    build_absence_options,
    add_absence,
    refresh_scheduling_message,
)

from utils.permissions import can_manage_raid_tools
from utils.panel_helpers import send_panel_error


class SchedulingReasonModal(discord.ui.Modal, title="Absence reason"):
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Vacation / Work / Family / Other",
        required=True,
        max_length=50,
    )

    def __init__(
        self,
        panel_id: str,
        *,
        selected_dates: list[str],
    ):
        super().__init__()
        self.panel_id = str(panel_id)
        self.selected_dates = selected_dates

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await send_panel_error(interaction, "Guild not found.")
            return

        ok = add_absence(
            interaction.guild.id,
            self.panel_id,
            user_id=interaction.user.id,
            display_name=interaction.user.display_name,
            dates=self.selected_dates,
            reason=str(self.reason.value),
        )

        if not ok:
            await send_panel_error(interaction, "Could not save absence.")
            return

        await refresh_scheduling_message(
            interaction.client,
            interaction.guild.id,
            self.panel_id,
        )

        await interaction.response.edit_message(
            content="Absence saved.",
            view=None,
        )


class AbsenceDateSelect(discord.ui.Select):
    def __init__(
        self,
        panel_id: str,
        *,
        guild_id: int | str,
        user_id: int | str,
    ):
        options = build_absence_options(
            guild_id=guild_id,
            panel_id=panel_id,
            user_id=user_id,
        )

        super().__init__(
            placeholder="Select raid days you will miss...",
            min_values=1,
            max_values=len(options),
            options=options,
            row=0,
        )

        self.panel_id = str(panel_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await send_panel_error(interaction, "Guild not found.")
            return

        await interaction.response.send_modal(
            SchedulingReasonModal(
                self.panel_id,
                selected_dates=list(self.values),
            )
        )


class ConfirmRemoveAllAbsencesView(discord.ui.View):
    def __init__(
        self,
        panel_id: str,
        *,
        guild_id: int | str,
        owner_id: int | str,
    ):
        super().__init__(timeout=120)
        self.panel_id = str(panel_id)
        self.guild_id = int(guild_id)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this panel can use these controls.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Confirm removal", style=discord.ButtonStyle.danger)
    async def confirm_removal(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        removed = remove_user_absences(
            self.guild_id,
            self.panel_id,
            user_id=self.owner_id,
        )

        await refresh_scheduling_message(
            interaction.client,
            self.guild_id,
            self.panel_id,
        )

        text = (
            f"Removed {removed} future absence sign(s)."
            if removed
            else "You had no future absence signs to remove."
        )
        await interaction.response.edit_message(content=text, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Select the raid days you will miss.",
            view=AbsenceView(
                self.panel_id,
                guild_id=self.guild_id,
                user_id=self.owner_id,
            ),
        )


class RemoveAllAbsencesButton(discord.ui.Button):
    def __init__(
        self,
        panel_id: str,
        *,
        guild_id: int | str,
        user_id: int | str,
    ):
        super().__init__(
            label="Remove all absences",
            style=discord.ButtonStyle.danger,
            row=1,
        )
        self.panel_id = str(panel_id)
        self.guild_id = int(guild_id)
        self.user_id = int(user_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Remove all of your future absence signs?",
            view=ConfirmRemoveAllAbsencesView(
                self.panel_id,
                guild_id=self.guild_id,
                owner_id=self.user_id,
            ),
        )


class AbsenceView(discord.ui.View):
    def __init__(
        self,
        panel_id: str,
        *,
        guild_id: int | str,
        user_id: int | str,
    ):
        super().__init__(timeout=120)

        self.add_item(
            AbsenceDateSelect(
                panel_id,
                guild_id=guild_id,
                user_id=user_id,
            )
        )
        self.add_item(
            RemoveAllAbsencesButton(
                panel_id,
                guild_id=guild_id,
                user_id=user_id,
            )
        )


class AbsentButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Absent",
            style=discord.ButtonStyle.secondary,
            custom_id=f"scheduling_absent:{panel_id}",
        )
        self.panel_id = str(panel_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await send_panel_error(interaction, "Guild not found.")
            return

        await interaction.response.send_message(
            "Select the raid days you will miss.",
            view=AbsenceView(
                self.panel_id,
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
            ),
            ephemeral=True,
        )


class SchedulingControlButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Control",
            style=discord.ButtonStyle.secondary,
            custom_id=f"scheduling_control:{panel_id}",
        )
        self.panel_id = str(panel_id)

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_raid_tools(interaction):
            await send_panel_error(
                interaction,
                "You do not have access to scheduling control.",
            )
            return

        await interaction.response.send_message(
            "Scheduling control panel.",
            view=SchedulingControlView(self.panel_id),
            ephemeral=True,
        )


class SchedulingRefreshButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Refresh",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.panel_id = str(panel_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await send_panel_error(interaction, "Guild not found.")
            return

        ok, message = await refresh_scheduling_message(
            interaction.client,
            interaction.guild.id,
            self.panel_id,
        )

        await interaction.response.edit_message(
            content=f"{message}" if ok else f"Warning: {message}",
            view=None,
        )


class SchedulingControlView(discord.ui.View):
    def __init__(self, panel_id: str):
        super().__init__(timeout=120)

        self.add_item(SchedulingRefreshButton(panel_id))


class SchedulingMessageView(discord.ui.View):
    def __init__(self, panel_id: str):
        super().__init__(timeout=None)
        self.panel_id = str(panel_id)

        self.add_item(AbsentButton(self.panel_id))
        self.add_item(SchedulingControlButton(self.panel_id))
