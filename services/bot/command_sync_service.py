from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSyncPlan:
    mode: str
    guild_id: int | None = None

    @property
    def is_guild_sync(self) -> bool:
        return self.mode == "guild"

    @property
    def is_global_sync(self) -> bool:
        return self.mode == "global"


def build_command_sync_plan(
    *,
    dev_mode: bool,
    test_guild_id: int | str | None,
) -> CommandSyncPlan:
    """Resolve how application commands should be synced for this runtime."""
    if not dev_mode:
        return CommandSyncPlan(mode="global")

    if test_guild_id in (None, "", 0, "0"):
        raise RuntimeError(
            "DEV_MODE is enabled, but TEST_GUILD_ID is not configured. "
            "Set TEST_GUILD_ID in secrets_local.py before starting the bot."
        )

    try:
        guild_id = int(test_guild_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "DEV_MODE is enabled, but TEST_GUILD_ID is not a valid Discord guild ID."
        ) from exc

    if guild_id <= 0:
        raise RuntimeError(
            "DEV_MODE is enabled, but TEST_GUILD_ID must be a positive Discord guild ID."
        )

    return CommandSyncPlan(mode="guild", guild_id=guild_id)
