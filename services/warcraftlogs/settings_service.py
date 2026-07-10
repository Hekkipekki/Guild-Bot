from __future__ import annotations

from dataclasses import dataclass

from data.guild_settings_store import ensure_guild_settings, update_guild_settings


VALID_WARCRAFTLOGS_REGIONS = {"us", "eu", "kr", "tw", "cn"}
VALID_WARCRAFTLOGS_RAID_SIZES = {10, 25}


@dataclass(frozen=True)
class WarcraftLogsGuildSettings:
    guild_id: int | None
    region: str
    raid_size: int

    @property
    def is_configured(self) -> bool:
        return self.guild_id is not None


def get_warcraftlogs_settings(discord_guild_id: int) -> WarcraftLogsGuildSettings:
    settings = ensure_guild_settings(discord_guild_id)
    value = settings.get("warcraftlogs_guild_id")
    try:
        logs_guild_id = int(value) if value else None
    except (TypeError, ValueError):
        logs_guild_id = None

    region = str(settings.get("warcraftlogs_region", "eu") or "eu").lower()
    if region not in VALID_WARCRAFTLOGS_REGIONS:
        region = "eu"

    try:
        raid_size = int(settings.get("warcraftlogs_raid_size", 10))
    except (TypeError, ValueError):
        raid_size = 10
    if raid_size not in VALID_WARCRAFTLOGS_RAID_SIZES:
        raid_size = 10

    return WarcraftLogsGuildSettings(
        guild_id=logs_guild_id,
        region=region,
        raid_size=raid_size,
    )


def set_warcraftlogs_settings(
    discord_guild_id: int,
    *,
    logs_guild_id: int,
    region: str = "eu",
    raid_size: int = 10,
) -> WarcraftLogsGuildSettings:
    clean_guild_id = int(logs_guild_id)
    if clean_guild_id <= 0:
        raise ValueError("Warcraft Logs guild ID must be a positive integer.")

    clean_region = str(region).strip().lower()
    if clean_region not in VALID_WARCRAFTLOGS_REGIONS:
        raise ValueError(
            f"Unsupported Warcraft Logs region: {region}."
        )

    clean_raid_size = int(raid_size)
    if clean_raid_size not in VALID_WARCRAFTLOGS_RAID_SIZES:
        raise ValueError("Warcraft Logs raid size must be 10 or 25.")

    update_guild_settings(
        discord_guild_id,
        {
            "warcraftlogs_guild_id": clean_guild_id,
            "warcraftlogs_region": clean_region,
            "warcraftlogs_raid_size": clean_raid_size,
        },
    )
    return get_warcraftlogs_settings(discord_guild_id)


def clear_warcraftlogs_settings(discord_guild_id: int) -> None:
    update_guild_settings(
        discord_guild_id,
        {
            "warcraftlogs_guild_id": None,
            "warcraftlogs_region": "eu",
            "warcraftlogs_raid_size": 10,
        },
    )
