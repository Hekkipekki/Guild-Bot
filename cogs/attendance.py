import discord
from discord import app_commands, File
from discord.ext import commands

from services.attendance.attendance_image_service import (
    render_attendance_report_image,
)
from services.attendance.attendance_report_service import (
    get_guild_attendance_records,
)


class AttendanceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="attendance",
        description="Show the guild attendance report.",
    )
    @app_commands.describe(
        raids="Number of recent raids to include (default: 12)",
        include_unfinalized="Include raids that are not finalized yet",
    )
    async def attendance(
        self,
        interaction: discord.Interaction,
        raids: int | None = None,
        include_unfinalized: bool = False,
    ):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        limit_raids = raids or 12
        if limit_raids < 1:
            limit_raids = 1
        if limit_raids > 30:
            limit_raids = 30

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            finalized_only = not include_unfinalized

            # Fallback so older test data still works
            if finalized_only:
                finalized_records = get_guild_attendance_records(
                    guild.id,
                    finalized_only=True,
                )
                if not finalized_records:
                    finalized_only = False

            buffer = render_attendance_report_image(
                guild_id=guild.id,
                finalized_only=finalized_only,
                limit_raids=limit_raids,
                title=None,
            )

            file = File(fp=buffer, filename="attendance_report.png")

            await interaction.followup.send(
                file=file,
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"⚠ Failed to generate attendance report: {type(e).__name__}: {e}",
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(AttendanceCommands(bot))