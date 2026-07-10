from collections.abc import Callable
from copy import deepcopy
from typing import Any


CURRENT_GUILD_SETTINGS_VERSION = 2


class UnsupportedGuildSettingsVersionError(ValueError):
    """Raised when settings were written by a newer bot version."""


Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _migrate_v0_to_v1(settings: dict[str, Any]) -> dict[str, Any]:
    """Add the first explicit schema version and current configurable fields."""
    migrated = deepcopy(settings)
    migrated.setdefault("hidden_weakaura_items", [])
    migrated.setdefault("raid_weekdays", [2, 6])
    migrated["config_version"] = 1
    return migrated


def _migrate_v1_to_v2(settings: dict[str, Any]) -> dict[str, Any]:
    """Add per-guild Warcraft Logs configuration fields."""
    migrated = deepcopy(settings)
    migrated.setdefault("warcraftlogs_guild_id", None)
    migrated.setdefault("warcraftlogs_raid_size", 10)
    migrated.setdefault("warcraftlogs_region", "eu")
    migrated["config_version"] = 2
    return migrated


MIGRATIONS: dict[int, Migration] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
}


def _read_version(settings: dict[str, Any]) -> int:
    value = settings.get("config_version", 0)
    try:
        version = int(value)
    except (TypeError, ValueError):
        return 0
    return max(version, 0)


def migrate_guild_settings(block: dict[str, Any] | Any) -> dict[str, Any]:
    """Return a migrated copy without mutating the supplied settings object.

    Unknown keys are retained. Configurations created by a newer bot version
    are rejected so an older deployment cannot silently rewrite or downgrade
    them.
    """
    settings = deepcopy(block) if isinstance(block, dict) else {}
    version = _read_version(settings)

    if version > CURRENT_GUILD_SETTINGS_VERSION:
        raise UnsupportedGuildSettingsVersionError(
            "Guild settings version "
            f"{version} is newer than supported version "
            f"{CURRENT_GUILD_SETTINGS_VERSION}."
        )

    while version < CURRENT_GUILD_SETTINGS_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise RuntimeError(
                f"Missing guild settings migration from version {version}."
            )
        settings = migration(settings)
        next_version = _read_version(settings)
        if next_version <= version:
            raise RuntimeError(
                f"Guild settings migration from version {version} did not advance."
            )
        version = next_version

    settings["config_version"] = CURRENT_GUILD_SETTINGS_VERSION
    return settings
