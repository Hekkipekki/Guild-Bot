from __future__ import annotations

from services.raid.raid_control_service import (
    remove_player_signup,
    set_player_status,
)

from constants.statuses import (
    SIGNUP_STATUS_SIGN,
    SIGNUP_STATUS_BENCH,
    SIGNUP_STATUS_LATE,
    SIGNUP_STATUS_TENTATIVE,
    SIGNUP_STATUS_ABSENCE,
)


VALID_ACTIONS = {
    SIGNUP_STATUS_SIGN,
    SIGNUP_STATUS_BENCH,
    SIGNUP_STATUS_LATE,
    SIGNUP_STATUS_TENTATIVE,
    SIGNUP_STATUS_ABSENCE,
}


async def apply_raid_control_action(
    *,
    raid_id: str,
    user_id: str,
    action: str,
):
    if action == "remove":
        return remove_player_signup(
            raid_id,
            user_id,
        )

    if action not in VALID_ACTIONS:
        return False

    return set_player_status(
        raid_id,
        user_id,
        action,
    )