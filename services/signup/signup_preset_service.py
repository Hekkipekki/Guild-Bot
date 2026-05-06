from services.guild.guild_settings_service import get_expected_players


def build_signup_payload(
    *,
    guild_id: int,
    title: str,
    description: str,
    leader: str,
    start_ts: int,
    channel_id: int,
    users: dict | None = None,
) -> dict:
    return {
        "title": title.strip(),
        "description": description.strip(),
        "leader": leader.strip(),
        "start_ts": start_ts,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "users": dict(users) if users else {},
        "expected_players": get_expected_players(guild_id),
        "missing_signup_reminders_sent": {
            "2880": False,
            "1440": False,
        },
        "signed_player_reminders_sent": {
            "60": False,
        },
        "missing_reminder_message_id": None,
        "signed_reminder_message_id": None,
    }