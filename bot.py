import asyncio
import traceback

import discord
from discord.ext import commands

import config
from data.signup_store import load_signups
from services.bot.command_sync_service import build_command_sync_plan
from services.guild.guild_settings_service import sync_guild_identity
from services.panels.panel_registry import PERMANENT_PANELS
from services.panels.permanent_panel_service import ensure_permanent_panel
from views.raidpack_views import RaidPackView
from views.signup.comp.comp_message_view import CompMessageView
from views.signup_views import SignupView


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

_views_registered = False
_commands_synced = False

EXTENSIONS = [
    "cogs.signup",
    "cogs.reminders",
    "cogs.guild_admin",
    "cogs.raid_builder",
    "cogs.raid_lifecycle",
    "cogs.attendance",
    "cogs.help",
    "cogs.scheduling",
    "cogs.warcraftlogs",
]


def _register_persistent_views() -> None:
    global _views_registered

    if _views_registered:
        return

    bot.add_view(RaidPackView())

    signups = load_signups()

    for message_id in signups.keys():
        try:
            bot.add_view(SignupView(str(message_id)))
        except Exception as e:
            print(f"Failed to register SignupView for message {message_id}: {e}")

    for raid_id, signup in signups.items():
        if not signup.get("comp_message_id"):
            continue

        try:
            bot.add_view(CompMessageView(str(raid_id)))
        except Exception as e:
            print(f"Failed to register CompMessageView for raid {raid_id}: {e}")

    _views_registered = True


async def _ensure_permanent_panels() -> None:
    for guild in bot.guilds:
        for panel in PERMANENT_PANELS:
            try:
                _, message = await ensure_permanent_panel(bot, guild, panel)
                print(f"[{panel.label}] {guild.name}: {message}")
            except Exception as e:
                print(f"[{panel.label}] {guild.name}: failed - {e}")


async def _sync_application_commands() -> None:
    global _commands_synced

    if _commands_synced:
        return

    plan = build_command_sync_plan(
        dev_mode=bool(config.DEV_MODE),
        test_guild_id=getattr(config, "TEST_GUILD_ID", None),
    )

    try:
        if plan.is_guild_sync:
            guild_obj = discord.Object(id=plan.guild_id)
            bot.tree.clear_commands(guild=guild_obj)
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            print(
                f"[Commands] DEV_MODE: synced {len(synced)} slash command(s) "
                f"to test guild {plan.guild_id}. Global commands were not synced."
            )
        else:
            synced = await bot.tree.sync()
            print(f"[Commands] Production: globally synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        raise

    _commands_synced = True


async def _load_extensions() -> None:
    for extension in EXTENSIONS:
        await bot.load_extension(extension)


async def _sync_guild_names() -> None:
    for guild in bot.guilds:
        try:
            sync_guild_identity(guild.id, guild.name)
        except Exception as e:
            print(f"[Guild Sync] {guild.id}: failed to sync guild name - {e}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        sync_guild_identity(guild.id, guild.name)
    except Exception as e:
        print(f"[Guild Join] Failed to store guild name for {guild.id}: {e}")

    embed = discord.Embed(
        title=f"Thanks for adding Guild Raid Bot to {guild.name}!",
        description=(
            "Before using the bot, a server administrator must configure it.\n\n"
            "⚙️ __**Setup**__\n"
            "**Run:** `/setup`\n\n"
            "Then configure:\n"
            "• **WeakAuras channel**\n"
            "• **Raid admins / leaders**\n"
            "• **Raid team** *(optional)*\n\n"
            "⚔️ __**Create raids**__\n"
            "After setup, use `/raid` to create raid signups.\n\n"
            "📖 __**Need help?**__\n"
            "Use `/help` to open the help panel."
        ),
        color=discord.Color.purple(),
    )
    embed.set_footer(text="Guild Raid Bot setup")

    me = guild.me

    channel = guild.system_channel
    if channel and me and channel.permissions_for(me).send_messages:
        try:
            await channel.send(embed=embed)
            return
        except Exception as e:
            print(f"[Guild Join] Failed to send onboarding in system channel for {guild.name}: {e}")

    for channel in guild.text_channels:
        if me and channel.permissions_for(me).send_messages:
            try:
                await channel.send(embed=embed)
                return
            except Exception:
                continue


@bot.event
async def on_ready():
    _register_persistent_views()
    await _sync_application_commands()
    await _sync_guild_names()
    await _ensure_permanent_panels()

    try:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/raid , /setup , /attendance",
            )
        )
    except Exception as e:
        print(f"Failed to set presence: {e}")

    runtime_mode = "development" if config.DEV_MODE else "production"
    print(f"Logged in as {bot.user} ({runtime_mode})")


@bot.event
async def on_command_error(ctx, error):
    print("Command error:")
    traceback.print_exception(type(error), error, error.__traceback__)


async def main():
    if not config.TOKEN:
        raise RuntimeError("Bot token not found. Define TOKEN in secrets_local.py")

    build_command_sync_plan(
        dev_mode=bool(config.DEV_MODE),
        test_guild_id=getattr(config, "TEST_GUILD_ID", None),
    )

    async with bot:
        await _load_extensions()
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
