from discord.ext import commands

from services.guild.guild_settings_service import get_weakauras_channel_id
from views.raidpack_views import RaidPackView


WA_PANEL_TEXT = """# Must Have Addons & WA's
- [Method Raid Tools](https://www.curseforge.com/wow/addons/method-raid-tools)
- [Gargul](https://www.curseforge.com/wow/addons/gargul)
- <:fojji:1482050733258838087> [Fojjicore](https://www.curseforge.com/wow/addons/fojjicore)
- <:fojji:1482050733258838087> [Fojji - Raid Assignments User](https://wago.io/FojjiRaidAssignsUserMoP) > `cheddar123`
- <:fojji:1482050733258838087> [Raid Anchors WA](https://wago.io/FojjiRaidAnchors-MoP)

**Raid Weakauras (Check at bottom)**

### RAIDLEADER ONLY
- <:fojji:1482050733258838087> [Fojji - [T15][Raid Leader] Throne of Thunder](https://wago.io/Fojji-ToT-RL) > `macaron123`

# Optional WeakAuras
- <:fojji:1482050733258838087> [Dungeon Pack](https://wago.io/Fojji-Dungeons-MoP) > `nutella123`
- <:fojji:1482050733258838087> [Dungeon Pack](https://wago.io/Fojji-Dungeons-MoP-PF) > `paprika123`
- <:fojji:1482050733258838087> [Fojji - Gear Checker](https://wago.io/Fojji-GearChecker) > `cucina123`
- <:fojji:1482050733258838087> [Fojji Trinket/Proc Tracker](https://wago.io/FojjiTrinkets-MoP)
- <:fojji:1482050733258838087> [Fojji - Raid Ability Timeline](https://wago.io/FojjiRaidAbilityTimeline) > `turnip123`

**Click the buttons below to download the Raid Pack WAs**
Click *"Dismiss this message"* if it shows an old version, then re-click the button.
"""


class WACommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def tot(self, ctx: commands.Context):
        guild = ctx.guild
        if guild is None:
            await ctx.send("❌ This command can only be used in a server.")
            return

        channel_id = get_weakauras_channel_id(guild.id)
        if not channel_id:
            await ctx.send(
                "❌ No WeakAuras channel is configured for this server. "
                "Use the Guild Admin panel to set one first."
            )
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                channel = None

        if channel is None:
            await ctx.send("❌ Could not find the configured WeakAuras channel.")
            return

        await channel.send(
            content=WA_PANEL_TEXT,
            view=RaidPackView(),
        )


async def setup(bot):
    await bot.add_cog(WACommands(bot))