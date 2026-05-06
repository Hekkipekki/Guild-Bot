from logic.unassigned import get_unassigned_players


MISSING_SIGNUP_THRESHOLDS = {
    "2880": "48 hours",
    "1440": "24 hours",
}

SIGNED_PLAYER_THRESHOLDS = {
    "60": "1 hour",
}


def should_send_threshold(minutes_left: int, threshold: int, window: int = 300) -> bool:
    """
    Send reminder if current time is inside the allowed reminder window.

    Example with window=300 (5 hours):
    - threshold=2880 -> sends when minutes_left is between 2581 and 2880
    - threshold=1440 -> sends when minutes_left is between 1141 and 1440
    - threshold=60   -> sends when minutes_left is between 1 and 60
    """
    return threshold - window < minutes_left <= threshold


def ensure_missing_signup_reminder_state(signup: dict) -> dict:
    return signup.setdefault(
        "missing_signup_reminders_sent",
        {
            "2880": False,
            "1440": False,
        },
    )


def ensure_signed_player_reminder_state(signup: dict) -> dict:
    return signup.setdefault(
        "signed_player_reminders_sent",
        {
            "60": False,
        },
    )


def get_signup_title(signup: dict) -> str:
    return signup.get("title", "Raid")


def get_signed_players(signup: dict) -> list[str]:
    users = signup.get("users", {})
    return [
        user_id
        for user_id, info in users.items()
        if info.get("status") == "sign"
    ]


def get_missing_players(signup: dict) -> list[str]:
    return get_unassigned_players(signup)


def find_missing_signup_threshold_to_send(
    minutes_left: int,
    reminders_sent: dict,
) -> tuple[str, str] | None:
    for threshold_str, label in sorted(
        MISSING_SIGNUP_THRESHOLDS.items(),
        key=lambda item: int(item[0]),
        reverse=True,
    ):
        threshold = int(threshold_str)

        if (
            not reminders_sent.get(threshold_str, False)
            and should_send_threshold(minutes_left, threshold, window=300)
        ):
            return threshold_str, label

    return None


def find_signed_player_threshold_to_send(
    minutes_left: int,
    reminders_sent: dict,
) -> tuple[str, str] | None:
    for threshold_str, label in sorted(
        SIGNED_PLAYER_THRESHOLDS.items(),
        key=lambda item: int(item[0]),
        reverse=True,
    ):
        threshold = int(threshold_str)

        if (
            not reminders_sent.get(threshold_str, False)
            and should_send_threshold(minutes_left, threshold, window=300)
        ):
            return threshold_str, label

    return None


def build_missing_signup_reminder_message(
    *,
    title: str,
    label: str,
    start_ts: int,
    user_ids: list[str],
) -> str:
    mentions = "\n".join(f"<@{user_id}>" for user_id in user_ids)

    return (
        f"⏰ **Raid reminder — {label} remaining**\n"
        f"**{title}** starts <t:{start_ts}:R>\n\n"
        f"Still missing signup from:\n{mentions}"
    )


def build_signed_player_reminder_message(
    *,
    title: str,
    label: str,
    start_ts: int,
    user_ids: list[str],
) -> str:
    mentions = " ".join(f"<@{user_id}>" for user_id in user_ids)

    return (
        f"⏰ **Raid starts <t:{start_ts}:R>**\n"
        f"{mentions}\n\n"
        f"**{title}** starts <t:{start_ts}:R> (<t:{start_ts}:t>)\n"
        f"Don't forget to check your bonus rolls, consumables, and your gear before raid starts — "
        f"we don't want to lose any time."
    )