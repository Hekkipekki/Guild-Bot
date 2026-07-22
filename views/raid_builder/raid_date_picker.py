from __future__ import annotations

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

import discord

from utils.panel_helpers import safe_panel_edit


SWEDEN_TZ = ZoneInfo("Europe/Stockholm")


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _shift_month(value: date, offset: int) -> date:
    month_index = (value.year * 12 + value.month - 1) + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _build_picker_content(month_value: date, selected_date: date | None = None) -> str:
    month_name = calendar.month_name[month_value.month]
    lines = [
        f"## 📅 Select Raid Date — {month_name} {month_value.year}",
        "Choose a week below, then select the raid date.",
    ]

    if selected_date is not None:
        lines.append(f"\nSelected: **{selected_date.strftime('%A, %d %B %Y')}**")

    return "\n".join(lines)


class RaidDateSelect(discord.ui.Select):
    def __init__(self, raid_data: dict, month_value: date, week_index: int):
        self.raid_data = dict(raid_data)
        self.month_value = month_value
        self.week_index = week_index

        month_weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            month_value.year,
            month_value.month,
        )
        selected_week = month_weeks[week_index]
        today = datetime.now(SWEDEN_TZ).date()

        options: list[discord.SelectOption] = []
        for day_value in selected_week:
            if day_value.month != month_value.month or day_value < today:
                continue

            options.append(
                discord.SelectOption(
                    label=day_value.strftime("%A %d %B"),
                    value=day_value.isoformat(),
                    description=f"Week {day_value.isocalendar().week}",
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No available dates",
                    value="unavailable",
                    description="Choose another week or month",
                )
            )

        super().__init__(
            placeholder=f"Select date from week {selected_week[0].isocalendar().week}",
            options=options,
            min_values=1,
            max_values=1,
            row=1,
            disabled=options[0].value == "unavailable",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "unavailable":
            return

        selected_date = date.fromisoformat(self.values[0])
        updated_data = dict(self.raid_data)
        updated_data["date"] = selected_date.isoformat()

        from views.raid_builder.raid_builder_helpers import build_preview_embed
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await safe_panel_edit(
            interaction,
            content=f"✅ Raid date set to **{selected_date.strftime('%A, %d %B %Y')}**.",
            embed=build_preview_embed(guild, updated_data),
            view=RaidBuilderView(updated_data),
        )


class RaidWeekSelect(discord.ui.Select):
    def __init__(self, raid_data: dict, month_value: date):
        self.raid_data = dict(raid_data)
        self.month_value = month_value

        today = datetime.now(SWEDEN_TZ).date()
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(
            month_value.year,
            month_value.month,
        )

        options: list[discord.SelectOption] = []
        for index, week in enumerate(weeks):
            valid_days = [
                day_value
                for day_value in week
                if day_value.month == month_value.month and day_value >= today
            ]
            if not valid_days:
                continue

            first_day = valid_days[0]
            last_day = valid_days[-1]
            options.append(
                discord.SelectOption(
                    label=f"Week {first_day.isocalendar().week}",
                    value=str(index),
                    description=(
                        f"{first_day.strftime('%d %b')} – {last_day.strftime('%d %b')}"
                    ),
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No available weeks",
                    value="unavailable",
                    description="Move to the next month",
                )
            )

        super().__init__(
            placeholder="Choose a week",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
            disabled=options[0].value == "unavailable",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "unavailable":
            return

        week_index = int(self.values[0])
        await safe_panel_edit(
            interaction,
            content=_build_picker_content(self.month_value),
            embed=None,
            view=RaidDatePickerView(
                self.raid_data,
                self.month_value,
                selected_week_index=week_index,
            ),
        )


class PreviousMonthButton(discord.ui.Button):
    def __init__(self, raid_data: dict, month_value: date):
        super().__init__(
            label="Previous Month",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.raid_data = dict(raid_data)
        self.month_value = month_value

    async def callback(self, interaction: discord.Interaction):
        previous_month = _shift_month(self.month_value, -1)
        current_month = _month_start(
            datetime.now(SWEDEN_TZ).year,
            datetime.now(SWEDEN_TZ).month,
        )

        if previous_month < current_month:
            previous_month = current_month

        await safe_panel_edit(
            interaction,
            content=_build_picker_content(previous_month),
            embed=None,
            view=RaidDatePickerView(self.raid_data, previous_month),
        )


class NextMonthButton(discord.ui.Button):
    def __init__(self, raid_data: dict, month_value: date):
        super().__init__(
            label="Next Month",
            emoji="➡️",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.raid_data = dict(raid_data)
        self.month_value = month_value

    async def callback(self, interaction: discord.Interaction):
        next_month = _shift_month(self.month_value, 1)
        await safe_panel_edit(
            interaction,
            content=_build_picker_content(next_month),
            embed=None,
            view=RaidDatePickerView(self.raid_data, next_month),
        )


class BackToRaidBuilderButton(discord.ui.Button):
    def __init__(self, raid_data: dict):
        super().__init__(
            label="Back",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.raid_data = dict(raid_data)

    async def callback(self, interaction: discord.Interaction):
        from views.raid_builder.raid_builder_helpers import build_preview_embed
        from views.raid_builder.raid_builder_view import RaidBuilderView

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "⚠ This command can only be used in a server.",
                ephemeral=True,
            )
            return

        await safe_panel_edit(
            interaction,
            content=None,
            embed=build_preview_embed(guild, self.raid_data),
            view=RaidBuilderView(self.raid_data),
        )


class RaidDatePickerView(discord.ui.View):
    def __init__(
        self,
        raid_data: dict,
        month_value: date | None = None,
        *,
        selected_week_index: int | None = None,
    ):
        super().__init__(timeout=120)

        if month_value is None:
            now = datetime.now(SWEDEN_TZ)
            month_value = _month_start(now.year, now.month)

        self.add_item(RaidWeekSelect(raid_data, month_value))

        if selected_week_index is not None:
            self.add_item(
                RaidDateSelect(
                    raid_data,
                    month_value,
                    selected_week_index,
                )
            )

        self.add_item(PreviousMonthButton(raid_data, month_value))
        self.add_item(NextMonthButton(raid_data, month_value))
        self.add_item(BackToRaidBuilderButton(raid_data))


def build_raid_date_picker_content(month_value: date | None = None) -> str:
    if month_value is None:
        now = datetime.now(SWEDEN_TZ)
        month_value = _month_start(now.year, now.month)

    return _build_picker_content(month_value)
