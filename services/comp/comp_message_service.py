import discord

from data.signup_store import load_signups, save_signups, find_message_signup
from logic.embed.comp_embed import build_comp_embed
from services.attendance.attendance_service import sync_attendance_from_comp


def _apply_signup_metadata_to_comp_data(signup: dict, comp_data: dict) -> dict:
    updated = dict(comp_data)
    updated["title"] = signup.get("title", updated.get("title", "Raid Comp"))
    updated["description"] = signup.get("description", updated.get("description", ""))
    updated["leader"] = signup.get("leader", updated.get("leader", ""))
    updated["start_ts"] = signup.get("start_ts", updated.get("start_ts"))
    return updated


def _persist_comp_data(signup: dict, comp_message_id: int | None, comp_data: dict) -> None:
    signup["comp_message_id"] = comp_message_id
    signup["last_comp_data"] = comp_data
    signup["attendance_snapshot_created"] = True
    signup["attendance_record_id"] = str(comp_data["raid_id"])


def _sync_attendance(signup: dict, comp_message_id: int | None, comp_data: dict) -> None:
    sync_attendance_from_comp(
        raid_id=comp_data["raid_id"],
        guild_id=signup.get("guild_id"),
        channel_id=signup.get("channel_id"),
        comp_message_id=comp_message_id,
        comp_data=comp_data,
        actor_user_id=None,
    )


async def post_comp_message(channel, comp_data: dict) -> tuple[bool, str]:
    data = load_signups()
    raid_id = comp_data["raid_id"]
    signup = find_message_signup(data, raid_id)

    if not signup:
        return False, "Raid not found."

    comp_data = _apply_signup_metadata_to_comp_data(signup, comp_data)

    embed = build_comp_embed(comp_data)
    mentions = " ".join(comp_data.get("mentions", []))
    message_id = signup.get("comp_message_id")

    try:
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(content=mentions, embed=embed)

                _persist_comp_data(signup, msg.id, comp_data)
                _sync_attendance(signup, msg.id, comp_data)
                save_signups(data)

                return True, "Comp updated."
            except discord.NotFound:
                signup["comp_message_id"] = None
                save_signups(data)

        msg = await channel.send(
            content=mentions,
            embed=embed,
        )

        _persist_comp_data(signup, msg.id, comp_data)
        _sync_attendance(signup, msg.id, comp_data)
        save_signups(data)

        return True, "Comp posted."

    except Exception as e:
        return False, str(e)


async def refresh_existing_comp_message(channel, raid_id: int | str) -> tuple[bool, str]:
    data = load_signups()
    signup = find_message_signup(data, raid_id)

    if not signup:
        return False, "Raid not found."

    comp_message_id = signup.get("comp_message_id")
    last_comp_data = signup.get("last_comp_data")

    if not comp_message_id or not last_comp_data:
        return True, "No existing comp message to refresh."

    updated_comp_data = _apply_signup_metadata_to_comp_data(signup, last_comp_data)
    embed = build_comp_embed(updated_comp_data)
    mentions = " ".join(updated_comp_data.get("mentions", []))

    try:
        msg = await channel.fetch_message(comp_message_id)
        await msg.edit(content=mentions, embed=embed)

        _persist_comp_data(signup, msg.id, updated_comp_data)
        _sync_attendance(signup, msg.id, updated_comp_data)
        save_signups(data)

        return True, "Comp metadata refreshed."

    except discord.NotFound:
        signup["comp_message_id"] = None
        save_signups(data)
        return False, "Existing comp message was not found."

    except Exception as e:
        return False, str(e)