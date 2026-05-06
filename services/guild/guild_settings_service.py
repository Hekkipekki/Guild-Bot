from data.guild_settings_store import (
    get_guild_settings,
    update_guild_settings,
    ensure_guild_settings,
)


def _get_list_setting(guild_id: int, key: str) -> list[str]:
    settings = ensure_guild_settings(guild_id)
    return [str(x) for x in settings.get(key, [])]


def _add_list_value(guild_id: int, key: str, value: int | str) -> bool:
    current = _get_list_setting(guild_id, key)
    value_str = str(value)

    if value_str in current:
        return False

    current.append(value_str)
    update_guild_settings(guild_id, {key: current})
    return True


def _remove_list_value(guild_id: int, key: str, value: int | str) -> bool:
    current = _get_list_setting(guild_id, key)
    value_str = str(value)

    if value_str not in current:
        return False

    current.remove(value_str)
    update_guild_settings(guild_id, {key: current})
    return True


def get_guild_name(guild_id: int) -> str:
    settings = ensure_guild_settings(guild_id)
    return str(settings.get("guild_name", "") or "")


def set_guild_name(guild_id: int, guild_name: str) -> None:
    update_guild_settings(guild_id, {}, guild_name=guild_name.strip())


def sync_guild_identity(guild_id: int, guild_name: str) -> None:
    ensure_guild_settings(guild_id, guild_name=guild_name.strip())


def get_raid_control_users(guild_id: int) -> list[str]:
    return _get_list_setting(guild_id, "raid_control_user_ids")


def add_raid_control_user(guild_id: int, user_id: int) -> bool:
    return _add_list_value(guild_id, "raid_control_user_ids", user_id)


def remove_raid_control_user(guild_id: int, user_id: int) -> bool:
    return _remove_list_value(guild_id, "raid_control_user_ids", user_id)


def get_expected_players(guild_id: int) -> list[str]:
    return _get_list_setting(guild_id, "expected_players")


def add_expected_player(guild_id: int, user_id: int) -> bool:
    return _add_list_value(guild_id, "expected_players", user_id)


def remove_expected_player(guild_id: int, user_id: int) -> bool:
    return _remove_list_value(guild_id, "expected_players", user_id)


def get_default_leader(guild_id: int) -> str:
    settings = ensure_guild_settings(guild_id)
    return str(settings.get("default_leader", "") or "")


def set_default_leader(guild_id: int, leader: str) -> None:
    update_guild_settings(guild_id, {"default_leader": leader.strip()})


def get_default_description(guild_id: int) -> str:
    settings = ensure_guild_settings(guild_id)
    return str(settings.get("default_description", "") or "")


def set_default_description(guild_id: int, description: str) -> None:
    update_guild_settings(guild_id, {"default_description": description.strip()})


def get_weakauras_channel_id(guild_id: int) -> int | None:
    settings = ensure_guild_settings(guild_id)
    value = settings.get("weakauras_channel_id")

    if value in (None, "", 0):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_weakauras_channel_id(guild_id: int, channel_id: int | None) -> None:
    update_guild_settings(guild_id, {"weakauras_channel_id": channel_id})


def get_guild_defaults(guild_id: int) -> dict:
    settings = ensure_guild_settings(guild_id)
    return {
        "guild_name": str(settings.get("guild_name", "") or ""),
        "raid_control_user_ids": [str(x) for x in settings.get("raid_control_user_ids", [])],
        "expected_players": [str(x) for x in settings.get("expected_players", [])],
        "default_leader": str(settings.get("default_leader", "") or ""),
        "default_description": str(settings.get("default_description", "") or ""),
        "weakauras_channel_id": settings.get("weakauras_channel_id"),
    }


def get_weakauras_message_id(guild_id: int) -> int | None:
    settings = ensure_guild_settings(guild_id)
    value = settings.get("weakauras_message_id")

    if value in (None, "", 0):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_weakauras_message_id(guild_id: int, message_id: int | None) -> None:
    update_guild_settings(guild_id, {"weakauras_message_id": message_id})