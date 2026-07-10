import discord

from services.guild.guild_settings_service import (
    get_hidden_weakaura_items,
    get_weakauras_channel_id,
    get_weakauras_message_id,
    set_weakauras_message_id,
)
from views.raidpack_views import RaidPackView


WA_SECTIONS = [
    {
        "heading": "## Required",
        "items": [
            ("required.method_raid_tools", "- [Method Raid Tools](https://www.curseforge.com/wow/addons/method-raid-tools)"),
            ("required.rc_loot_council", "- [RC Loot Council](https://www.curseforge.com/wow/addons/rclootcouncil-classic)"),
            ("required.fojjicore", "- <:fojji:1482050733258838087> [Fojjicore](https://www.curseforge.com/wow/addons/fojjicore)"),
            ("required.raid_assignments_user", "- <:fojji:1482050733258838087> [Raid Assignments User](https://wago.io/FojjiRaidAssignsUserMoP) > `turmeric123`"),
            ("required.raid_anchors", "- <:fojji:1482050733258838087> [Raid Anchors WA](https://wago.io/FojjiRaidAnchors-MoP)"),
            ("required.stormlash_banner", "- <:fojji:1482050733258838087> [Stormlash & Skull Banner Rotation](https://wago.io/Fojji-StormlashBanner-Rotations)"),
        ],
    },
    {
        "heading": "### Raidleader Only",
        "prefix": ["## Raid WeakAuras", "Use the buttons below to download the raid packs.", ""],
        "items": [
            ("raidleader.fojji_soo", "- <:fojji:1482050733258838087> [Fojji SoO Raid Leader](https://wago.io/Fojji-SoO-RL) > `cucumber123`"),
        ],
    },
    {
        "heading": "## Optional WeakAuras",
        "items": [
            ("optional.numen_core", "- <:fojji:1482050733258838087> [Numen Core](https://wago.io/Fojji-NumenCoreMoP) > `zoodle123` (External Requests)"),
            ("optional.dungeon_pack", "- <:fojji:1482050733258838087> [Dungeon Pack](https://wago.io/Fojji-Dungeons-MoP) > `flounder123`"),
            ("optional.dungeon_pack_pf", "- <:fojji:1482050733258838087> [Dungeon Pack PF](https://wago.io/Fojji-Dungeons-MoP-PF) > `paprika123`"),
            ("optional.gear_checker", "- <:fojji:1482050733258838087> [Gear Checker](https://wago.io/Fojji-GearChecker) > `cucina123`"),
            ("optional.trinket_proc", "- <:fojji:1482050733258838087> [Trinket/Proc Tracker](https://wago.io/FojjiTrinkets-MoP)"),
            ("optional.bonus_loot", "- <:fojji:1482050733258838087> [Bonus Loot History](https://wago.io/Fojji-BonusLoot) > `turkey123`"),
            ("optional.cooldown_pulse", "- <:fojji:1482050733258838087> [Cooldown Pulse](https://wago.io/FojjiCooldownPulse-MoP) > `bukayo123`"),
            ("optional.raid_timeline", "- <:fojji:1482050733258838087> [Raid Ability Timeline](https://wago.io/FojjiRaidAbilityTimeline) > `turnip123`"),
            ("optional.reminders", "- <:fojji:1482050733258838087> [Glyph/Talent/Set Reminders](https://wago.io/FojjiGlyphTalentSet-Reminders-MoP) > `ketchup123`"),
        ],
    },
    {
        "heading": "## Class WA's",
        "items": [
            ("class.fojji_class_was", "- <:fojji:1482050733258838087> [Fojji Class WA's](https://discord.com/channels/1423706462773051542/1445447282559422545)"),
        ],
    },
]

WA_ITEM_LABELS = {
    "required.method_raid_tools": "Method Raid Tools",
    "required.rc_loot_council": "RC Loot Council",
    "required.fojjicore": "Fojjicore",
    "required.raid_assignments_user": "Raid Assignments User",
    "required.raid_anchors": "Raid Anchors WA",
    "required.stormlash_banner": "Stormlash & Banner Rotation",
    "raidleader.fojji_soo": "Fojji SoO Raid Leader",
    "optional.numen_core": "Numen Core",
    "optional.dungeon_pack": "Dungeon Pack",
    "optional.dungeon_pack_pf": "Dungeon Pack PF",
    "optional.gear_checker": "Gear Checker",
    "optional.trinket_proc": "Trinket/Proc Tracker",
    "optional.bonus_loot": "Bonus Loot History",
    "optional.cooldown_pulse": "Cooldown Pulse",
    "optional.raid_timeline": "Raid Ability Timeline",
    "optional.reminders": "Glyph/Talent/Set Reminders",
    "class.fojji_class_was": "Fojji Class WA's",
}


def build_weakauras_panel_text(guild_id: int) -> str:
    hidden = set(get_hidden_weakaura_items(guild_id))
    lines = ["# Must Have Addons & WA's", ""]

    for section in WA_SECTIONS:
        visible_items = [line for key, line in section["items"] if key not in hidden]
        if not visible_items:
            continue

        prefix = section.get("prefix", [])
        lines.extend(prefix)
        lines.append(section["heading"])
        lines.extend(visible_items)
        lines.append("")

    lines.extend([
        "**Click the buttons below to download the Raid Pack WAs.**",
        "",
        "> Last updated `2026-07-10 Boss packs`",
    ])
    return "\n".join(lines).strip()


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

    content = build_weakauras_panel_text(guild.id)
    message_id = get_weakauras_message_id(guild.id)

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(content=content, view=RaidPackView(), suppress=True)
            return True, "WeakAuras panel updated."
        except discord.NotFound:
            set_weakauras_message_id(guild.id, None)
        except Exception as e:
            return False, f"Failed to update existing panel: {e}"

    try:
        msg = await channel.send(content=content, view=RaidPackView(), suppress_embeds=True)
        set_weakauras_message_id(guild.id, msg.id)
        return True, "WeakAuras panel posted."
    except Exception as e:
        return False, f"Failed to post WeakAuras panel: {e}"
