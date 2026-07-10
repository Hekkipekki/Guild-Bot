import discord

from services.guild.guild_settings_service import get_guild_defaults
from utils.embed_theme import build_panel_embed


WEEKDAY_LABELS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def build_guild_config_embed(guild: discord.Guild) -> discord.Embed:
    settings = get_guild_defaults(guild.id)

    raid_admins = settings.get("raid_control_user_ids", [])
    raid_team = settings.get("expected_players", [])
    weakauras_channel_id = settings.get("weakauras_channel_id")
    scheduling_channel_id = settings.get("scheduling_channel_id")
    signup_theme_label = settings.get("signup_theme_label", "Classic")
    hidden_wa_items = settings.get("hidden_weakaura_items", [])
    raid_weekdays = settings.get("raid_weekdays", [2, 6])

    raid_admin_text = (
        "\n".join(f"• <@{user_id}>" for user_id in raid_admins)
        if raid_admins
        else "-"
    )

    raid_team_text = (
        "\n".join(f"• <@{user_id}>" for user_id in raid_team)
        if raid_team
        else "-"
    )

    wa_channel_text = f"<#{weakauras_channel_id}>" if weakauras_channel_id else "-"
    scheduling_channel_text = (
        f"<#{scheduling_channel_id}>" if scheduling_channel_id else "-"
    )
    raid_days_text = ", ".join(
        WEEKDAY_LABELS.get(int(day), str(day)) for day in raid_weekdays
    )

    embed = build_panel_embed(
        title=f"Setup — {guild.name}",
        description="Configure this server's raid bot setup.",
    )

    embed.add_field(
        name="Raid Admins / Leaders",
        value=raid_admin_text,
        inline=False,
    )
    embed.add_field(name="Raid Team", value=raid_team_text, inline=False)
    embed.add_field(name="Signup Theme", value=signup_theme_label, inline=False)
    embed.add_field(
        name="WeakAuras Channel",
        value=f"{wa_channel_text}\nHidden entries: {len(hidden_wa_items)}",
        inline=False,
    )
    embed.add_field(
        name="Scheduling",
        value=f"{scheduling_channel_text}\nRaid days: {raid_days_text}",
        inline=False,
    )

    return embed
