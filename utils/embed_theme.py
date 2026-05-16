# ================================================
# FILE: utils/embed_theme.py
# ================================================

import discord


DEFAULT_EMBED_COLOR = discord.Color.purple()


def build_base_embed(
    *,
    title: str,
    description: str | None = None,
    color: discord.Color = DEFAULT_EMBED_COLOR,
    footer: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description or "",
        color=color,
    )

    if footer:
        embed.set_footer(text=footer)

    return embed


def build_panel_embed(
    *,
    title: str,
    description: str | None = None,
) -> discord.Embed:
    return build_base_embed(
        title=title,
        description=description,
        footer="This panel closes automatically.",
    )


def build_success_embed(
    *,
    title: str,
    description: str | None = None,
) -> discord.Embed:
    return build_base_embed(
        title=title,
        description=description,
        color=discord.Color.green(),
    )


def build_error_embed(
    *,
    title: str,
    description: str | None = None,
) -> discord.Embed:
    return build_base_embed(
        title=title,
        description=description,
        color=discord.Color.red(),
    )