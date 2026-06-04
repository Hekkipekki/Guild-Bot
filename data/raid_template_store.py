from typing import Any

from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)


DATA_FILE_NAME = "raid_templates.json"


def _get_templates_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, DATA_FILE_NAME)


def load_templates() -> dict[str, dict[str, Any]]:
    """
    Compatibility function.

    New storage:
        data/guilds/<guild_id>/raid_templates.json
        {
            "templates": [...]
        }

    This scans all guild folders and returns:
        {
            guild_id: {"templates": [...]}
        }
    """
    from data.guild_data import GUILDS_ROOT

    if not GUILDS_ROOT.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}

    for guild_dir in GUILDS_ROOT.iterdir():
        if not guild_dir.is_dir():
            continue

        path = guild_dir / DATA_FILE_NAME
        block = read_json(path, {})
        if not isinstance(block, dict):
            block = {}

        templates = block.get("templates", [])
        if not isinstance(templates, list):
            templates = []

        result[guild_dir.name] = {"templates": templates}

    return result


def save_templates(data: dict[str, dict[str, Any]]) -> None:
    """
    Compatibility function.

    Saves each guild block into its own raid_templates.json.
    """
    for guild_id, block in data.items():
        templates = []

        if isinstance(block, dict):
            value = block.get("templates", [])
            if isinstance(value, list):
                templates = value

        path = _get_templates_file(guild_id)
        write_json(path, {"templates": templates}, indent=2)


def get_guild_templates(guild_id: int | str) -> list[dict[str, Any]]:
    path = _get_templates_file(guild_id)
    block = read_json(path, {})

    if not isinstance(block, dict):
        return []

    templates = block.get("templates", [])
    return templates if isinstance(templates, list) else []


def save_guild_templates(guild_id: int | str, templates: list[dict[str, Any]]) -> None:
    path = _get_templates_file(guild_id)
    write_json(path, {"templates": templates}, indent=2)