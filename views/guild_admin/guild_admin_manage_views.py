import asyncio
import discord

from services.guild.guild_settings_service import (
    add_raid_control_user,
    remove_raid_control_user,
    add_expected_player,
    remove_expected_player,
    set_weakauras_channel_id,
)
from utils.discord_utils import delete_interaction_after
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS
from views.guild_admin.guild_admin_helpers import build_guild_config_embed


async def _return_to_setup_overview(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "⚠ This command can only be used in a server.",
            ephemeral=True,
        )
        return

    from views.guild_admin.guild_admin_view import GuildSetupView

    await interaction.response.edit_message(
        content=content,
        embed=build_guild_config_embed(guild),
        view=GuildSetupView(),
    )
    asyncio.create_task(
        delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
    )


class BackToSetupButton(discord.ui.Button):
    def __init__(self, row: int = 1):
        super().__init__(
            label="Back",
            emoji=parse_button_emoji("leave"),
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await _return_to_setup_overview(interaction, content=None)


class RaidAdminUserSelect(discord.ui.UserSelect):
    def __init__(self, mode: str):
        self.mode = mode
        placeholder = (
            "Select users to add as raid admins / leaders..."
            if mode == "add"
            else "Select users to remove from raid admins / leaders..."
        )

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=25,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        changed = 0
        for member in self.values:
            if self.mode == "add":
                if add_raid_control_user(guild.id, member.id):
                    changed += 1
            else:
                if remove_raid_control_user(guild.id, member.id):
                    changed += 1

        await _return_to_setup_overview(
            interaction,
            content=f"✅ Updated raid admins / leaders. Changed {changed} user(s).",
        )


class RaidTeamUserSelect(discord.ui.UserSelect):
    def __init__(self, mode: str):
        self.mode = mode
        placeholder = (
            "Select users to add to the raid team..."
            if mode == "add"
            else "Select users to remove from the raid team..."
        )

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=25,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        changed = 0
        for member in self.values:
            if self.mode == "add":
                if add_expected_player(guild.id, member.id):
                    changed += 1
            else:
                if remove_expected_player(guild.id, member.id):
                    changed += 1

        await _return_to_setup_overview(
            interaction,
            content=f"✅ Updated raid team. Changed {changed} user(s).",
        )


class RaidAdminManageView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)
        self.add_item(RaidAdminUserSelect(mode))
        self.add_item(BackToSetupButton())


class RaidTeamManageView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)
        self.add_item(RaidTeamUserSelect(mode))
        self.add_item(BackToSetupButton())


class RaidAdminManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Add Leader", style=discord.ButtonStyle.secondary, row=0)
    async def add_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Select users to add as raid admins / leaders.",
            embed=None,
            view=RaidAdminManageView("add"),
        )

    @discord.ui.button(label="Remove Leader", style=discord.ButtonStyle.secondary, row=0)
    async def remove_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Select users to remove from raid admins / leaders.",
            embed=None,
            view=RaidAdminManageView("remove"),
        )

    @discord.ui.button(
        label="Back",
        emoji=parse_button_emoji("leave"),
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _return_to_setup_overview(interaction, content=None)


class RaidTeamManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Add Raid Member", style=discord.ButtonStyle.secondary, row=0)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Select users to add to the raid team.",
            embed=None,
            view=RaidTeamManageView("add"),
        )

    @discord.ui.button(label="Remove Raid Member", style=discord.ButtonStyle.secondary, row=0)
    async def remove_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Select users to remove from the raid team.",
            embed=None,
            view=RaidTeamManageView("remove"),
        )

    @discord.ui.button(
        label="Back",
        emoji=parse_button_emoji("leave"),
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _return_to_setup_overview(interaction, content=None)


class WeakAurasChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select the WeakAuras channel...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        channel = self.values[0]
        set_weakauras_channel_id(guild.id, channel.id)

        from services.guild.weakauras_panel_service import ensure_weakauras_panel_for_guild
        ok, message = await ensure_weakauras_panel_for_guild(interaction.client, guild)

        status_line = f"✅ WeakAuras channel set to {channel.mention}."
        if message:
            status_line += f"\n{message}"

        await _return_to_setup_overview(
            interaction,
            content=status_line,
        )


class WeakAurasChannelManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(WeakAurasChannelSelect())
        self.add_item(BackToSetupButton())