from data.signup_store import load_signups


def get_signup_entry(raid_id: int, user_id: str) -> dict | None:
    data = load_signups()
    raid = data.get(str(raid_id), {})
    users = raid.get("users", {})
    return users.get(str(user_id))