import json
from pathlib import Path
from typing import Any


DATA_FILE = Path(__file__).resolve().parent / "signups.json"


def _ensure_data_dir() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_signups() -> dict[str, dict[str, Any]]:
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_signups(data: dict[str, dict[str, Any]]) -> None:
    _ensure_data_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
) -> dict[str, Any]:
    key = str(message_id)

    data[key] = {
        "title": title,
        "description": description,
        "leader": leader,
        "start_ts": start_ts,
        "users": {},
    }

    save_signups(data)
    return data[key]


def remove_message_signup(
    data: dict[str, dict[str, Any]],
    message_id: int | str,
    save: bool = True,
) -> bool:
    key = str(message_id)

    if key not in data:
        return False

    del data[key]

    if save:
        save_signups(data)

    return True


def remove_signup_by_message_id(message_id: int | str) -> bool:
    data = load_signups()
    removed = remove_message_signup(data, message_id, save=False)

    if removed:
        save_signups(data)

    return removed


def get_all_signup_message_ids() -> list[int]:
    data = load_signups()
    message_ids = []

    for key in data.keys():
        try:
            message_ids.append(int(key))
        except (TypeError, ValueError):
            continue

    return message_ids