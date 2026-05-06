from data.character_store import (
    get_user_characters as store_get_user_characters,
    get_character_by_class as store_get_character_by_class,
    add_character as store_add_character,
    remove_character as store_remove_character,
    update_character_name_by_class as store_update_character_name_by_class,
    update_character_spec_by_class as store_update_character_spec_by_class,
)


"""
Character Service

Thin service layer that wraps the character_store_dev.

Responsibilities:
• Enforce guild-scoped character storage
• Provide a stable interface for UI and signup systems
• Prevent direct store access from views
"""


# -----------------------------
# Fetch characters
# -----------------------------


def get_user_characters(guild_id: int, user_id: int) -> list[dict]:
    """Return all saved characters for a user in a specific guild."""
    return store_get_user_characters(guild_id, user_id)


def get_character_by_class(
    guild_id: int,
    user_id: int,
    class_name: str,
) -> dict | None:
    """Return the character saved for a specific class."""
    return store_get_character_by_class(guild_id, user_id, class_name)


# -----------------------------
# Add / Remove characters
# -----------------------------


def add_user_character(
    guild_id: int,
    user_id: int,
    char: dict,
) -> bool:
    """Add a new character to the user's guild character list."""
    return store_add_character(guild_id, user_id, char)


def remove_user_character(
    guild_id: int,
    user_id: int,
    index: int,
) -> bool:
    """Remove a character by index."""
    return store_remove_character(guild_id, user_id, index)


# -----------------------------
# Update characters
# -----------------------------


def update_character_name(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_name: str,
) -> bool:
    """Update a character's name for a given class."""
    return store_update_character_name_by_class(
        guild_id,
        user_id,
        class_name,
        new_name,
    )


def update_character_spec(
    guild_id: int,
    user_id: int,
    class_name: str,
    new_spec: str,
    new_role: str,
) -> bool:
    """Update spec and role for a character."""
    return store_update_character_spec_by_class(
        guild_id,
        user_id,
        class_name,
        new_spec,
        new_role,
    )