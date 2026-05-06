import config


NOTE_MARKER = " - 📝"


def get_player_display_text(user_id: str, info: dict) -> str:
    """
    Priority for signed players:
    1. explicit signup character name
    2. fallback to stored display_name if present
    3. fallback to Discord mention
    """
    char_name = (info.get("name") or "").strip()
    if char_name:
        return char_name

    display_name = (info.get("display_name") or "").strip()
    if display_name:
        return display_name

    return f"<@{user_id}>"


def _has_note(info: dict) -> bool:
    return bool((info.get("note") or "").strip())


def format_player_line(user_id: str, info: dict) -> str:
    spec = info.get("spec", "Unknown")
    emoji = config.SPEC_EMOJIS.get(spec, "")
    player_text = get_player_display_text(user_id, info)

    if _has_note(info):
        player_text = f"{player_text}{NOTE_MARKER}"

    return f"{emoji} {player_text}" if emoji else player_text


def format_unassigned_player(user_id: str) -> str:
    return f"<@{user_id}>"