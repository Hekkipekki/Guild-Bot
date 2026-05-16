import discord

from logic.embed.signup_themes.classic import build_classic_signup_embed


DEFAULT_SIGNUP_THEME = "classic"


def get_signup_theme(signup: dict) -> str:
    return (
        signup.get("signup_theme")
        or signup.get("theme")
        or DEFAULT_SIGNUP_THEME
    )


def build_signup_embed(title: str, description: str, signup: dict) -> discord.Embed:
    theme = get_signup_theme(signup)

    if theme == "classic":
        return build_classic_signup_embed(title, description, signup)

    # Safe fallback
    return build_classic_signup_embed(title, description, signup)