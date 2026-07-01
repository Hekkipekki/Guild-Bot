from typing import Any

from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)


LEGACY_DATA_FILE_NAME = "guild_settings.json"


DEFAULT_GUILD_SETTINGS = {
    "guild_name": "",
    "raid_control_user_ids": [],
    "expected_players": [],
    "default_leader": "",
    "default_description": "",
    "signup_theme": "classic",
    "weakauras_channel_id": None,
    "weakauras_message_id": None,
    "scheduling_channel_id": None,
    "scheduling_message_id": None,
}


def _build_default_settings() -> dict[str, Any]:
    return dict(DEFAULT_GUILD_SETTINGS)


def _normalize_guild_block(block: dict[str, Any] | Any) -> dict[str, Any]:
    normalized = _build_default_settings()

    if isinstance(block, dict):
        normalized.update(block)

    if normalized.get("signup_theme") not in ("classic", "compact", "split_by_class"):
        normalized["signup_theme"] = "classic"

    return normalized


def _get_guild_settings_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, LEGACY_DATA_FILE_NAME)


def load_guild_settings() -> dict[str, dict[str, Any]]:
    """
    Compatibility function.

    Old system:
        data/guild_settings.json
        {
            "guild_id": { settings }
        }

    New system:
        data/guilds/<guild_id>/guild_settings.json
        { settings }

    This returns all guild settings by scanning data/guilds/.
    """
    from data.guild_data import GUILDS_ROOT

    if not GUILDS_ROOT.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}

    for guild_dir in GUILDS_ROOT.iterdir():
        if not guild_dir.is_dir():
            continue

        guild_id = guild_dir.name
        path = guild_dir / LEGACY_DATA_FILE_NAME
        block = read_json(path, {})
        result[guild_id] = _normalize_guild_block(block)

    return result


def save_guild_settings(data: dict[str, dict[str, Any]]) -> None:
    """
    Compatibility function.

    Saves each guild block into its own guild-specific file.
    """
    for guild_id, block in data.items():
        ensure_guild_files(guild_id)
        path = _get_guild_settings_file(guild_id)
        write_json(path, _normalize_guild_block(block), indent=2)


def get_guild_settings(guild_id: int | str) -> dict[str, Any]:
    path = _get_guild_settings_file(guild_id)
    block = read_json(path, {})
    return _normalize_guild_block(block)


def ensure_guild_settings(
    guild_id: int | str,
    guild_name: str | None = None,
) -> dict[str, Any]:
    ensure_guild_files(guild_id)

    path = _get_guild_settings_file(guild_id)
    current = _normalize_guild_block(read_json(path, {}))

    changed = False

    if guild_name is not None and str(guild_name).strip():
        clean_name = str(guild_name).strip()
        if current.get("guild_name") != clean_name:
            current["guild_name"] = clean_name
            changed = True

    # Always save once so missing/default keys are written.
    if changed or not path.exists():
        write_json(path, current, indent=2)
    else:
        # Also write back normalized data if keys were missing.
        write_json(path, current, indent=2)

    return current


def update_guild_settings(
    guild_id: int | str,
    updates: dict[str, Any],
    guild_name: str | None = None,
) -> dict[str, Any]:
    ensure_guild_files(guild_id)

    path = _get_guild_settings_file(guild_id)
    current = _normalize_guild_block(read_json(path, {}))

    current.update(updates)
    current = _normalize_guild_block(current)

    if guild_name is not None and str(guild_name).strip():
        current["guild_name"] = str(guild_name).strip()

    write_json(path, current, indent=2)
    return current