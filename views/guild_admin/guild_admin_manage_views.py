import asyncio
import discord

from services.guild.guild_settings_service import (
    VALID_SIGNUP_THEMES,
    add_raid_control_user,
    remove_raid_control_user,
    add_expected_player,
    remove_expected_player,
    get_hidden_weakaura_items,
    get_raid_weekdays,
    set_hidden_weakaura_items,
    set_raid_weekdays,
    set_weakauras_channel_id,
    get_signup_theme,
    set_signup_theme,
    set_scheduling_channel_id,
)

from utils.discord_utils import delete_interaction_after
from utils.emoji_helpers import parse_button_emoji
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS
from utils.panel_helpers import safe_panel_edit
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

    await safe_panel_edit(
        interaction,
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
        await _return_to_setup_overview(interaction)


class PendingUserSelect(discord.ui.UserSelect):
    def __init__(self, *, target: str, mode: str):
        self.target = target
        self.mode = mode
        noun = "raid admins / leaders" if target == "admins" else "raid team members"
        action = "add" if mode == "add" else "remove"
        super().__init__(
            placeholder=f"Select users to {action} as {noun}...",
            min_values=1,
            max_values=25,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, ConfirmUserSelectionView):
            return

        view.selected_user_ids = [member.id for member in self.values]
        mentions = ", ".join(member.mention for member in self.values)
        await interaction.response.edit_message(
            content=(
                f"Selected: {mentions}\n\n"
                "Click **Confirm** to save these changes, or **Back** to cancel."
            ),
            view=view,
        )


class ConfirmUserSelectionButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Confirm",
            style=discord.ButtonStyle.success,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        view = self.view
        if guild is None or not isinstance(view, ConfirmUserSelectionView):
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        if not view.selected_user_ids:
            await interaction.response.send_message(
                "Select at least one user before confirming.", ephemeral=True
            )
            return

        changed = 0
        for user_id in view.selected_user_ids:
            if view.target == "admins":
                changed += int(
                    add_raid_control_user(guild.id, user_id)
                    if view.mode == "add"
                    else remove_raid_control_user(guild.id, user_id)
                )
            else:
                changed += int(
                    add_expected_player(guild.id, user_id)
                    if view.mode == "add"
                    else remove_expected_player(guild.id, user_id)
                )

        label = "raid admins / leaders" if view.target == "admins" else "raid team"
        await _return_to_setup_overview(
            interaction,
            content=f"✅ Updated {label}. Changed {changed} user(s).",
        )


class ConfirmUserSelectionView(discord.ui.View):
    def __init__(self, *, target: str, mode: str):
        super().__init__(timeout=120)
        self.target = target
        self.mode = mode
        self.selected_user_ids: list[int] = []
        self.add_item(PendingUserSelect(target=target, mode=mode))
        self.add_item(ConfirmUserSelectionButton())
        self.add_item(BackToSetupButton(row=1))


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
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        selected_theme = self.values[0]
        if not set_signup_theme(guild.id, selected_theme):
            await _return_to_setup_overview(
                interaction, content="⚠ Invalid signup theme selected."
            )
            return

        label = VALID_SIGNUP_THEMES.get(selected_theme, selected_theme)
        await _return_to_setup_overview(
            interaction, content=f"✅ Signup theme set to **{label}**."
        )


def _theme_description(theme: str) -> str:
    descriptions = {
        "classic": "Current stable signup layout.",
        "compact": "Compact Raid-Helper-inspired layout.",
        "split_by_class": "Class-grouped signup layout.",
    }
    return descriptions.get(theme, "Signup layout theme.")


class SignupThemeManageView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.add_item(SignupThemeSelect(guild_id))
        self.add_item(BackToSetupButton())


class RaidAdminManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Add Leader", style=discord.ButtonStyle.secondary, row=0)
    async def add_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_panel_edit(
            interaction,
            content="Select users, then click Confirm.",
            embed=None,
            view=ConfirmUserSelectionView(target="admins", mode="add"),
        )

    @discord.ui.button(label="Remove Leader", style=discord.ButtonStyle.secondary, row=0)
    async def remove_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_panel_edit(
            interaction,
            content="Select users, then click Confirm.",
            embed=None,
            view=ConfirmUserSelectionView(target="admins", mode="remove"),
        )

    @discord.ui.button(
        label="Back",
        emoji=parse_button_emoji("leave"),
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _return_to_setup_overview(interaction)


class RaidTeamManageChoiceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Add Raid Member", style=discord.ButtonStyle.secondary, row=0)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_panel_edit(
            interaction,
            content="Select users, then click Confirm.",
            embed=None,
            view=ConfirmUserSelectionView(target="team", mode="add"),
        )

    @discord.ui.button(label="Remove Raid Member", style=discord.ButtonStyle.secondary, row=0)
    async def remove_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await safe_panel_edit(
            interaction,
            content="Select users, then click Confirm.",
            embed=None,
            view=ConfirmUserSelectionView(target="team", mode="remove"),
        )

    @discord.ui.button(
        label="Back",
        emoji=parse_button_emoji("leave"),
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _return_to_setup_overview(interaction)


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
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        channel = self.values[0]
        set_weakauras_channel_id(guild.id, channel.id)
        view = WeakAuraItemsManageView(guild.id)
        await safe_panel_edit(
            interaction,
            content=f"WeakAuras channel: {channel.mention}",
            embed=view.build_embed(),
            view=view,
        )


class WeakAuraToggleButton(discord.ui.Button):
    def __init__(self, *, index: int, item_key: str, hidden: bool):
        super().__init__(
            label=str(index),
            style=discord.ButtonStyle.danger if hidden else discord.ButtonStyle.secondary,
            row=(index - 1) // 5,
        )
        self.item_key = item_key

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, WeakAuraItemsManageView):
            return

        if self.item_key in view.hidden_items:
            view.hidden_items.remove(self.item_key)
        else:
            view.hidden_items.add(self.item_key)

        view.rebuild_buttons()
        await interaction.response.edit_message(
            content=interaction.message.content,
            embed=view.build_embed(),
            view=view,
        )


class WeakAuraSaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Save", style=discord.ButtonStyle.success, row=4)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        view = self.view
        if guild is None or not isinstance(view, WeakAuraItemsManageView):
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        set_hidden_weakaura_items(guild.id, sorted(view.hidden_items))
        from services.guild.weakauras_panel_service import ensure_weakauras_panel_for_guild

        _, message = await ensure_weakauras_panel_for_guild(interaction.client, guild)
        await _return_to_setup_overview(
            interaction,
            content=f"✅ WeakAuras panel preferences saved.\n{message}",
        )


class WeakAuraShowAllButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Show All", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, WeakAuraItemsManageView):
            return
        view.hidden_items.clear()
        view.rebuild_buttons()
        await interaction.response.edit_message(
            content=interaction.message.content,
            embed=view.build_embed(),
            view=view,
        )


class WeakAuraBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Back",
            emoji=parse_button_emoji("leave"),
            style=discord.ButtonStyle.secondary,
            row=4,
        )

    async def callback(self, interaction: discord.Interaction):
        await _return_to_setup_overview(interaction)


