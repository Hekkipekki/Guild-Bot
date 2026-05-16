from __future__ import annotations


def get_player_display_name(player: dict) -> str:
    return (
        (player.get("name") or "").strip()
        or (player.get("display_name") or "").strip()
        or "Unknown"
    )