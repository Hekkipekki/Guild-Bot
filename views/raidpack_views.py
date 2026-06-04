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
        label=config.PACKS["SoO_01_08"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="SoO_01_08",
        row=0,
    )
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "SoO_01_08")

    @discord.ui.button(
        label=config.PACKS["SoO_09_14"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="SoO_09_14",
        row=0,
    )
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "SoO_09_14")

    @discord.ui.button(
        label=config.PACKS["SoO_frames"]["label"],
        style=discord.ButtonStyle.primary,
        custom_id="SoO_frames",
        row=0,
    )
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "SoO_frames")

    @discord.ui.button(
        label=config.PACKS["SoO_assignments"]["label"],
        style=discord.ButtonStyle.secondary,
        custom_id="SoO_assignments",
        row=1,
    )
    async def b5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_wa(interaction, "SoO_assignments")