import asyncio
import discord

from services.comp.comp_message_service import post_comp_message
from views.signup.comp.comp_bench_view import CompBenchView
from utils.discord_utils import delete_interaction_after
from utils.ui_timing import (
    ERROR_MESSAGE_AUTO_DELETE_SECONDS,
    RAID_CONTROL_AUTO_DELETE_SECONDS,
)


async def _send_choice_error(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        msg = await interaction.followup.send(
            message,
            ephemeral=True,
            wait=True,
        )
        asyncio.create_task(msg.delete(delay=ERROR_MESSAGE_AUTO_DELETE_SECONDS))
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, ERROR_MESSAGE_AUTO_DELETE_SECONDS)
        )


def _build_bench_prompt(comp_data: dict) -> str:
    steps = comp_data.get("bench_choice_steps", [])
    if not steps:
        return "Select which player should be benched:"

    step = steps[0]
    count = int(step.get("count_to_bench", 0) or 0)
    role = step.get("role") or "player"
    player_word = "player" if count == 1 else "players"

    return f"Select {count} {role} {player_word} to bench."


class BuildCompOptionButton(discord.ui.Button):
    def __init__(self, label_text: str, comp_data: dict, row: int = 0):
        super().__init__(
            label=f"Build {label_text}",
            style=discord.ButtonStyle.success,
            row=row,
        )
        self.comp_data = comp_data

    async def callback(self, interaction: discord.Interaction):
        try:
            comp_data = self.comp_data
            steps = comp_data.get("bench_choice_steps", [])

            if steps:
                await interaction.response.edit_message(
                    content=_build_bench_prompt(comp_data),
                    view=CompBenchView(comp_data),
                )
                return

            ok, message = await post_comp_message(
                interaction.channel,
                comp_data,
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
            await _send_choice_error(
                interaction,
                f"Comp build failed: {type(e).__name__}: {e}",
            )


class CancelCompChoiceButton(discord.ui.Button):
    def __init__(self, row: int = 1):
        super().__init__(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="Comp build cancelled.",
            view=None,
        )
        asyncio.create_task(
            delete_interaction_after(interaction, RAID_CONTROL_AUTO_DELETE_SECONDS)
        )


class CompChoiceView(discord.ui.View):
    def __init__(self, option_226: dict, option_235: dict):
        super().__init__(timeout=120)
        self.add_item(BuildCompOptionButton("2/2/6", option_226, row=0))
        self.add_item(BuildCompOptionButton("2/3/5", option_235, row=0))
        self.add_item(CancelCompChoiceButton(row=1))