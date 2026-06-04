from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)


DATA_FILE_NAME = "characters.json"


def _get_characters_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, DATA_FILE_NAME)


def _normalize_characters_data(data: dict | object) -> dict[str, list[dict]]:
    """
    New guild-specific format:
    {
        "user_id": [
            {"name": "...", "class": "...", "spec": "...", "role": "..."}
        ]
    }
    """
    if not isinstance(data, dict):
        return {}

    normalized: dict[str, list[dict]] = {}

    for user_id, chars in data.items():
        if isinstance(chars, list):
            normalized[str(user_id)] = [
                char for char in chars if isinstance(char, dict)
            ]

    return normalized


def load_characters(guild_id: int | str | None = None) -> dict:
    """
    Compatibility function.

    Preferred:
        load_characters(guild_id)

    Old fallback:
        load_characters()
        returns all guild character files as:
        {
            guild_id: {
                user_id: [characters]
            }
        }
    """
    if guild_id is not None:
        path = _get_characters_file(guild_id)
        return _normalize_characters_data(read_json(path, {}))

    from data.guild_data import GUILDS_ROOT

    if not GUILDS_ROOT.exists():
        return {}

    result: dict[str, dict[str, list[dict]]] = {}

    for guild_dir in GUILDS_ROOT.iterdir():
        if not guild_dir.is_dir():
            continue

        path = guild_dir / DATA_FILE_NAME
        result[guild_dir.name] = _normalize_characters_data(read_json(path, {}))

    return result


def save_characters(data: dict, guild_id: int | str | None = None) -> None:
    """
    Compatibility function.

    Preferred:
        save_characters(data, guild_id)

    Old fallback:
        save_characters(all_data)
        expects:
        {
            guild_id: {
                user_id: [characters]
            }
        }
    """
    if guild_id is not None:
        path = _get_characters_file(guild_id)
        write_json(path, _normalize_characters_data(data), indent=4)
        return

    if not isinstance(data, dict):
        return

    for maybe_guild_id, guild_data in data.items():
        if isinstance(guild_data, dict):
            path = _get_characters_file(maybe_guild_id)
            write_json(path, _normalize_characters_data(guild_data), indent=4)


def _get_user_list(data: dict, user_id: int | str) -> list[dict]:
    user_key = str(user_id)

    user_chars = data.get(user_key, [])
    if not isinstance(user_chars, list):
        data[user_key] = []
        return []

    return user_chars


def get_user_characters(guild_id: int, user_id: int) -> list[dict]:
    data = load_characters(guild_id)
    return _get_user_list(data, user_id)


def get_character_by_class(guild_id: int, user_id: int, class_name: str) -> dict | None:
    characters = get_user_characters(guild_id, user_id)

    for char in characters:
        if char.get("class") == class_name:
            return char

    return None


def add_character(guild_id: int, user_id: int, char: dict) -> bool:
    data = load_characters(guild_id)
    user_key = str(user_id)

    if user_key not in data or not isinstance(data[user_key], list):
        data[user_key] = []

    existing = data[user_key]

    for saved in existing:
        if saved.get("class") == char.get("class"):
            return False

    existing.append(char)
    save_characters(data, guild_id)
    return True


def remove_character(guild_id: int, user_id: int, index: int) -> bool:
    data = load_characters(guild_id)
    user_key = str(user_id)

    if user_key not in data or not isinstance(data[user_key], list):
        return False

    if not (0 <= index < len(data[user_key])):
        return False

    data[user_key].pop(index)
    save_characters(data, guild_id)
    return True


def update_character_name_by_class(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_name: str,
) -> bool:
    data = load_characters(guild_id)
    user_key = str(user_id)

    if user_key not in data or not isinstance(data[user_key], list):
        return False

    for char in data[user_key]:
        if char.get("class") == class_name:
            char["name"] = new_name.strip()
            save_characters(data, guild_id)
            return True

    return False


def update_character_spec_by_class(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_spec: str,
    new_role: str,
) -> bool:
    data = load_characters(guild_id)
    user_key = str(user_id)

    if user_key not in data or not isinstance(data[user_key], list):
        return False

    for char in data[user_key]:
        if char.get("class") == class_name:
            char["spec"] = new_spec
            char["role"] = new_role
            save_characters(data, guild_id)
            return True

    return False