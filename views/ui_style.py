from __future__ import annotations

import discord


BUTTON_VARIANTS = {
    "default": discord.ButtonStyle.secondary,
    "primary": discord.ButtonStyle.primary,
    "danger": discord.ButtonStyle.danger,
    "success": discord.ButtonStyle.success,
}


BUTTON_VARIANT_OVERRIDES = {
    "raid_control.cancel_raid": "danger",
}


def get_button_style(
    key: str,
    *,
    variant: str | None = None,
):
    selected_variant = (
        variant
        or BUTTON_VARIANT_OVERRIDES.get(key)
        or "default"
    )

    return BUTTON_VARIANTS[selected_variant]