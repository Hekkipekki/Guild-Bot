from typing import Any

from data.guild_data import (
    ensure_guild_files,
    get_guild_file,
    read_json,
    write_json,
)


DATA_FILE_NAME = "attendance.json"


def _get_attendance_file(guild_id: int | str):
    ensure_guild_files(guild_id)
    return get_guild_file(guild_id, DATA_FILE_NAME)


def _normalize_attendance_data(data: dict | object) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}

    for raid_id, record in data.items():
        if isinstance(record, dict):
            normalized[str(raid_id)] = record

    return normalized


def _get_record_guild_id(record: dict[str, Any]) -> str | None:
    guild_id = record.get("guild_id")

    if guild_id in (None, "", 0):
        return None

    return str(guild_id)


def load_attendance(guild_id: int | str | None = None) -> dict[str, dict[str, Any]]:
    """
    Preferred:
        load_attendance(guild_id)

    Compatibility:
        load_attendance()
        scans all guild-specific attendance files and merges them into one dict.
    """
    if guild_id is not None:
        path = _get_attendance_file(guild_id)
        return _normalize_attendance_data(read_json(path, {}))

    from data.guild_data import GUILDS_ROOT

    if not GUILDS_ROOT.exists():
        return {}

    merged: dict[str, dict[str, Any]] = {}

    for guild_dir in GUILDS_ROOT.iterdir():
        if not guild_dir.is_dir():
            continue

        path = guild_dir / DATA_FILE_NAME
        guild_records = _normalize_attendance_data(read_json(path, {}))

        for raid_id, record in guild_records.items():
            if "guild_id" not in record or record.get("guild_id") in (None, "", 0):
                record["guild_id"] = guild_dir.name

            merged[str(raid_id)] = record

    return merged


def save_attendance(
    data: dict[str, dict[str, Any]],
    guild_id: int | str | None = None,
) -> None:
    """
    Preferred:
        save_attendance(data, guild_id)

    Compatibility:
        save_attendance(data)
        splits attendance records into guild-specific files using record["guild_id"].
    """
    normalized = _normalize_attendance_data(data)

    if guild_id is not None:
        path = _get_attendance_file(guild_id)

        for record in normalized.values():
            if "guild_id" not in record or record.get("guild_id") in (None, "", 0):
                record["guild_id"] = str(guild_id)

        write_json(path, normalized, indent=2)
        return

    grouped: dict[str, dict[str, dict[str, Any]]] = {}

    for raid_id, record in normalized.items():
        record_guild_id = _get_record_guild_id(record)
        if record_guild_id is None:
            continue

        grouped.setdefault(record_guild_id, {})[str(raid_id)] = record

    for record_guild_id, guild_records in grouped.items():
        path = _get_attendance_file(record_guild_id)
        write_json(path, guild_records, indent=2)


def find_attendance_record(
    data: dict[str, dict[str, Any]],
    raid_id: int | str,
) -> dict[str, Any] | None:
    return data.get(str(raid_id))


def get_or_create_attendance_record(
    data: dict[str, dict[str, Any]],
    raid_id: int | str,
    guild_id: int | str | None = None,
) -> dict[str, Any]:
    key = str(raid_id)

    if key not in data:
        data[key] = {
            "raid_id": key,
            "guild_id": str(guild_id) if guild_id is not None else None,
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

    elif guild_id is not None and data[key].get("guild_id") in (None, "", 0):
        data[key]["guild_id"] = str(guild_id)

    return data[key]