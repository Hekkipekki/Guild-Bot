from __future__ import annotations

import discord

from utils.permissions import can_manage_raid_tools

from utils.panel_helpers import (
    send_panel_error,
    safe_panel_edit,
)

from services.signup.signup_refresh_service import (
    refresh_signup_message_by_id,
)

from views.signup.raid_control.raid_control_components import (
    RaidControlPlayerSelect,
    RaidControlActionSelect,
)

from views.signup.raid_control.raid_control_navigation import (
    CloseRaidControlButton,
)

from views.signup.raid_control.raid_control_actions import (
    apply_raid_control_action,
)

from views.signup.raid_control.raid_control_buttons import (
    OpenAttendanceButton,
    OpenSpecManagementButton,
    OpenRaidSettingsButton,
    PostCompButton,
    CancelRaidButton,
)

from views.signup.raid_control.raid_control_notes import (
    OpenNotesButton,
)


class RaidControlView(discord.ui.View):
    def __init__(self, raid_id: str):
        super().__init__(timeout=120)

        self.raid_id = str(raid_id)

        self.selected_user_id: str | None = None
        self.selected_action: str | None = None

        self.add_item(
            RaidControlPlayerSelect(self.raid_id)
        )

        self.add_item(
            RaidControlActionSelect()
        )

        self.add_item(
            OpenSpecManagementButton(self.raid_id)
        )

        self.add_item(
            OpenRaidSettingsButton(self.raid_id)
        )

        self.add_item(
            OpenAttendanceButton(self.raid_id)
        )

        self.add_item(
            OpenNotesButton(self.raid_id)
)

        self.add_item(
            PostCompButton(self.raid_id)
        )

        self.add_item(
            CancelRaidButton(self.raid_id)
        )

        self.add_item(
            CloseRaidControlButton()
        )

    async def try_apply_action(
        self,
        interaction: discord.Interaction,
    ):
        if not can_manage_raid_tools(interaction):
            await send_panel_error(
                interaction,
                "You do not have access to raid control.",
            )
            return

        if not self.selected_user_id:
            return

        if not self.selected_action:
            return

        ok = await apply_raid_control_action(
            raid_id=self.raid_id,
            user_id=self.selected_user_id,
            action=self.selected_action,
        )

        if not ok:
            await send_panel_error(
                interaction,
                "Could not apply raid control action.",
            )
            return

        refreshed = await refresh_signup_message_by_id(
            interaction.channel,
            int(self.raid_id),
        )

        if not refreshed:
            await send_panel_error(
                interaction,
                "Raid updated, but failed to refresh signup message.",
            )
            return

        await safe_panel_edit(
            interaction,
            content="Raid control updated.",
            view=RaidControlView(self.raid_id),
        )