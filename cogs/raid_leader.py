import discord
from discord import app_commands
from discord.ext import commands

from services.raid.raid_admin_service import (
    update_raid_title,
    update_raid_description,
    update_raid_leader,
    update_raid_time_only,
    update_raid_date_only,
)
from services.signup.signup_refresh_service import refresh_signup_message_by_id
from utils.discord_utils import send_ephemeral_error, send_ephemeral_success
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
)


class RaidLeaderCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _refresh_signup(
        self,
        interaction: discord.Interaction,
        raid_id: int,
    ) -> bool:
        if interaction.channel is None:
            return False

        try:
            await refresh_signup_message_by_id(interaction.channel, raid_id)
            return True
        except Exception:
            return False

    @app_commands.command(name="raidtitle", description="Change the title of a raid signup")
    @app_commands.checks.has_permissions(administrator=True)
    async def raidtitle(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        new_title: str,
    ):
        try:
            raid_id_int = int(raid_id)
        except ValueError:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid ID must be a valid message ID number.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        ok = update_raid_title(raid_id_int, new_title)
        if not ok:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid signup not found.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        refreshed = await self._refresh_signup(interaction, raid_id_int)
        message = (
            "✅ Raid title updated."
            if refreshed
            else "✅ Raid title updated, but could not refresh the embed message."
        )
        await send_ephemeral_success(
            interaction,
            message,
            delete_after=SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
        )

    @app_commands.command(name="raiddesc", description="Change the description of a raid signup")
    @app_commands.checks.has_permissions(administrator=True)
    async def raiddesc(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        new_description: str,
    ):
        try:
            raid_id_int = int(raid_id)
        except ValueError:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid ID must be a valid message ID number.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        ok = update_raid_description(raid_id_int, new_description)
        if not ok:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid signup not found.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        refreshed = await self._refresh_signup(interaction, raid_id_int)
        message = (
            "✅ Raid description updated."
            if refreshed
            else "✅ Raid description updated, but could not refresh the embed message."
        )
        await send_ephemeral_success(
            interaction,
            message,
            delete_after=SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
        )

    @app_commands.command(name="raidleader", description="Change the leader text of a raid signup")
    @app_commands.checks.has_permissions(administrator=True)
    async def raidleader(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        new_leader: str,
    ):
        try:
            raid_id_int = int(raid_id)
        except ValueError:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid ID must be a valid message ID number.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        ok = update_raid_leader(raid_id_int, new_leader)
        if not ok:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid signup not found.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        refreshed = await self._refresh_signup(interaction, raid_id_int)
        message = (
            "✅ Raid leader updated."
            if refreshed
            else "✅ Raid leader updated, but could not refresh the embed message."
        )
        await send_ephemeral_success(
            interaction,
            message,
            delete_after=SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
        )

    @app_commands.command(name="raidtime", description="Change the raid time using HH:MM, for example 19:30")
    @app_commands.checks.has_permissions(administrator=True)
    async def raidtime(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        new_time: str,
    ):
        try:
            raid_id_int = int(raid_id)
        except ValueError:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid ID must be a valid message ID number.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        ok, updated_ts, error_message = update_raid_time_only(raid_id_int, new_time)
        if not ok:
            await send_ephemeral_error(
                interaction,
                f"⚠ {error_message}",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        refreshed = await self._refresh_signup(interaction, raid_id_int)
        message = (
            f"✅ Raid time updated to <t:{updated_ts}:t>."
            if refreshed
            else f"✅ Raid time updated to <t:{updated_ts}:t>, but could not refresh the embed message."
        )
        await send_ephemeral_success(
            interaction,
            message,
            delete_after=SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
        )

    @app_commands.command(name="raiddate", description="Change the raid date using YYYY-MM-DD, for example 2026-03-15")
    @app_commands.checks.has_permissions(administrator=True)
    async def raiddate(
        self,
        interaction: discord.Interaction,
        raid_id: str,
        new_date: str,
    ):
        try:
            raid_id_int = int(raid_id)
        except ValueError:
            await send_ephemeral_error(
                interaction,
                "⚠ Raid ID must be a valid message ID number.",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        ok, updated_ts, error_message = update_raid_date_only(raid_id_int, new_date)
        if not ok:
            await send_ephemeral_error(
                interaction,
                f"⚠ {error_message}",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )
            return

        refreshed = await self._refresh_signup(interaction, raid_id_int)
        message = (
            f"✅ Raid date updated to <t:{updated_ts}:D>."
            if refreshed
            else f"✅ Raid date updated to <t:{updated_ts}:D>, but could not refresh the embed message."
        )
        await send_ephemeral_success(
            interaction,
            message,
            delete_after=SLASH_COMMAND_RESPONSE_AUTO_DELETE_SECONDS,
        )

    @raidtitle.error
    @raiddesc.error
    @raidleader.error
    @raidtime.error
    @raiddate.error
    async def raid_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.errors.MissingPermissions):
            if not interaction.response.is_done():
                await send_ephemeral_error(
                    interaction,
                    "⛔ You do not have permission to use this command.",
                    delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
                )
            return

        if not interaction.response.is_done():
            await send_ephemeral_error(
                interaction,
                f"⚠ Command failed: {error}",
                delete_after=ERROR_MESSAGE_AUTO_DELETE_SECONDS,
            )


async def setup(bot):
    await bot.add_cog(RaidLeaderCommands(bot))