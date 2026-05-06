import json
from pathlib import Path
from typing import Any


DATA_FILE = Path(__file__).resolve().parent / "raid_templates.json"


def _ensure_data_dir() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_templates() -> dict[str, dict[str, Any]]:
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_templates(data: dict[str, dict[str, Any]]) -> None:
    _ensure_data_dir()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_templates(guild_id: int | str) -> list[dict[str, Any]]:
    data = load_templates()
    guild_block = data.get(str(guild_id), {})

    templates = guild_block.get("templates", [])
    return templates if isinstance(templates, list) else []


def save_guild_templates(guild_id: int | str, templates: list[dict[str, Any]]) -> None:
    data = load_templates()
    key = str(guild_id)

    if key not in data or not isinstance(data[key], dict):
        data[key] = {}

    data[key]["templates"] = templates
    save_templates(data)