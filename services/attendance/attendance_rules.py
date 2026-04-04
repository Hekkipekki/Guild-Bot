from __future__ import annotations

from typing import Any


VALID_ATTENDANCE_STATUSES = {
    "attending",
    "benched",
    "late",
    "tentative",
    "absent",
    "not_selected",
    "no_sign",
}

ATTENDANCE_STATUS_LABELS = {
    "attending": "Attending",
    "benched": "Benched",
    "late": "Late",
    "tentative": "Tentative",
    "absent": "Absent",
    "not_selected": "No Sign",
    "no_sign": "No Sign",
    "unknown": "Unknown",
}

ATTENDANCE_STATUS_ORDER = [
    "attending",
    "benched",
    "late",
    "tentative",
    "absent",
    "not_selected",
    "no_sign",
    "unknown",
]

_PRESENT_STATUSES = {"attending", "benched", "late"}
_MISSED_STATUSES = {"absent", "tentative", "not_selected", "no_sign"}


def normalize_attendance_status(
    status: str | None,
    *,
    default: str = "unknown",
) -> str:
    value = (status or "").strip().lower()
    if value in VALID_ATTENDANCE_STATUSES:
        return value
    return default


def is_valid_attendance_status(status: str | None) -> bool:
    return normalize_attendance_status(status, default="") in VALID_ATTENDANCE_STATUSES


def get_attendance_status_label(status: str | None) -> str:
    normalized = normalize_attendance_status(status)
    return ATTENDANCE_STATUS_LABELS.get(normalized, "Unknown")


def get_attendance_status_sort_index(status: str | None) -> int:
    normalized = normalize_attendance_status(status)
    try:
        return ATTENDANCE_STATUS_ORDER.index(normalized)
    except ValueError:
        return len(ATTENDANCE_STATUS_ORDER)


def is_present_attendance_status(status: str | None) -> bool:
    return normalize_attendance_status(status) in _PRESENT_STATUSES


def is_missed_attendance_status(status: str | None) -> bool:
    return normalize_attendance_status(status) in _MISSED_STATUSES


def copy_player_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": entry.get("display_name", ""),
        "name": entry.get("name", ""),
        "class": entry.get("class", ""),
        "spec": entry.get("spec", ""),
        "role": entry.get("role", ""),
        "note": entry.get("note", ""),
    }


def normalize_player_map(players: list[tuple[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}

    for user_id, entry in players:
        normalized[str(user_id)] = dict(entry)

    return normalized


def build_manual_placeholder_player(user_id: int | str) -> dict[str, Any]:
    key = str(user_id)
    return {
        "display_name": f"User {key}",
        "name": "",
        "class": "",
        "spec": "",
        "role": "",
        "note": "",
        "user_id": key,
        "signup_status": "no_sign",
        "auto_status": "no_sign",
        "attendance_status": "no_sign",
        "status_source": "manual",
        "manual_override": True,
        "edited_by": None,
        "edited_at": None,
    }


def derive_auto_snapshot_players(comp_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Build automatic attendance state from comp snapshot.

    Priority:
    1. group_1 + group_2 -> attending
    2. bench_players -> benched
    3. late_players -> late
    4. tentative_players -> tentative
    5. absence_players -> absent
    6. signed but not selected/bench/etc -> not_selected
    """
    players: dict[str, dict[str, Any]] = {}

    group_1 = normalize_player_map(comp_data.get("group_1", []))
    group_2 = normalize_player_map(comp_data.get("group_2", []))
    bench_players = normalize_player_map(comp_data.get("bench_players", []))
    late_players = normalize_player_map(comp_data.get("late_players", []))
    tentative_players = normalize_player_map(comp_data.get("tentative_players", []))
    absence_players = normalize_player_map(comp_data.get("absence_players", []))
    signed_players = normalize_player_map(comp_data.get("signed_players", []))

    def apply_bucket(
        source: dict[str, dict[str, Any]],
        attendance_status: str,
        signup_status: str,
    ) -> None:
        for user_id, entry in source.items():
            players[user_id] = {
                **copy_player_entry(entry),
                "user_id": user_id,
                "signup_status": signup_status,
                "auto_status": attendance_status,
                "attendance_status": attendance_status,
                "status_source": "auto",
                "manual_override": False,
                "edited_by": None,
                "edited_at": None,
            }

    apply_bucket(group_1, "attending", "sign")
    apply_bucket(group_2, "attending", "sign")
    apply_bucket(bench_players, "benched", "bench")
    apply_bucket(late_players, "late", "late")
    apply_bucket(tentative_players, "tentative", "tentative")
    apply_bucket(absence_players, "absent", "absence")

    for user_id, entry in signed_players.items():
        if user_id in players:
            continue

        players[user_id] = {
            **copy_player_entry(entry),
            "user_id": user_id,
            "signup_status": "sign",
            "auto_status": "not_selected",
            "attendance_status": "not_selected",
            "status_source": "auto",
            "manual_override": False,
            "edited_by": None,
            "edited_at": None,
        }

    return players