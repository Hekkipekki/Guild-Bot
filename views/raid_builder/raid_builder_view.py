import discord

from views.raid_builder.raid_builder_buttons import (
    CreateNewRaidButton,
    UseTemplateButton,
    CancelRaidStartButton,
    DeleteTemplateButton,
    BackFromTemplateButton,
    EditTitleButton,
    EditDescriptionButton,
    EditLeaderButton,
    EditDateButton,
    EditTimeButton,
    RecurringRaidButton,
    SaveTemplateButton,
    OverwriteTemplateButton,
    PostRaidButton,
    BackToRaidStartButton,
    CancelRaidBuilderButton,
)
from views.raid_builder.raid_builder_selects import (
    RaidTemplateSelect,
    DeleteTemplateSelect,
    RaidChannelSelect,
)


class RaidStartView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=120)
        self.add_item(CreateNewRaidButton(guild_id, channel_id))
        self.add_item(UseTemplateButton(guild_id, channel_id))
        self.add_item(CancelRaidStartButton())


class DeleteTemplateView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=120)
        self.add_item(DeleteTemplateSelect(guild_id, channel_id))
        self.add_item(BackFromTemplateButton(guild_id, channel_id))


class RaidTemplateView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=120)
        self.add_item(RaidTemplateSelect(guild_id, channel_id))
        self.add_item(DeleteTemplateButton(guild_id, channel_id))
        self.add_item(BackFromTemplateButton(guild_id, channel_id))


class RaidBuilderView(discord.ui.View):
    def __init__(self, raid_data: dict, existing_template_name: str | None = None):
        super().__init__(timeout=120)
        self.add_item(EditTitleButton(raid_data))
        self.add_item(EditDescriptionButton(raid_data))
        self.add_item(EditLeaderButton(raid_data))
        self.add_item(EditDateButton(raid_data))
        self.add_item(EditTimeButton(raid_data))
        self.add_item(RecurringRaidButton(raid_data))
        self.add_item(RaidChannelSelect(raid_data))
        self.add_item(SaveTemplateButton(raid_data))

        if existing_template_name:
            self.add_item(OverwriteTemplateButton(raid_data, existing_template_name))

        self.add_item(PostRaidButton(raid_data))
        self.add_item(BackToRaidStartButton())
        self.add_item(CancelRaidBuilderButton())