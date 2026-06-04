from typing import Any

from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)


DATA_FILE_NAME = "signups.json"


def _get_signups_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, DATA_FILE_NAME)


def _normalize_signups_data(data: dict | object) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}

    for message_id, signup in data.items():
        if isinstance(signup, dict):
            normalized[str(message_id)] = signup

    return normalized


def _get_signup_guild_id(signup: dict[str, Any]) -> str | None:
    guild_id = signup.get("guild_id")

    if guild_id in (None, "", 0):
        return None

    return str(guild_id)


def load_signups(guild_id: int | str | None = None) -> dict[str, dict[str, Any]]:
    """
    Preferred:
        load_signups(guild_id)

    Compatibility:
        load_signups()
        scans all guild-specific signup files and merges them into one dict.
    """
    if guild_id is not None:
        path = _get_signups_file(guild_id)
        return _normalize_signups_data(read_json(path, {}))

    from data.guild_data import GUILDS_ROOT

    if not GUILDS_ROOT.exists():
        return {}

    merged: dict[str, dict[str, Any]] = {}

    for guild_dir in GUILDS_ROOT.iterdir():
        if not guild_dir.is_dir():
            continue

        path = guild_dir / DATA_FILE_NAME
        guild_signups = _normalize_signups_data(read_json(path, {}))

        for message_id, signup in guild_signups.items():
            if "guild_id" not in signup or signup.get("guild_id") in (None, "", 0):
                signup["guild_id"] = guild_dir.name

            merged[str(message_id)] = signup

    return merged


def save_signups(
    data: dict[str, dict[str, Any]],
    guild_id: int | str | None = None,
) -> None:
    """
    Preferred:
        save_signups(data, guild_id)

    Compatibility:
        save_signups(data)
        splits signups into guild-specific files using each signup's guild_id.
    """
    normalized = _normalize_signups_data(data)

    if guild_id is not None:
        path = _get_signups_file(guild_id)

        for signup in normalized.values():
            if "guild_id" not in signup or signup.get("guild_id") in (None, "", 0):
                signup["guild_id"] = str(guild_id)

        write_json(path, normalized, indent=2)
        return

    grouped: dict[str, dict[str, dict[str, Any]]] = {}

    for message_id, signup in normalized.items():
        signup_guild_id = _get_signup_guild_id(signup)
        if signup_guild_id is None:
            # Cannot safely place this signup into a guild file.
            # Keep compatibility by skipping instead of corrupting another guild.
            continue

        grouped.setdefault(signup_guild_id, {})[str(message_id)] = signup

    for signup_guild_id, guild_signups in grouped.items():
        path = _get_signups_file(signup_guild_id)
        write_json(path, guild_signups, indent=2)


def signup_exists(data: dict[str, dict[str, Any]], message_id: int | str) -> bool:
    return str(message_id) in data


def find_message_signup(
    data: dict[str, dict[str, Any]],
    message_id: int | str,
) -> dict[str, Any] | None:
    return data.get(str(message_id))


def get_message_signup(
    data: dict[str, dict[str, Any]],
    message_id: int | str,
) -> dict[str, Any]:
    """
    Ensures a signup entry exists and returns it.

    Prefer `find_message_signup()` for read/update flows where a missing
    signup should fail instead of being silently created.
    """
    key = str(message_id)

    if key not in data:
        data[key] = {
            "guild_id": None,
            "channel_id": None,
            "title": "",
            "description": "",
            "leader": "",
            "start_ts": None,
            "users": {},
        }

    return data[key]


def init_message_signup(
    data: dict[str, dict[str, Any]],
    message_id: int | str,
    title: str,
    description: str,
    leader: str = "",
    start_ts: int | None = None,
    guild_id: int | str | None = None,
    channel_id: int | str | None = None,
) -> dict[str, Any]:
    key = str(message_id)

    data[key] = {
        "guild_id": str(guild_id) if guild_id is not None else None,
        "channel_id": str(channel_id) if channel_id is not None else None,
        "title": title,
        "description": description,
        "leader": leader,
        "start_ts": start_ts,
        "users": {},
    }

    if guild_id is not None:
        save_signups(data, guild_id)
    else:
        save_signups(data)

    return data[key]


def remove_message_signup(
    data: dict[str, dict[str, Any]],
    message_id: int | str,
    save: bool = True,
    guild_id: int | str | None = None,
) -> bool:
    key = str(message_id)

    if key not in data:
        return False

    removed_signup = data[key]
    removed_guild_id = guild_id or _get_signup_guild_id(removed_signup)

    del data[key]

    if save:
        if removed_guild_id is not None:
            save_signups(data, removed_guild_id)
        else:
            save_signups(data)

    return True


def remove_signup_by_message_id(
    message_id: int | str,
    guild_id: int | str | None = None,
) -> bool:
    data = load_signups(guild_id)
    removed = remove_message_signup(
        data,
        message_id,
        save=False,
        guild_id=guild_id,
    )

    if removed:
        save_signups(data, guild_id)

    return removed


def get_all_signup_message_ids(guild_id: int | str | None = None) -> list[int]:
    data = load_signups(guild_id)
    message_ids = []

    for key in data.keys():
        try:
            message_ids.append(int(key))
        except (TypeError, ValueError):
            continue

    return message_ids