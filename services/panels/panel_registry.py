from services.guild.weakauras_panel_service import WEAKAURAS_PANEL
from services.scheduling.scheduling_panel_service import SCHEDULING_PANEL


PERMANENT_PANELS = (
    WEAKAURAS_PANEL,
    SCHEDULING_PANEL,
)

PERMANENT_PANELS_BY_KEY = {
    panel.key: panel
    for panel in PERMANENT_PANELS
}
