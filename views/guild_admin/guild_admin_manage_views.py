import asyncio
import discord

from services.guild.guild_settings_service import (
    VALID_SIGNUP_THEMES,
    add_raid_control_user,
    remove_raid_control_user,
    add_expected_player,
    remove_expected_player,
    set_weakauras_channel_id,
    get_signup_theme,
    set_signup_theme,
    set_scheduling_channel_id,
)

from utils.discord_utils import delete_interaction_after
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS
from utils.panel_helpers import safe_panel_edit

from views.guild_admin.guild_admin_helpers import (
    build_guild_config_embed,
)


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

    await safe_panel_edit(
        interaction,
        content=content,
        embed=build_guild_config_embed(guild),
        view=GuildSetupView(),
    )

    asyncio.create_task(
        delete_interaction_after(
            interaction,
            RAID_CONTROL_AUTO_DELETE_SECONDS,
        )
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
        await _return_to_setup_overview(
            interaction,
            content=None,
        )


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


class SignupThemeSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        current_theme = get_signup_theme(guild_id)

        options = [
            discord.SelectOption(
                label=label,
                value=theme,
                description=_theme_description(theme),
                default=theme == current_theme,
            )
            for theme, label in VALID_SIGNUP_THEMES.items()
        ]

        super().__init__(
            placeholder="Select signup embed theme...",
            min_values=1,
            max_values=1,
            options=options,
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

        selected_theme = self.values[0]
        ok = set_signup_theme(guild.id, selected_theme)

        if not ok:
            await _return_to_setup_overview(
                interaction,
                content="⚠ Invalid signup theme selected.",
            )
            return

        label = VALID_SIGNUP_THEMES.get(selected_theme, selected_theme)

        await _return_to_setup_overview(
            interaction,
            content=f"✅ Signup theme set to **{label}**.",
        )


def _theme_description(theme: str) -> str:
    if theme == "classic":
        return "Current stable signup layout."
    if theme == "compact":
        return "Future compact Raid-Helper-inspired layout."
    if theme == "split_by_class":
        return "Future class-grouped signup layout."
    return "Signup layout theme."


class SignupThemeManageView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)

        self.add_item(
            SignupThemeSelect(guild_id)
        )

        self.add_item(
            BackToSetupButton()
        )


class RaidAdminManageView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)

        self.add_item(
            RaidAdminUserSelect(mode)
        )

        self.add_item(
            BackToSetupButton()
        )


class RaidTeamManageView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)

        self.add_item(
            RaidTeamUserSelect(mode)
        )

        self.add_item(
            BackToSetupButton()
        )


class RaidAdminManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(
        label="Add Leader",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def add_admin(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await safe_panel_edit(
            interaction,
            content="Select users to add as raid admins / leaders.",
            embed=None,
            view=RaidAdminManageView("add"),
        )

    @discord.ui.button(
        label="Remove Leader",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def remove_admin(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await safe_panel_edit(
            interaction,
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
    async def back(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await _return_to_setup_overview(
            interaction,
            content=None,
        )


class RaidTeamManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(
        label="Add Raid Member",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def add_team(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await safe_panel_edit(
            interaction,
            content="Select users to add to the raid team.",
            embed=None,
            view=RaidTeamManageView("add"),
        )

    @discord.ui.button(
        label="Remove Raid Member",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def remove_team(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await safe_panel_edit(
            interaction,
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
    async def back(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await _return_to_setup_overview(
            interaction,
            content=None,
        )


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

        set_weakauras_channel_id(
            guild.id,
            channel.id,
        )

        from services.guild.weakauras_panel_service import (
            ensure_weakauras_panel_for_guild,
        )

        ok, message = await ensure_weakauras_panel_for_guild(
            interaction.client,
            guild,
        )

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

        self.add_item(
            WeakAurasChannelSelect()
        )

        self.add_item(
            BackToSetupButton()
        )

class SchedulingChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select the Scheduling channel...",
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

        set_scheduling_channel_id(
            guild.id,
            channel.id,
        )

        from services.scheduling.scheduling_panel_service import (
            ensure_scheduling_panel_for_guild,
        )

        ok, message = await ensure_scheduling_panel_for_guild(
            interaction.client,
            guild,
        )

        status_line = f"✅ Scheduling channel set to {channel.mention}."

        if message:
            status_line += f"\n{message}"

        await _return_to_setup_overview(
            interaction,
            content=status_line,
        )


class SchedulingChannelManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

        self.add_item(
            SchedulingChannelSelect()
        )

        self.add_item(
            BackToSetupButton()
        )