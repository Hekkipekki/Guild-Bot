from __future__ import annotations

from typing import Any
from data.guild_data import ensure_guild_files, get_guild_file, read_json, write_json

DATA_FILE_NAME = "scheduling.json"


def _path(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, DATA_FILE_NAME)


def load_scheduling(guild_id: int | str) -> dict[str, Any]:
    data = read_json(_path(guild_id), {})
    return data if isinstance(data, dict) else {}


def save_scheduling(guild_id: int | str, data: dict[str, Any]) -> None:
    write_json(_path(guild_id), data, indent=2)


def get_panel(data: dict[str, Any], panel_id: str) -> dict[str, Any] | None:
    return data.get("panels", {}).get(str(panel_id))