class WeakAuraItemsManageView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.hidden_items = set(get_hidden_weakaura_items(guild_id))
        self.rebuild_buttons()

    def _items(self) -> list[tuple[str, str, str]]:
        from services.guild.weakauras_panel_service import WA_ITEM_LABELS, WA_SECTIONS

        items: list[tuple[str, str, str]] = []
        for section in WA_SECTIONS:
            category = section["heading"].lstrip("# ")
            for key, _ in section["items"]:
                items.append((category, key, WA_ITEM_LABELS[key]))
        return items

    def rebuild_buttons(self) -> None:
        self.clear_items()
        for index, (_, key, _) in enumerate(self._items(), start=1):
            self.add_item(
                WeakAuraToggleButton(
                    index=index,
                    item_key=key,
                    hidden=key in self.hidden_items,
                )
            )
        self.add_item(WeakAuraSaveButton())
        self.add_item(WeakAuraShowAllButton())
        self.add_item(WeakAuraBackButton())

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="WeakAura & Addon Visibility",
            description=(
                "Click a numbered button to toggle an entry.\n"
                "👁️ = shown  •  ❌ = hidden\n"
                "Red numbered buttons are currently hidden. Changes are applied only after **Save**."
            ),
            color=discord.Color.purple(),
        )

        grouped: dict[str, list[str]] = {}
        for index, (category, key, label) in enumerate(self._items(), start=1):
            icon = "❌" if key in self.hidden_items else "👁️"
            grouped.setdefault(category, []).append(f"`{index:02}` {icon} {label}")

        for category, lines in grouped.items():
            embed.add_field(
                name=category,
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=f"Hidden: {len(self.hidden_items)} / {len(self._items())}")
        return embed


class WeakAurasChannelManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(WeakAurasChannelSelect())
        self.add_item(BackToSetupButton())


WEEKDAY_OPTIONS = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


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
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        channel = self.values[0]
        set_scheduling_channel_id(guild.id, channel.id)
        await safe_panel_edit(
            interaction,
            content=(
                f"Scheduling channel: {channel.mention}\n"
                "Select the exact weekdays used for raids."
            ),
            embed=None,
            view=RaidWeekdaysManageView(guild.id),
        )


class RaidWeekdaysSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        current = set(get_raid_weekdays(guild_id))
        options = [
            discord.SelectOption(label=label, value=str(day), default=day in current)
            for day, label in WEEKDAY_OPTIONS
        ]
        super().__init__(
            placeholder="Select all raid weekdays...",
            min_values=1,
            max_values=7,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, RaidWeekdaysManageView):
            return
        view.selected_weekdays = [int(value) for value in self.values]
        labels = [label for day, label in WEEKDAY_OPTIONS if day in view.selected_weekdays]
        await interaction.response.edit_message(
            content=(
                f"Selected raid days: **{', '.join(labels)}**\n\n"
                "Click **Confirm** to save."
            ),
            view=view,
        )


class RaidWeekdaysConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm", style=discord.ButtonStyle.success, row=1)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        view = self.view
        if guild is None or not isinstance(view, RaidWeekdaysManageView):
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        if not set_raid_weekdays(guild.id, view.selected_weekdays):
            await interaction.response.send_message(
                "Select at least one raid day.", ephemeral=True
            )
            return

        from services.scheduling.scheduling_panel_service import ensure_scheduling_panel_for_guild

        _, message = await ensure_scheduling_panel_for_guild(interaction.client, guild)
        labels = [label for day, label in WEEKDAY_OPTIONS if day in view.selected_weekdays]
        await _return_to_setup_overview(
            interaction,
            content=f"✅ Raid days set to **{', '.join(labels)}**.\n{message}",
        )


class RaidWeekdaysManageView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.selected_weekdays = get_raid_weekdays(guild_id)
        self.add_item(RaidWeekdaysSelect(guild_id))
        self.add_item(RaidWeekdaysConfirmButton())
        self.add_item(BackToSetupButton(row=1))


class SchedulingChannelManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SchedulingChannelSelect())
        self.add_item(BackToSetupButton())
