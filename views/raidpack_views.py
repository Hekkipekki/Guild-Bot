import discord
from pathlib import Path
import config


def get_pack_path(key: str) -> Path:
    return (config.BASE_DIR / config.PACKS[key]["file"]).resolve()


class RaidPackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def send_wa(self, interaction: discord.Interaction, key: str):
        cfg = config.PACKS[key]
        path = get_pack_path(key)

        if not path.exists():
            await interaction.response.send_message(
                f"❌ File not found for **{cfg['title']}**\n`{path}`",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"**{cfg['title']} {cfg['version']}**\n"
            f"• Download the file\n"
            f"• Open it and copy the import string",
            file=discord.File(str(path)),
            ephemeral=True,
        )

    @discord.ui.button(
        label=config.PACKS["tot_01_06"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="tot_01_06",
        row=0,
    )
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "tot_01_06")

    @discord.ui.button(
        label=config.PACKS["tot_07_13"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="tot_07_13",
        row=0,
    )
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "tot_07_13")

    @discord.ui.button(
        label=config.PACKS["tot_frames"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="tot_frames",
        row=0,
    )
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "tot_frames")

    @discord.ui.button(
        label=config.PACKS["tot_personal_assignments"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="tot_personal_assignments",
        row=0,
    )
    async def b4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "tot_personal_assignments")

    @discord.ui.button(
        label=config.PACKS["tot_assignments"]["label"],
        style=discord.ButtonStyle.secondary,
        custom_id="tot_assignments",
        row=1,
    )
    async def b5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "tot_assignments")