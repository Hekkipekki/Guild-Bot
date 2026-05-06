import config

from data.signup_store import load_signups, save_signups, find_message_signup


VALID_STATUSES = {"sign", "late", "bench", "tentative", "absence"}


def get_signup_data(raid_id: str) -> dict | None:
    data = load_signups()
    return find_message_signup(data, raid_id)


def get_players(raid_id: str) -> list[dict]:
    signup = get_signup_data(raid_id)
    if not signup:
        return []

    users = signup.get("users", {})
    players = []

    for user_id, entry in users.items():
        players.append(
            {
                "user_id": str(user_id),
                "name": entry.get("name") or entry.get("display_name") or "Unknown",
                "class": entry.get("class"),
                "spec": entry.get("spec"),
                "role": entry.get("role"),
                "status": entry.get("status"),
            }
        )

    players.sort(key=lambda p: (p.get("name") or "").lower())
    return players


def get_player_entry(raid_id: str, user_id: str) -> dict | None:
    signup = get_signup_data(raid_id)
    if not signup:
        return None

    users = signup.get("users", {})
    return users.get(str(user_id))


def get_player_class(raid_id: str, user_id: str) -> str | None:
    entry = get_player_entry(raid_id, user_id)
    if not entry:
        return None

    selected_class = entry.get("class")
    if not selected_class:
        return None

    return selected_class


def get_valid_specs_for_player(raid_id: str, user_id: str) -> list[dict]:
    selected_class = get_player_class(raid_id, user_id)
    if not selected_class:
        return []

    spec_map = config.CLASS_SPECS.get(selected_class, {})
    if not spec_map:
        return []

    return [
        {
            "spec": spec_name,
            "role": role_name,
        }
        for spec_name, role_name in spec_map.items()
    ]


def set_player_status(raid_id: str, user_id: str, new_status: str) -> bool:
    if new_status not in VALID_STATUSES:
        return False

    data = load_signups()
    raid = find_message_signup(data, raid_id)
    if not raid:
        return False

    users = raid.get("users", {})
    user_key = str(user_id)

    if user_key not in users:
        return False

    users[user_key]["status"] = new_status
    save_signups(data)
    return True


def remove_player_signup(raid_id: str, user_id: str) -> bool:
    data = load_signups()
    raid = find_message_signup(data, raid_id)
    if not raid:
        return False

    users = raid.get("users", {})
    user_key = str(user_id)

    if user_key not in users:
        return False

    del users[user_key]
    save_signups(data)
    return True


def change_player_spec(raid_id: str, user_id: str, new_spec: str) -> bool:
    """
    Changes spec/role for the CURRENT raid signup entry only.

    This does NOT update the saved character database.
    """
    data = load_signups()
    raid = find_message_signup(data, raid_id)
    if not raid:
        return False

    users = raid.get("users", {})
    user_key = str(user_id)
    entry = users.get(user_key)

    if not entry:
        return False

    selected_class = entry.get("class")
    if not selected_class:
        return False

    spec_map = config.CLASS_SPECS.get(selected_class, {})
    if not spec_map:
        return False

    if new_spec not in spec_map:
        return False

    entry["spec"] = new_spec
    entry["role"] = spec_map[new_spec]

    save_signups(data)
    return True
    
def toggle_recurring(raid_id: str) -> bool:
    data = load_signups()
    raid = find_message_signup(data, raid_id)

    if not raid:
        return False

    current = raid.get("is_recurring", False)
    raid["is_recurring"] = not current

    save_signups(data)
    return True


def set_recurring_interval(raid_id: str, days: int) -> bool:
    if days < 1:
        return False

    data = load_signups()
    raid = find_message_signup(data, raid_id)

    if not raid:
        return False

    raid["recurring_interval_days"] = days
    raid["is_recurring"] = True

    save_signups(data)
    return True


def get_recurring_settings(raid_id: str) -> dict:
    raid = get_signup_data(raid_id)
    if not raid:
        return {}

    return {
        "enabled": raid.get("is_recurring", False),
        "interval": raid.get("recurring_interval_days", None),
    }