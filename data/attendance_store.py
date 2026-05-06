import json
from pathlib import Path
from typing import Any


DATA_FILE = Path(__file__).resolve().parent / "attendance.json"


def _ensure_data_dir() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_attendance() -> dict[str, dict[str, Any]]:
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_attendance(data: dict[str, dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_attendance_record(
    data: dict[str, dict[str, Any]],
    raid_id: int | str,
) -> dict[str, Any] | None:
    return data.get(str(raid_id))


def get_or_create_attendance_record(
    data: dict[str, dict[str, Any]],
    raid_id: int | str,
) -> dict[str, Any]:
    key = str(raid_id)

    if key not in data:
        data[key] = {
            "raid_id": key,
            "guild_id": None,
            "channel_id": None,
            "title": "",
            "description": "",
            "leader": "",
            "start_ts": None,
            "comp_message_id": None,
            "snapshot_source": "comp_post",
            "snapshot_version": 1,
            "finalized": False,
            "players": {},
            "history": [],
        }

    return data[key]