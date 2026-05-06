from __future__ import annotations

import discord

from services.guild.guild_settings_service import get_raid_control_users


def can_manage_raid_tools(source: discord.Interaction | discord.abc.Snowflake | discord.Member) -> bool:
    """
    Guild-scoped permission check for raid tools.

    Accepts either:
    - discord.Interaction
    - discord.Member
    - any object that exposes .guild and .id like a guild member

    Rules:
    1. Server administrators always pass
    2. Users listed in this guild's raid_control_user_ids pass
    3. Everyone else fails
    """

    if isinstance(source, discord.Interaction):
        user = source.user
        guild = source.guild
    else:
        user = source
        guild = getattr(source, "guild", None)

    if guild is None:
        return False

    guild_permissions = getattr(user, "guild_permissions", None)
    if guild_permissions and getattr(guild_permissions, "administrator", False):
        return True

    allowed_ids = get_raid_control_users(guild.id)
    return str(user.id) in {str(user_id) for user_id in allowed_ids}