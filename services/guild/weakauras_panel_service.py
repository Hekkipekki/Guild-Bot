import discord

from services.guild.guild_settings_service import (
    get_weakauras_channel_id,
    get_weakauras_message_id,
    set_weakauras_message_id,
)
from views.raidpack_views import RaidPackView


WA_PANEL_TEXT = """# Must Have Addons & WA's
- [Method Raid Tools](https://www.curseforge.com/wow/addons/method-raid-tools)
- [RC Loot Council](https://www.curseforge.com/wow/addons/rclootcouncil-classic)
- <:fojji:1482050733258838087> [Fojjicore](https://www.curseforge.com/wow/addons/fojjicore)
- <:fojji:1482050733258838087> [Fojji - Raid Assignments User](https://wago.io/FojjiRaidAssignsUserMoP) > `turmeric123`
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


async def ensure_weakauras_panel_for_guild(bot, guild: discord.Guild) -> tuple[bool, str]:
    channel_id = get_weakauras_channel_id(guild.id)
    if not channel_id:
        return False, "No WeakAuras channel configured."

    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except Exception:
            return False, "Configured WeakAuras channel not found."

    message_id = get_weakauras_message_id(guild.id)

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(
                content=WA_PANEL_TEXT,
                view=RaidPackView(),
                suppress=True,
            )
            return True, "WeakAuras panel updated."
        except discord.NotFound:
            set_weakauras_message_id(guild.id, None)
        except Exception as e:
            return False, f"Failed to update existing panel: {e}"

    try:
        msg = await channel.send(
            content=WA_PANEL_TEXT,
            view=RaidPackView(),
            suppress_embeds=True,
        )
        set_weakauras_message_id(guild.id, msg.id)
        return True, "WeakAuras panel posted."
    except Exception as e:
        return False, f"Failed to post WeakAuras panel: {e}"