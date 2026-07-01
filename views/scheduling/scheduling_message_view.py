from __future__ import annotations

import discord

from services.scheduling.scheduling_service import (
    build_absence_options,
    add_absence,
    clear_old_absences,
    refresh_scheduling_message,
)

from utils.permissions import can_manage_raid_tools
from utils.panel_helpers import send_panel_error


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

        ok = add_absence(
            interaction.guild.id,
            self.panel_id,
            user_id=interaction.user.id,
            display_name=interaction.user.display_name,
            dates=list(self.values),
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
            content="✅ Absence saved.",
            view=None,
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
            content=f"✅ {message}" if ok else f"⚠ {message}",
            view=None,
        )


class SchedulingClearOldButton(discord.ui.Button):
    def __init__(self, panel_id: str):
        super().__init__(
            label="Clear Old Dates",
            style=discord.ButtonStyle.danger,
            row=0,
        )
        self.panel_id = str(panel_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await send_panel_error(interaction, "Guild not found.")
            return

        removed = clear_old_absences(
            interaction.guild.id,
            self.panel_id,
        )

        await refresh_scheduling_message(
            interaction.client,
            interaction.guild.id,
            self.panel_id,
        )

        await interaction.response.edit_message(
            content=f"✅ Cleared {removed} old date(s).",
            view=None,
        )


class SchedulingControlView(discord.ui.View):
    def __init__(self, panel_id: str):
        super().__init__(timeout=120)

        self.add_item(SchedulingRefreshButton(panel_id))
        self.add_item(SchedulingClearOldButton(panel_id))


class SchedulingMessageView(discord.ui.View):
    def __init__(self, panel_id: str):
        super().__init__(timeout=None)
        self.panel_id = str(panel_id)

        self.add_item(AbsentButton(self.panel_id))
        self.add_item(SchedulingControlButton(self.panel_id))