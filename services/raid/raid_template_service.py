from data.raid_template_store import get_guild_templates, save_guild_templates


def list_templates(guild_id: int) -> list[dict]:
    return get_guild_templates(guild_id)


def save_template(guild_id: int, template_name: str, raid_data: dict) -> bool:
    templates = get_guild_templates(guild_id)
    name = template_name.strip()

    if not name:
        return False

    existing_names = [t.get("name", "").strip().lower() for t in templates]
    if name.lower() in existing_names:
        return False

    template = {
        "name": name,
        "title": raid_data.get("title", "New Raid Signup"),
        "description": raid_data.get("description", ""),
        "leader": raid_data.get("leader", ""),
        "time": raid_data.get("time", "19:30"),
        "channel_id": raid_data.get("channel_id"),
        "is_recurring": bool(raid_data.get("is_recurring", False)),
        "recurring_interval_days": raid_data.get("recurring_interval_days"),
    }

    templates.append(template)
    save_guild_templates(guild_id, templates)
    return True


def overwrite_template(guild_id: int, template_name: str, raid_data: dict) -> bool:
    templates = get_guild_templates(guild_id)
    name = template_name.strip()

    if not name:
        return False

    found = False
    updated_templates = []

    for template in templates:
        if template.get("name", "").strip().lower() == name.lower():
            updated_templates.append(
                {
                    "name": name,
                    "title": raid_data.get("title", "New Raid Signup"),
                    "description": raid_data.get("description", ""),
                    "leader": raid_data.get("leader", ""),
                    "time": raid_data.get("time", "19:30"),
                    "channel_id": raid_data.get("channel_id"),
                    "is_recurring": bool(raid_data.get("is_recurring", False)),
                    "recurring_interval_days": raid_data.get("recurring_interval_days"),
                }
            )
            found = True
        else:
            updated_templates.append(template)

    if not found:
        return False

    save_guild_templates(guild_id, updated_templates)
    return True


def delete_template(guild_id: int, template_name: str) -> bool:
    templates = get_guild_templates(guild_id)
    name = template_name.strip().lower()

    updated_templates = [
        template
        for template in templates
        if template.get("name", "").strip().lower() != name
    ]

    if len(updated_templates) == len(templates):
        return False

    save_guild_templates(guild_id, updated_templates)
    return True


def get_template_by_name(guild_id: int, template_name: str) -> dict | None:
    templates = get_guild_templates(guild_id)
    name = template_name.strip().lower()

    for template in templates:
        if template.get("name", "").strip().lower() == name:
            return template

    return None


def build_raid_data_from_template(
    guild_id: int,
    channel_id: int,
    template_name: str,
    date_str: str,
) -> dict | None:
    template = get_template_by_name(guild_id, template_name)
    if not template:
        return None

    return {
        "title": template.get("title", "New Raid Signup"),
        "description": template.get("description", ""),
        "leader": template.get("leader", ""),
        "date": date_str,
        "time": template.get("time", "19:30"),
        "channel_id": template.get("channel_id") or channel_id,
        "is_recurring": bool(template.get("is_recurring", False)),
        "recurring_interval_days": template.get("recurring_interval_days"),
    }