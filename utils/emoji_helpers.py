import discord
import config


def _parse_emoji(raw: str | None):
    if not raw:
        return None

    try:
        return discord.PartialEmoji.from_str(raw)
    except Exception:
        return None


def parse_spec_emoji(spec_name: str):
    return _parse_emoji(config.SPEC_EMOJIS.get(spec_name))


def parse_class_emoji(class_name: str):
    return _parse_emoji(getattr(config, "CLASS_EMOJIS", {}).get(class_name))


def parse_button_emoji(name: str):
    return _parse_emoji(getattr(config, "BUTTON_EMOJIS", {}).get(name))


def get_button_emoji(name: str):
    return parse_button_emoji(name)