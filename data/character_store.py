import json
from pathlib import Path


FILE = Path(__file__).resolve().parent / "characters.json"


def _ensure_data_dir() -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)


def load_characters() -> dict:
    if not FILE.exists():
        return {}

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_characters(data: dict) -> None:
    _ensure_data_dir()

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _is_legacy_user_only_format(data: dict) -> bool:
    """
    Legacy format:
    {
        "user_id": [characters]
    }

    New format:
    {
        "guild_id": {
            "user_id": [characters]
        }
    }
    """
    if not data:
        return False

    return all(isinstance(value, list) for value in data.values())


def _migrate_legacy_data_to_guild(data: dict, guild_id: int) -> dict:
    """
    One-time lazy migration:
    Move legacy flat user->characters data into the guild that first accesses it.
    """
    if not _is_legacy_user_only_format(data):
        return data

    migrated = {
        str(guild_id): {
            str(user_id): chars if isinstance(chars, list) else []
            for user_id, chars in data.items()
        }
    }
    save_characters(migrated)
    return migrated


def _get_guild_bucket(data: dict, guild_id: int) -> dict:
    data = _migrate_legacy_data_to_guild(data, guild_id)

    guild_key = str(guild_id)
    guild_bucket = data.get(guild_key)

    if not isinstance(guild_bucket, dict):
        data[guild_key] = {}
        save_characters(data)
        guild_bucket = data[guild_key]

    return guild_bucket


def _get_user_list(data: dict, guild_id: int, user_id: int) -> list[dict]:
    guild_bucket = _get_guild_bucket(data, guild_id)
    user_key = str(user_id)

    user_chars = guild_bucket.get(user_key, [])
    if not isinstance(user_chars, list):
        guild_bucket[user_key] = []
        save_characters(data)
        return []

    return user_chars


def get_user_characters(guild_id: int, user_id: int) -> list[dict]:
    data = load_characters()
    return _get_user_list(data, guild_id, user_id)


def get_character_by_class(guild_id: int, user_id: int, class_name: str) -> dict | None:
    characters = get_user_characters(guild_id, user_id)

    for char in characters:
        if char.get("class") == class_name:
            return char

    return None


def add_character(guild_id: int, user_id: int, char: dict) -> bool:
    data = load_characters()
    guild_bucket = _get_guild_bucket(data, guild_id)
    user_key = str(user_id)

    if user_key not in guild_bucket or not isinstance(guild_bucket[user_key], list):
        guild_bucket[user_key] = []

    existing = guild_bucket[user_key]

    for saved in existing:
        if saved.get("class") == char.get("class"):
            return False

    existing.append(char)
    save_characters(data)
    return True


def remove_character(guild_id: int, user_id: int, index: int) -> bool:
    data = load_characters()
    guild_bucket = _get_guild_bucket(data, guild_id)
    user_key = str(user_id)

    if user_key not in guild_bucket or not isinstance(guild_bucket[user_key], list):
        return False

    if not (0 <= index < len(guild_bucket[user_key])):
        return False

    guild_bucket[user_key].pop(index)
    save_characters(data)
    return True


def update_character_name_by_class(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_name: str,
) -> bool:
    data = load_characters()
    guild_bucket = _get_guild_bucket(data, guild_id)
    user_key = str(user_id)

    if user_key not in guild_bucket or not isinstance(guild_bucket[user_key], list):
        return False

    for char in guild_bucket[user_key]:
        if char.get("class") == class_name:
            char["name"] = new_name.strip()
            save_characters(data)
            return True

    return False


def update_character_spec_by_class(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_spec: str,
    new_role: str,
) -> bool:
    data = load_characters()
    guild_bucket = _get_guild_bucket(data, guild_id)
    user_key = str(user_id)

    if user_key not in guild_bucket or not isinstance(guild_bucket[user_key], list):
        return False

    for char in guild_bucket[user_key]:
        if char.get("class") == class_name:
            char["spec"] = new_spec
            char["role"] = new_role
            save_characters(data)
            return True

    return False