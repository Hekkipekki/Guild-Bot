import discord
from discord.ext import commands

from services.raid.raid_preset_service import (
    build_wednesday_signup,
    build_sunday_signup,
    build_template_signup,
)
from services.signup.signup_message_service import send_signup_message


class SignupCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _delete_command_message(self, ctx: commands.Context) -> None:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        except discord.NotFound:
            pass

    async def _send_temporary_confirmation(
        self,
        ctx: commands.Context,
        content: str,
        *,
        delete_after: int = 5,
    ) -> None:
        msg = await ctx.send(content)
        try:
            await msg.delete(delay=delete_after)
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _post_signup(self, ctx: commands.Context, signup: dict) -> None:
        await self._delete_command_message(ctx)

        ok = await send_signup_message(ctx, signup)
        if not ok:
            await self._send_temporary_confirmation(
                ctx,
                "⚠ Failed to create signup message.",
            )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def nuke(self, ctx: commands.Context):
        await self._delete_command_message(ctx)

        deleted_messages = await ctx.channel.purge(limit=1000)

        await self._send_temporary_confirmation(
            ctx,
            f"💣 Deleted {len(deleted_messages)} messages from this channel.",
        )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def template(self, ctx: commands.Context):
        signup = build_template_signup(ctx.guild.id, ctx.channel.id)
        await self._post_signup(ctx, signup)

async def setup(bot):
    await bot.add_cog(SignupCommands(bot))