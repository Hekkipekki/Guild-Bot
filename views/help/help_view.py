import asyncio

import discord

from utils.discord_utils import delete_interaction_after
from utils.ui_timing import SLASH_PANEL_AUTO_DELETE_SECONDS


def _base_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.purple(),
    )
    embed.set_footer(text="This help panel closes automatically.")
    return embed


def build_help_home_embed() -> discord.Embed:
    return _base_embed(
        "📖 Guild Bot Help",
        (
            "Select a category below:\n\n"
            "⚙️ __**Setup Help**__\n"
            "*Configure the bot for your server*\n\n"
            "⚔️ __**Raid Help**__\n"
            "*Create and manage raids*\n\n"
            "📊 __**Attendance Help**__\n"
            "*Understand attendance tracking*\n\n"
            "👤 __**Player Help**__\n"
            "*How to sign up and manage your character*"
        ),
    )


def build_setup_help_embed() -> discord.Embed:
    return _base_embed(
        "⚙️ Setup Help",
        (
            "📌 __**Initial Setup**__\n"
            "Run `/setup` as a server administrator.\n\n"
            "⚙️ __**Configure the bot**__\n"
            "Set your:\n"
            "• **Raid Admins / Leaders**\n"
            "• **Raid Team**\n"
            "• **WeakAuras Channel**\n\n"
            "🚀 __**You're ready**__\n"
            "Raid leaders can now create raids using `/raid`.\n\n"
            "💡 *You can always change these settings later in the setup panel.*"
        ),
    )


def build_raid_help_embed() -> discord.Embed:
    return _base_embed(
        "⚔️ Raid Help",
        (
            "📌 __**Create a raid**__\n"
            "Use `/raid` to open the raid builder.\n\n"

            "⚙️ __**Configure raid details**__\n"
            "• **Title**\n"
            "• **Description**\n"
            "• **Leader**\n"
            "• **Date & Time**\n"
            "• **Channel**\n\n"

            "💾 __**Templates**__\n"
            "Save raid setups as templates to reuse later.\n"
            "*Perfect for weekly raids.*\n\n"

            "🔁 __**Recurring raids**__\n"
            "Create raids that automatically repeat.\n"
            "*Example: Every Wednesday or Sunday.*\n\n"

            "⏰ __**Reminders**__\n"
            "The bot automatically reminds players:\n"
            "• **Before the raid starts**\n"
            "• **If they haven't signed up**\n\n"

            "👥 __**After posting**__\n"
            "Players sign up directly from the signup message.\n\n"

            "🎛️ __**Raid Control**__\n"
            "Manage everything from the **Raid Control** button:\n"
            "• Edit raid\n"
            "• Build comp\n"
            "• Manage attendance\n\n"

            "💡 *All raid information can be edited later in Raid Control.*"
        ),
    )


def build_attendance_help_embed() -> discord.Embed:
    return _base_embed(
        "📊 Attendance Help",
        (
            "📌 __**How attendance works**__\n"
            "Attendance is based on the **posted comp**.\n\n"
            "📸 __**Snapshot system**__\n"
            "When a comp is posted, the bot stores:\n"
            "• **Signed players**\n"
            "• **Benched players**\n"
            "• **Late players**\n"
            "• **Tentative players**\n"
            "• **Absent players**\n"
            "• **Not selected / no-sign players**\n\n"
            "🔄 __**Can it be changed?**__\n"
            "Yes — raid leaders can edit attendance later.\n\n"
            "📈 __**View attendance**__\n"
            "Use `/attendance` to see reports.\n\n"
            "💡 *Attendance always reflects the comp at the time it was posted.*"
        ),
    )


def build_player_help_embed() -> discord.Embed:
    return _base_embed(
        "👤 Player Help",
        (
            "📌 __**Sign up**__\n"
            "Select your class from the signup dropdown.\n\n"
            "💾 __**Saved characters**__\n"
            "If you already have a saved character for that class, the bot can auto-sign you.\n\n"
            "🆕 __**New character**__\n"
            "If you do not have one saved yet, you will choose a spec first.\n\n"
            "🔄 __**Change your status**__\n"
            "Use the main signup buttons to change to:\n"
            "• **Bench**\n"
            "• **Late**\n"
            "• **Tentative**\n"
            "• **Absence**\n\n"
            "📝 __**Notes**__\n"
            "**Late**, **Tentative**, and **Absence** require a note.\n\n"
            "⚙️ __**Edit signup**__\n"
            "Use the signup panel to update:\n"
            "• **Name**\n"
            "• **Spec**\n"
            "• **Note**\n\n"
            "💡 *You can update your signup at any time.*"
        ),
    )


class HelpSectionButton(discord.ui.Button):
    def __init__(self, label: str, section: str, row: int = 0):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.section = section

    async def callback(self, interaction: discord.Interaction):
        if self.section == "setup":
            embed = build_setup_help_embed()
        elif self.section == "raid":
            embed = build_raid_help_embed()
        elif self.section == "attendance":
            embed = build_attendance_help_embed()
        else:
            embed = build_player_help_embed()

        await interaction.response.edit_message(
            embed=embed,
            view=HelpView(current_section=self.section),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SLASH_PANEL_AUTO_DELETE_SECONDS)
        )


class BackToHelpHomeButton(discord.ui.Button):
    def __init__(self, row: int = 1):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.primary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=build_help_home_embed(),
            view=HelpView(),
        )
        asyncio.create_task(
            delete_interaction_after(interaction, SLASH_PANEL_AUTO_DELETE_SECONDS)
        )


class CloseHelpButton(discord.ui.Button):
    def __init__(self, row: int = 1):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Help panel closed.",
            embed=None,
            view=None,
        )
        asyncio.create_task(delete_interaction_after(interaction, 1))


class HelpView(discord.ui.View):
    def __init__(self, current_section: str | None = None):
        super().__init__(timeout=120)

        self.add_item(HelpSectionButton("Setup Help", "setup", row=0))
        self.add_item(HelpSectionButton("Raid Help", "raid", row=0))
        self.add_item(HelpSectionButton("Attendance Help", "attendance", row=0))
        self.add_item(HelpSectionButton("Player Help", "player", row=0))

        if current_section is not None:
            self.add_item(BackToHelpHomeButton(row=1))

        self.add_item(CloseHelpButton(row=1))