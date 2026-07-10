from __future__ import annotations

import discord

from services.guild.setup_validation_service import (
    SetupValidationReport,
    ValidationState,
    repair_all_panels,
    repair_scheduling_panel,
    repair_weakauras_panel,
    validate_guild_setup,
)
from utils.embed_theme import build_panel_embed


_STATE_ICON = {
    ValidationState.OK: "✅",
    ValidationState.WARNING: "⚠️",
    ValidationState.ERROR: "❌",
}


def build_setup_validation_embed(
    guild: discord.Guild,
    report: SetupValidationReport,
) -> discord.Embed:
    if report.is_healthy:
        summary = "All configured channels and permanent panels passed validation."
    else:
        summary = (
            f"Found **{report.error_count}** error(s) and "
            f"**{report.warning_count}** warning(s)."
        )

    embed = build_panel_embed(
        title=f"Setup Validation — {guild.name}",
        description=summary,
    )
    for item in report.items:
        embed.add_field(
            name=f"{_STATE_ICON[item.state]} {item.label}",
            value=item.detail,
            inline=False,
        )
    return embed


async def _show_report(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
) -> None:
    guild = interaction.guild
    if guild is None:
        if interaction.response.is_done():
            await interaction.followup.send(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
        return

    if not interaction.response.is_done():
        await interaction.response.defer()

    report = await validate_guild_setup(guild)
    await interaction.edit_original_response(
        content=content,
        embed=build_setup_validation_embed(guild, report),
        view=SetupValidationView(),
    )


class RefreshValidationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Refresh",
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await _show_report(interaction, content="Validation refreshed.")


class RepairWeakAurasButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Repair WeakAuras",
            style=discord.ButtonStyle.primary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()
        _, message = await repair_weakauras_panel(interaction.client, guild)
        await _show_report(interaction, content=message)


class RepairSchedulingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Repair Scheduling",
            style=discord.ButtonStyle.primary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()
        _, message = await repair_scheduling_panel(interaction.client, guild)
        await _show_report(interaction, content=message)


class RepairAllButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Repair All Panels",
            style=discord.ButtonStyle.success,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        await interaction.response.defer()
        messages = await repair_all_panels(interaction.client, guild)
        await _show_report(interaction, content="\n".join(messages))


class BackToSetupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.", ephemeral=True
            )
            return

        from views.guild_admin.guild_admin_helpers import build_guild_config_embed
        from views.guild_admin.guild_admin_view import GuildSetupView

        await interaction.response.edit_message(
            content=None,
            embed=build_guild_config_embed(guild),
            view=GuildSetupView(),
        )


class SetupValidationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(RefreshValidationButton())
        self.add_item(RepairWeakAurasButton())
        self.add_item(RepairSchedulingButton())
        self.add_item(RepairAllButton())
        self.add_item(BackToSetupButton())


async def open_setup_validation(interaction: discord.Interaction) -> None:
    await _show_report(interaction)
