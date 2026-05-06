from services.guild.guild_settings_service import (
    get_default_leader,
    get_default_description,
)
from services.signup.signup_preset_service import build_signup_payload
from services.signup.signup_template_service import build_fake_users
from utils.time_helpers import next_weekday


def _get_defaults(guild_id: int) -> tuple[str, str]:
    leader = get_default_leader(guild_id) or "Raid Leader"
    description = get_default_description(guild_id) or "Raid signup"
    return leader, description


def build_wednesday_signup(guild_id: int, channel_id: int) -> dict:
    leader, description = _get_defaults(guild_id)
    return build_signup_payload(
        guild_id=guild_id,
        title="HC Progression - Wednesday",
        description=description,
        leader=leader,
        start_ts=next_weekday(2, 19, 30),
        channel_id=channel_id,
    )


def build_sunday_signup(guild_id: int, channel_id: int) -> dict:
    leader, description = _get_defaults(guild_id)
    return build_signup_payload(
        guild_id=guild_id,
        title="HC Progression - Sunday",
        description=description,
        leader=leader,
        start_ts=next_weekday(6, 19, 30),
        channel_id=channel_id,
    )


def build_template_signup(guild_id: int, channel_id: int) -> dict:
    leader, description = _get_defaults(guild_id)
    return build_signup_payload(
        guild_id=guild_id,
        title="HC Progression - Template Preview",
        description="Visual preview with fake raid roster",
        leader=leader,
        start_ts=next_weekday(2, 19, 30),
        channel_id=channel_id,
        users=build_fake_users(),
    )