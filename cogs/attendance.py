import asyncio

import discord
from discord import app_commands, File
from discord.ext import commands

from services.attendance.attendance_image_service import (
    render_attendance_report_image,
)
from services.attendance.attendance_report_service import (
    get_guild_attendance_records,
)
from utils.discord_utils import delete_message_after, send_ephemeral_error
from utils.ui_timing import (
    ATTENDANCE_REPORT_AUTO_DELETE_SECONDS,
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
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
            await send_ephemeral_error(
                interaction,
                "⚠ This command can only be used in a server.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
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

            msg = await interaction.followup.send(
                file=file,
                ephemeral=True,
                wait=True,
            )

            asyncio.create_task(
                delete_message_after(
                    msg,
                    ATTENDANCE_REPORT_AUTO_DELETE_SECONDS,
                )
            )

        except Exception as e:
            await send_ephemeral_error(
                interaction,
                f"⚠ Failed to generate attendance report: {type(e).__name__}: {e}",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )


async def setup(bot):
    await bot.add_cog(AttendanceCommands(bot))