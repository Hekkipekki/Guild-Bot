import asyncio
import discord

from utils.discord_utils import delete_interaction_after
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS
from views.guild_admin.guild_admin_manage_views import (
    RaidAdminManageChoiceView,
    RaidTeamManageChoiceView,
    WeakAurasChannelManageView,
    SignupThemeManageView,
)
from utils.panel_helpers import safe_panel_edit


class RaidAdminsSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Raid Admin & Leader",
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Manage raid admins / leaders.",
            embed=None,
            view=RaidAdminManageChoiceView(),
        )


class RaidTeamSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Raid Team",
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Manage raid team.",
            embed=None,
            view=RaidTeamManageChoiceView(),
        )


class SignupThemeSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Signup Theme",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await safe_panel_edit(
            interaction,
            content="Select the signup embed layout theme for new raids.",
            embed=None,
            view=SignupThemeManageView(guild.id),
        )


class WeakAurasSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="WeakAuras Channel",
            style=discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Select the channel to use for WeakAuras posts.",
            embed=None,
            view=WeakAurasChannelManageView(),
        )


class CloseSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            emoji=parse_button_emoji("cancel_raid"),
            style=discord.ButtonStyle.secondary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await safe_panel_edit(
            interaction,
            content="Setup closed.",
            embed=None,
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class GuildSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        self.add_item(RaidAdminsSetupButton())
        self.add_item(RaidTeamSetupButton())
        self.add_item(SignupThemeSetupButton())
        self.add_item(WeakAurasSetupButton())
        self.add_item(CloseSetupButton())