from typing import Any

from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)
from data.guild_settings_migrations import (
    CURRENT_GUILD_SETTINGS_VERSION,
    migrate_guild_settings,
)


LEGACY_DATA_FILE_NAME = "guild_settings.json"


DEFAULT_GUILD_SETTINGS = {
    "config_version": CURRENT_GUILD_SETTINGS_VERSION,
    "guild_name": "",
    "raid_control_user_ids": [],
    "expected_players": [],
    "default_leader": "",
    "default_description": "",
    "signup_theme": "classic",
    "weakauras_channel_id": None,
    "weakauras_message_id": None,
    "hidden_weakaura_items": [],
    "scheduling_channel_id": None,
    "scheduling_message_id": None,
    "raid_weekdays": [2, 6],
    "warcraftlogs_guild_id": None,
    "warcraftlogs_region": "eu",
    "warcraftlogs_raid_size": 10,
}


def _build_default_settings() -> dict[str, Any]:
    defaults = dict(DEFAULT_GUILD_SETTINGS)
    defaults["raid_control_user_ids"] = []
    defaults["expected_players"] = []
    defaults["hidden_weakaura_items"] = []
    defaults["raid_weekdays"] = [2, 6]
    return defaults


def _normalize_guild_block(block: dict[str, Any]) -> dict[str, Any]:
    normalized = _build_default_settings()
    normalized.update(block)
    normalized["config_version"] = CURRENT_GUILD_SETTINGS_VERSION

    if normalized.get("signup_theme") not in ("classic", "compact", "split_by_class"):
        normalized["signup_theme"] = "classic"

    raid_weekdays = normalized.get("raid_weekdays", [2, 6])
    if not isinstance(raid_weekdays, list):
        raid_weekdays = [2, 6]

    valid_weekdays: list[int] = []
    for value in raid_weekdays:
        try:
            weekday = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= weekday <= 6 and weekday not in valid_weekdays:
            valid_weekdays.append(weekday)

    normalized["raid_weekdays"] = sorted(valid_weekdays) or [2, 6]

    hidden_items = normalized.get("hidden_weakaura_items", [])
    if not isinstance(hidden_items, list):
        hidden_items = []
    normalized["hidden_weakaura_items"] = sorted(
        {str(item) for item in hidden_items if item}
    )

    guild_id = normalized.get("warcraftlogs_guild_id")
    try:
        normalized["warcraftlogs_guild_id"] = int(guild_id) if guild_id else None
    except (TypeError, ValueError):
        normalized["warcraftlogs_guild_id"] = None

    region = str(normalized.get("warcraftlogs_region", "eu") or "eu").lower()
    normalized["warcraftlogs_region"] = region if region in {"us", "eu", "kr", "tw", "cn"} else "eu"

    try:
        raid_size = int(normalized.get("warcraftlogs_raid_size", 10))
    except (TypeError, ValueError):
        raid_size = 10
    normalized["warcraftlogs_raid_size"] = raid_size if raid_size in {10, 25} else 10

    return normalized


def _prepare_guild_block(block: dict[str, Any] | Any) -> dict[str, Any]:
    migrated = migrate_guild_settings(block)
    return _normalize_guild_block(migrated)


def _get_guild_settings_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, LEGACY_DATA_FILE_NAME)


def load_guild_settings() -> dict[str, dict[str, Any]]:
    """Load all per-guild settings, migrating old schemas in memory."""
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
        result[guild_id] = _prepare_guild_block(block)
    return result


def save_guild_settings(data: dict[str, dict[str, Any]]) -> None:
    """Save each guild block into its guild-specific settings file."""
    for guild_id, block in data.items():
        path = _get_guild_settings_file(guild_id)
        write_json(path, _prepare_guild_block(block), indent=2)


def get_guild_settings(guild_id: int | str) -> dict[str, Any]:
    path = _get_guild_settings_file(guild_id)
    block = read_json(path, {})
    return _prepare_guild_block(block)


def ensure_guild_settings(
    guild_id: int | str,
    guild_name: str | None = None,
) -> dict[str, Any]:
    path = _get_guild_settings_file(guild_id)
    raw = read_json(path, {})
    current = _prepare_guild_block(raw)

    if guild_name is not None and str(guild_name).strip():
        clean_name = str(guild_name).strip()
        if current.get("guild_name") != clean_name:
            current["guild_name"] = clean_name

    if current != raw:
        write_json(path, current, indent=2)

    return current


def update_guild_settings(
    guild_id: int | str,
    updates: dict[str, Any],
    guild_name: str | None = None,
) -> dict[str, Any]:
    path = _get_guild_settings_file(guild_id)
    current = _prepare_guild_block(read_json(path, {}))

    current.update(updates)
    current = _prepare_guild_block(current)

    if guild_name is not None and str(guild_name).strip():
        current["guild_name"] = str(guild_name).strip()

    write_json(path, current, indent=2)
    return current
