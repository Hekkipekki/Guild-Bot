import time

from data.signup_store import load_signups, save_signups, find_message_signup


NOTE_REQUIRED_STATUSES = {"late", "tentative", "absence"}


def _get_signup(data: dict, raid_id: int) -> dict | None:
    return find_message_signup(data, raid_id)


def _get_user_entry(signup: dict, user_id: str, create: bool = False) -> dict | None:
    users = signup.setdefault("users", {})

    if create:
        users.setdefault(user_id, {})

    return users.get(user_id)


def _validate_signup_entry_for_status(
    signup: dict | None,
    user_id: str,
    *,
    create: bool = True,
) -> tuple[dict | None, str | None]:
    if not signup:
        return None, "⚠ Raid signup not found."

    entry = _get_user_entry(signup, user_id, create=create)
    if entry is None:
        return None, "⚠ Signup entry not found."

    if entry.get("spec") in ("", "Unknown", None):
        return None, "⚠ Please select your class first from the dropdown."

    return entry, None


def _apply_status_and_note(
    entry: dict,
    *,
    status: str,
    note: str | None = None,
) -> None:
    entry["status"] = status
    entry["timestamp"] = time.time()
    entry.setdefault("name", "")

    if note is not None:
        entry["note"] = note.strip()
    elif status not in NOTE_REQUIRED_STATUSES:
        entry["note"] = ""
    else:
        entry.setdefault("note", "")


def get_signup_user(raid_id: int, user_id: str) -> dict | None:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return None

    return signup.get("users", {}).get(user_id)


def set_user_status(raid_id: int, user_id: str, status: str) -> tuple[bool, str | None]:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    entry, error_message = _validate_signup_entry_for_status(signup, user_id, create=True)
    if entry is None:
        return False, error_message

    _apply_status_and_note(entry, status=status)
    save_signups(data)
    return True, None


def set_user_status_with_note(
    raid_id: int,
    user_id: str,
    status: str,
    note: str,
) -> tuple[bool, str | None]:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    entry, error_message = _validate_signup_entry_for_status(signup, user_id, create=True)
    if entry is None:
        return False, error_message

    cleaned_note = note.strip()
    if status in NOTE_REQUIRED_STATUSES and not cleaned_note:
        return False, "⚠ A note is required for Tentative or Absence."

    _apply_status_and_note(entry, status=status, note=cleaned_note)
    save_signups(data)
    return True, None


def remove_user_signup(raid_id: int, user_id: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    users = signup.get("users", {})

    if user_id not in users:
        return False

    del users[user_id]
    save_signups(data)
    return True


def set_user_class(raid_id: int, user_id: str, selected_class: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    entry = _get_user_entry(signup, user_id, create=True)

    entry["class"] = selected_class
    entry["spec"] = ""
    entry["role"] = ""
    entry["timestamp"] = time.time()
    entry.setdefault("name", "")
    entry.setdefault("note", "")

    save_signups(data)
    return True


def set_user_spec(
    raid_id: int,
    user_id: str,
    selected_class: str,
    selected_spec: str,
    role: str,
    *,
    character_name: str | None = None,
    auto_sign: bool = False,
) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    entry = _get_user_entry(signup, user_id, create=True)

    entry["class"] = selected_class
    entry["spec"] = selected_spec
    entry["role"] = role
    entry["timestamp"] = time.time()

    if character_name is not None:
        entry["name"] = character_name
    else:
        entry.setdefault("name", f"{selected_spec} {selected_class}")

    entry.setdefault("note", "")

    if auto_sign:
        entry["status"] = "sign"
        entry["note"] = ""
    else:
        entry.pop("status", None)

    save_signups(data)
    return True


def update_user_name(raid_id: int, user_id: str, new_name: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    entry = _get_user_entry(signup, user_id, create=False)

    if not entry:
        return False

    entry["name"] = new_name.strip()
    entry["timestamp"] = time.time()
    entry.setdefault("note", "")

    save_signups(data)
    return True


def update_user_note(raid_id: int, user_id: str, note: str) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    entry = _get_user_entry(signup, user_id, create=False)

    if not entry:
        return False

    entry["note"] = note.strip()
    entry["timestamp"] = time.time()
    entry.setdefault("name", "")

    save_signups(data)
    return True


def update_user_spec(
    raid_id: int,
    user_id: str,
    selected_class: str,
    selected_spec: str,
    role: str,
) -> bool:
    data = load_signups()
    signup = _get_signup(data, raid_id)

    if not signup:
        return False

    entry = _get_user_entry(signup, user_id, create=False)

    if not entry:
        return False

    entry["class"] = selected_class
    entry["spec"] = selected_spec
    entry["role"] = role
    entry["timestamp"] = time.time()
    entry.setdefault("note", "")
    entry.setdefault("name", f"{selected_spec} {selected_class}")

    save_signups(data)
    return True