import asyncio
import discord

from services.comp.comp_message_service import post_comp_message
from utils.ui_timing import RAID_CONTROL_AUTO_DELETE_SECONDS, ERROR_MESSAGE_AUTO_DELETE_SECONDS
from utils.emoji_helpers import parse_spec_emoji
from utils.discord_utils import delete_interaction_after


def _display_role(entry: dict) -> str:
    role = entry.get("role", "")
    if role in ("Melee", "Ranged"):
        return "DPS"
    return role


def _player_label(user_id: str, entry: dict) -> str:
    name = entry.get("name") or entry.get("display_name") or user_id
    spec = entry.get("spec", "")
    role = _display_role(entry)
    return f"{name} ({spec} {role})"


def _sort_by_timestamp(players: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    return sorted(players, key=lambda item: item[1].get("timestamp", 0))


def _group_signed(players: list[tuple[str, dict]]) -> dict[str, list[tuple[str, dict]]]:
    grouped = {"Tank": [], "Healer": [], "DPS": []}

    for user_id, entry in players:
        role = _display_role(entry)
        if role in grouped:
            grouped[role].append((user_id, entry))

    return grouped


def _consume_next_bench_step(comp_data: dict, benched_user_ids: set[str]) -> dict:
    signed_players = [
        (user_id, entry)
        for user_id, entry in comp_data.get("signed_players", [])
        if user_id not in benched_user_ids
    ]

    grouped = _group_signed(_sort_by_timestamp(signed_players))
    role_targets = comp_data.get("role_targets", {})

    tanks = grouped["Tank"][:role_targets.get("Tank", 2)]
    healers = grouped["Healer"][:role_targets.get("Healer", 0)]
    dps = grouped["DPS"][:role_targets.get("DPS", 0)]

    selected_players = tanks + healers + dps
    selected_ids = {user_id for user_id, _ in selected_players}

    group_1 = list(tanks) + list(healers)
    remaining_dps = list(dps)

    while len(group_1) < 5 and remaining_dps:
        group_1.append(remaining_dps.pop(0))

    group_2 = remaining_dps

    existing_bench = list(comp_data.get("bench_players", []))
    new_bench = list(existing_bench)

    for user_id, entry in comp_data.get("signed_players", []):
        if user_id in benched_user_ids and all(user_id != existing_id for existing_id, _ in new_bench):
            new_bench.append((user_id, entry))

    remaining_steps = list(comp_data.get("bench_choice_steps", []))
    if remaining_steps:
        remaining_steps.pop(0)

    updated = dict(comp_data)
    updated["signed_players"] = signed_players
    updated["selected_players"] = selected_players
    updated["mentions"] = [f"<@{user_id}>" for user_id, _ in selected_players]
    updated["group_1"] = group_1
    updated["group_2"] = group_2
    updated["bench_players"] = new_bench
    updated["bench_choice_steps"] = remaining_steps

    if not remaining_steps:
        for user_id, entry in signed_players:
            if user_id not in selected_ids and all(user_id != existing_id for existing_id, _ in new_bench):
                new_bench.append((user_id, entry))
        updated["bench_players"] = new_bench

    return updated


def _build_step_prompt(step: dict) -> str:
    count = int(step.get("count_to_bench", 0) or 0)
    role = step.get("role") or "player"
    player_word = "player" if count == 1 else "players"
    return f"Select {count} {role} {player_word} to bench."


class BenchSelect(discord.ui.Select):
    def __init__(self, comp_data: dict, step: dict):
        self.comp_data = comp_data
        self.step = step

        bench_count = max(1, int(step.get("count_to_bench", 1)))
        candidates = step.get("candidates", [])

        options = []
        for user_id, entry in candidates:
            spec = entry.get("spec", "")
            options.append(
                discord.SelectOption(
                    label=_player_label(user_id, entry)[:100],
                    value=user_id,
                    emoji=parse_spec_emoji(spec),
                )
            )

        super().__init__(
            placeholder=_build_step_prompt(step)[:150],
            min_values=bench_count,
            max_values=bench_count,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_ids = set(self.values)
            updated_comp_data = _consume_next_bench_step(self.comp_data, selected_ids)
            remaining_steps = updated_comp_data.get("bench_choice_steps", [])

            if remaining_steps:
                next_step = remaining_steps[0]
                await interaction.response.edit_message(
                    content=_build_step_prompt(next_step),
                    view=CompBenchView(updated_comp_data),
                )
                return

            ok, message = await post_comp_message(
                interaction.channel,
                updated_comp_data,
            )

            if not ok:
                await interaction.response.edit_message(
                    content=message,
                    view=None,
                )
                asyncio.create_task(
                    delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
                )
                return

            await interaction.response.edit_message(
                content="Comp posted.",
                view=None,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
            )

        except Exception as e:
            await interaction.response.edit_message(
                content=f"Failed to post comp: {type(e).__name__}: {e}",
                view=None,
            )
            asyncio.create_task(
                delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
            )


class CompBenchView(discord.ui.View):
    def __init__(self, comp_data: dict):
        super().__init__(timeout=120)
        steps = comp_data.get("bench_choice_steps", [])
        if steps:
            self.add_item(BenchSelect(comp_data, steps[0]))