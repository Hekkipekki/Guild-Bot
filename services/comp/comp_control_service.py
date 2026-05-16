from __future__ import annotations

from copy import deepcopy
from typing import Any

import discord

from data.attendance_store import load_attendance, save_attendance
from data.signup_store import find_message_signup, load_signups, save_signups
from services.comp.comp_message_service import post_comp_message


ACTION_LABELS = {
    "sign": "Sign / Attending",
    "bench": "Bench",
    "late": "Late",
    "tentative": "Tentative",
    "absence": "Absence",
}


STATUS_LIST_KEYS = {
    "bench": "bench_players",
    "late": "late_players",
    "tentative": "tentative_players",
    "absence": "absence_players",
}


PLAYER_LIST_KEYS = [
    "group_1",
    "group_2",
    "selected_players",
    "signed_players",
    "bench_players",
    "late_players",
    "tentative_players",
    "absence_players",
]


def _entry_name(user_id: str, entry: dict) -> str:
    return (
        (entry.get("name") or "").strip()
        or (entry.get("display_name") or "").strip()
        or str(user_id)
    )


def _as_pair_list(value: Any) -> list[tuple[str, dict]]:
    result: list[tuple[str, dict]] = []

    if not isinstance(value, list):
        return result

    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue

        user_id, entry = item
        if not isinstance(entry, dict):
            continue

        result.append((str(user_id), dict(entry)))

    return result


def _replace_pair_list(comp_data: dict, key: str, pairs: list[tuple[str, dict]]) -> None:
    comp_data[key] = [[str(user_id), entry] for user_id, entry in pairs]


def _remove_user_from_comp_lists(comp_data: dict, user_id: str) -> None:
    user_id = str(user_id)

    for key in PLAYER_LIST_KEYS:
        pairs = _as_pair_list(comp_data.get(key, []))
        pairs = [(uid, entry) for uid, entry in pairs if str(uid) != user_id]
        _replace_pair_list(comp_data, key, pairs)

    mentions = comp_data.get("mentions", [])
    if isinstance(mentions, list):
        comp_data["mentions"] = [
            mention for mention in mentions if mention != f"<@{user_id}>"
        ]

    status_buckets = comp_data.get("status_buckets", {})
    if isinstance(status_buckets, dict):
        for key, value in list(status_buckets.items()):
            pairs = _as_pair_list(value)
            pairs = [(uid, entry) for uid, entry in pairs if str(uid) != user_id]
            status_buckets[key] = [[uid, entry] for uid, entry in pairs]


def _add_to_status_bucket(comp_data: dict, user_id: str, entry: dict, status: str) -> None:
    status_buckets = comp_data.setdefault("status_buckets", {})
    bucket = _as_pair_list(status_buckets.get(status, []))
    bucket.append((user_id, entry))
    status_buckets[status] = [[uid, item] for uid, item in bucket]


def _add_signed_player(comp_data: dict, user_id: str, entry: dict) -> None:
    signed_players = _as_pair_list(comp_data.get("signed_players", []))
    signed_players.append((user_id, entry))
    _replace_pair_list(comp_data, "signed_players", signed_players)

    selected_players = _as_pair_list(comp_data.get("selected_players", []))
    selected_players.append((user_id, entry))
    _replace_pair_list(comp_data, "selected_players", selected_players)

    group_1 = _as_pair_list(comp_data.get("group_1", []))
    group_2 = _as_pair_list(comp_data.get("group_2", []))

    if len(group_1) < 5:
        group_1.append((user_id, entry))
    elif len(group_2) < 5:
        group_2.append((user_id, entry))
    else:
        bench_players = _as_pair_list(comp_data.get("bench_players", []))
        bench_entry = dict(entry)
        bench_entry["status"] = "bench"
        bench_players.append((user_id, bench_entry))
        _replace_pair_list(comp_data, "bench_players", bench_players)

    _replace_pair_list(comp_data, "group_1", group_1)
    _replace_pair_list(comp_data, "group_2", group_2)

    mentions = comp_data.setdefault("mentions", [])
    mention = f"<@{user_id}>"
    if mention not in mentions:
        mentions.append(mention)

    _add_to_status_bucket(comp_data, user_id, entry, "sign")


