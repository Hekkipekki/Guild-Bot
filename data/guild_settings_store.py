import json
from pathlib import Path
from typing import Any


DATA_FILE = Path(__file__).resolve().parent / "guild_settings.json"

DEFAULT_GUILD_SETTINGS = {
    "guild_name": "",
    "raid_control_user_ids": [],
    "expected_players": [],
    "default_leader": "",
    "default_description": "",
    "weakauras_channel_id": None,
    "weakauras_message_id": None,
}


def _ensure_data_dir() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def _build_default_settings() -> dict[str, Any]:
    return dict(DEFAULT_GUILD_SETTINGS)


def _normalize_guild_block(block: dict[str, Any] | Any) -> dict[str, Any]:
    """
    Ensures older guild blocks are upgraded with any newly added keys.
    """
    normalized = _build_default_settings()

    if isinstance(block, dict):
        normalized.update(block)

    return normalized


def load_guild_settings() -> dict[str, dict[str, Any]]:
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}

            normalized_data: dict[str, dict[str, Any]] = {}
            changed = False

            for guild_id, block in data.items():
                normalized_block = _normalize_guild_block(block)
                normalized_data[str(guild_id)] = normalized_block

                if not isinstance(block, dict) or block != normalized_block:
                    changed = True

            if changed:
                save_guild_settings(normalized_data)

            return normalized_data

    except (json.JSONDecodeError, OSError):
        return {}


def save_guild_settings(data: dict[str, dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_settings(guild_id: int | str) -> dict[str, Any]:
    data = load_guild_settings()
    block = data.get(str(guild_id), {})
    return _normalize_guild_block(block)


def ensure_guild_settings(
    guild_id: int | str,
    guild_name: str | None = None,
) -> dict[str, Any]:
    data = load_guild_settings()
    key = str(guild_id)
    changed = False

    if key not in data:
        data[key] = _build_default_settings()
        changed = True
    else:
        normalized = _normalize_guild_block(data[key])
        if data[key] != normalized:
            data[key] = normalized
            changed = True

    if guild_name is not None and str(guild_name).strip():
        clean_name = str(guild_name).strip()
        if data[key].get("guild_name") != clean_name:
            data[key]["guild_name"] = clean_name
            changed = True

    if changed:
        save_guild_settings(data)

    return data[key]


def update_guild_settings(
    guild_id: int | str,
    updates: dict[str, Any],
    guild_name: str | None = None,
) -> dict[str, Any]:
    data = load_guild_settings()
    key = str(guild_id)

    if key not in data:
        data[key] = _build_default_settings()
    else:
        data[key] = _normalize_guild_block(data[key])

    data[key].update(updates)

    if guild_name is not None and str(guild_name).strip():
        data[key]["guild_name"] = str(guild_name).strip()

    save_guild_settings(data)
    return data[key]