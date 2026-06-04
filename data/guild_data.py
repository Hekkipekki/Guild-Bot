import json
from pathlib import Path
from typing import Any


DATA_ROOT = Path(__file__).resolve().parent
GUILDS_ROOT = DATA_ROOT / "guilds"


DEFAULT_GUILD_FILES = {
    "guild_settings.json": {},
    "signups.json": {},
    "attendance.json": {},
    "characters.json": {},
    "raid_templates.json": {},
}


def get_guild_dir(guild_id: int | str) -> Path:
    return GUILDS_ROOT / str(guild_id)


def get_guild_file(guild_id: int | str, filename: str) -> Path:
    return get_guild_dir(guild_id) / filename


def ensure_guild_files(guild_id: int | str) -> None:
    guild_dir = get_guild_dir(guild_id)
    guild_dir.mkdir(parents=True, exist_ok=True)

    for filename, default_data in DEFAULT_GUILD_FILES.items():
        path = guild_dir / filename
        if not path.exists():
            write_json(path, default_data)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if data is not None else default
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)