def _add_status_player(comp_data: dict, user_id: str, entry: dict, status: str) -> None:
    list_key = STATUS_LIST_KEYS.get(status)
    if not list_key:
        return

    players = _as_pair_list(comp_data.get(list_key, []))
    players.append((user_id, entry))
    _replace_pair_list(comp_data, list_key, players)
    _add_to_status_bucket(comp_data, user_id, entry, status)


def get_comp_control_players(raid_id: int | str) -> list[dict]:
    data = load_signups()
    signup = find_message_signup(data, raid_id)
    if not signup:
        return []

    players_by_id: dict[str, dict] = {}

    for user_id, entry in signup.get("users", {}).items():
        if isinstance(entry, dict):
            players_by_id[str(user_id)] = {
                "user_id": str(user_id),
                "name": _entry_name(str(user_id), entry),
                "class": entry.get("class"),
                "spec": entry.get("spec"),
                "role": entry.get("role"),
                "status": entry.get("status") or "unknown",
            }

    comp_data = signup.get("last_comp_data") or {}
    for key in PLAYER_LIST_KEYS:
        for user_id, entry in _as_pair_list(comp_data.get(key, [])):
            players_by_id.setdefault(
                str(user_id),
                {
                    "user_id": str(user_id),
                    "name": _entry_name(str(user_id), entry),
                    "class": entry.get("class"),
                    "spec": entry.get("spec"),
                    "role": entry.get("role"),
                    "status": entry.get("status") or "unknown",
                },
            )

    players = list(players_by_id.values())
    players.sort(key=lambda item: (item.get("name") or "").lower())
    return players


async def apply_comp_player_action(
    *,
    channel,
    raid_id: int | str,
    user_id: int | str,
    action: str,
) -> tuple[bool, str]:
    if action not in ACTION_LABELS:
        return False, "Invalid comp action."

    data = load_signups()
    signup = find_message_signup(data, raid_id)

    if not signup:
        return False, "Raid signup not found."

    comp_data = signup.get("last_comp_data")
    if not comp_data:
        return False, "No posted comp found for this raid."

    user_key = str(user_id)
    users = signup.setdefault("users", {})
    entry = users.get(user_key)

    if not entry:
        entry = None
        for key in PLAYER_LIST_KEYS:
            for uid, item in _as_pair_list(comp_data.get(key, [])):
                if str(uid) == user_key:
                    entry = dict(item)
                    break
            if entry:
                break

    if not entry:
        return False, "Player not found in signup or comp."

    entry = dict(entry)
    entry["status"] = action
    users[user_key] = entry

    updated_comp_data = deepcopy(comp_data)
    _remove_user_from_comp_lists(updated_comp_data, user_key)

    if action == "sign":
        _add_signed_player(updated_comp_data, user_key, entry)
    else:
        _add_status_player(updated_comp_data, user_key, entry, action)

    updated_comp_data["raid_id"] = str(raid_id)
    signup["last_comp_data"] = updated_comp_data
    save_signups(data)

    ok, message = await post_comp_message(channel, updated_comp_data)
    if not ok:
        return False, message

    return True, f"Comp updated: {_entry_name(user_key, entry)} → {ACTION_LABELS[action]}"


async def cancel_posted_comp(
    *,
    channel,
    raid_id: int | str,
) -> tuple[bool, str]:
    raid_key = str(raid_id)

    data = load_signups()
    signup = find_message_signup(data, raid_key)

    if not signup:
        return False, "Raid signup not found."

    comp_message_id = signup.get("comp_message_id")

    if comp_message_id:
        try:
            msg = await channel.fetch_message(int(comp_message_id))
            await msg.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            return False, "Bot does not have permission to delete the comp message."
        except discord.HTTPException as e:
            return False, f"Could not delete comp message: {e}"

    signup["comp_message_id"] = None
    signup.pop("last_comp_data", None)
    signup["attendance_snapshot_created"] = False
    signup.pop("attendance_record_id", None)

    save_signups(data)

    attendance = load_attendance()
    if raid_key in attendance:
        del attendance[raid_key]
        save_attendance(attendance)

    return True, "Comp cancelled. Attendance snapshot removed."