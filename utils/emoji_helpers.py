import discord
import config


def _is_dev_mode() -> bool:
    return bool(getattr(config, "DEV_MODE", False))


SPEC_FALLBACK_EMOJIS = {
    "Blood": "🛡️",
    "FrostDK": "❄️",
    "Unholy": "💀",
    "Balance": "🌙",
    "Feral": "🐈",
    "Guardian": "🐻",
    "RestorationDruid": "🌿",
    "Beast Mastery": "🐺",
    "BeastMastery": "🐺",
    "Marksmanship": "🏹",
    "Survival": "🪤",
    "Arcane": "🔮",
    "Fire": "🔥",
    "Frost": "❄️",
    "Brewmaster": "🍺",
    "Mistweaver": "🌫️",
    "Windwalker": "🌪️",
    "HolyPaladin": "✨",
    "ProtectionPaladin": "🛡️",
    "Retribution": "🔨",
    "Discipline": "🟡",
    "HolyPriest": "✨",
    "Shadow": "🌑",
    "Assassination": "🗡️",
    "Combat": "⚔️",
    "Subtlety": "🥷",
    "Sublety": "🥷",
    "Elemental": "⚡",
    "Enhancement": "🔨",
    "Enmhancement": "🔨",
    "RestorationShaman": "💧",
    "Affliction": "🟣",
    "Demonology": "😈",
    "Destruction": "🔥",
    "Arms": "⚔️",
    "Fury": "🪓",
    "ProtectionWarrior": "🛡️",
}


CLASS_FALLBACK_EMOJIS = {
    "Death Knight": "💀",
    "Warrior": "⚔️",
    "Druid": "🐻",
    "Paladin": "🔨",
    "Monk": "🍃",
    "Priest": "✨",
    "Mage": "🔥",
    "Warlock": "💜",
    "Hunter": "🏹",
    "Rogue": "🗡️",
    "Shaman": "⚡",
}


BUTTON_FALLBACK_EMOJIS = {
    "sign": "✅",
    "late": "⏰",
    "note": "📝",
    "bench": "🪑",
    "tentative": "❔",
    "absence": "❌",
    "config": "⚙️",
    "leave": "🚪",
    "create_raid": "➕",
    "create_template": "📋",
    "submit_raid": "✅",
    "cancel_raid": "🗑️",
}


def _parse_emoji(raw: str | None):
    if not raw:
        return None

    try:
        return discord.PartialEmoji.from_str(raw)
    except Exception:
        return None


def _emoji_from_config_or_fallback(
    config_map: dict,
    fallback_map: dict,
    key: str,
):
    fallback = fallback_map.get(key, "❔")

    if _is_dev_mode():
        return fallback

    parsed = _parse_emoji(config_map.get(key))

    return parsed or fallback


def parse_spec_emoji(spec_name: str):
    return _emoji_from_config_or_fallback(
        getattr(config, "SPEC_EMOJIS", {}),
        SPEC_FALLBACK_EMOJIS,
        spec_name,
    )


def parse_class_emoji(class_name: str):
    return _emoji_from_config_or_fallback(
        getattr(config, "CLASS_EMOJIS", {}),
        CLASS_FALLBACK_EMOJIS,
        class_name,
    )


def parse_button_emoji(name: str):
    return _emoji_from_config_or_fallback(
        getattr(config, "BUTTON_EMOJIS", {}),
        BUTTON_FALLBACK_EMOJIS,
        name,
    )


def get_button_emoji(name: str):
    return parse_button_emoji(name)