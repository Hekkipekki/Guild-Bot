import discord

from data.signup_store import load_signups, find_message_signup
from logic.embed.signup_embed import build_signup_embed


def _build_signup_embed_for_raid(raid_id: int) -> discord.Embed | None:
    data = load_signups()
    signup = find_message_signup(data, raid_id)

    if not signup:
        return None

    title = signup.get("title", "Raid Signup")
    description = signup.get("description", "")

    return build_signup_embed(title, description, signup)


async def refresh_signup_message(
    interaction: discord.Interaction,
    raid_id: int,
) -> bool:
    embed = _build_signup_embed_for_raid(raid_id)

    if embed is None:
        return False

    from views.signup_views import SignupView

    try:
        await interaction.message.edit(
            embed=embed,
            view=SignupView(str(raid_id)),
        )
        return True

    except discord.NotFound:
        return False
    except discord.HTTPException:
        return False


async def refresh_signup_message_by_id(
    channel: discord.abc.Messageable,
    raid_id: int,
) -> bool:
    embed = _build_signup_embed_for_raid(raid_id)

    if embed is None:
        return False

    from views.signup_views import SignupView

    try:
        message = await channel.fetch_message(raid_id)

        await message.edit(
            embed=embed,
            view=SignupView(str(raid_id)),
        )

        return True

    except discord.NotFound:
        return False
    except discord.Forbidden:
        return False
    except discord.HTTPException:
        return False