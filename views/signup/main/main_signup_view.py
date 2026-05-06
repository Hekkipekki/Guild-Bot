import discord

from views.signup.main.status_buttons import SignupStatusButton
from views.signup.main.class_dropdown import ClassDropdown
from views.signup.raid_control.raid_control_button import RaidControlButton


class SignupView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=None)
        self.raid_id = raid_id

        dropdown = ClassDropdown(self.raid_id)
        dropdown.row = 0
        self.add_item(dropdown)

        self.add_item(
            SignupStatusButton(
                raid_id=self.raid_id,
                status="late",
                label="Late",
                emoji_name="late",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
        )
        self.add_item(
            SignupStatusButton(
                raid_id=self.raid_id,
                status="bench",
                label="Bench",
                emoji_name="bench",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
        )
        self.add_item(
            SignupStatusButton(
                raid_id=self.raid_id,
                status="tentative",
                label="Tentative",
                emoji_name="tentative",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
        )
        self.add_item(
            SignupStatusButton(
                raid_id=self.raid_id,
                status="absence",
                label="Absence",
                emoji_name="absence",
                style=discord.ButtonStyle.secondary,
                row=1,
            )
        )

        self.add_item(
            RaidControlButton(
                raid_id=self.raid_id,
                row=1,
            )
        )