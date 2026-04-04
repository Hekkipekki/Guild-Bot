from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from services.attendance.attendance_report_service import (
    build_attendance_matrix,
    get_attendance_overview_stats,
)


STATUS_COLORS = {
    "attending": "#179c32",     # green
    "benched": "#a59b24",       # yellow
    "late": "#1f6fd1",          # blue

    "absent": "#c32626",        # red
    "tentative": "#c32626",     # red
    "no_sign": "#c32626",       # red
    "not_selected": "#c32626",  # red

    "unknown": "#101010",
    None: "#101010",
}

BACKGROUND_COLOR = "#0a0a0a"
HEADER_BG = "#171717"
GRID_BORDER = "#242424"
TEXT_PRIMARY = "#f2f2f2"
TEXT_MUTED = "#bdbdbd"
ROW_ALT_1 = "#050505"
ROW_ALT_2 = "#090909"

LEFT_NAME_WIDTH = 210
PCT_WIDTH = 78
CELL_WIDTH = 72
HEADER_HEIGHT = 46
ROW_HEIGHT = 34
TOP_TITLE_HEIGHT = 42
BOTTOM_PADDING = 14
RIGHT_PADDING = 12
LEFT_PADDING = 12


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Prefer clearer Windows/UI fonts first, then fall back to Linux fonts.
    """
    if bold:
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold
            "C:/Windows/Fonts/arialbd.ttf",    # Arial Bold
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",    # Segoe UI
            "C:/Windows/Fonts/arial.ttf",      # Arial
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)

    return ImageFont.load_default()


FONT_TITLE = _load_font(20, bold=True)
FONT_HEADER = _load_font(16, bold=True)
FONT_BODY = _load_font(16, bold=False)
FONT_BODY_BOLD = _load_font(16, bold=True)
FONT_SMALL = _load_font(13, bold=False)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, font) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text

    suffix = "..."
    for i in range(len(text), 0, -1):
        candidate = text[:i].rstrip() + suffix
        if draw.textlength(candidate, font=font) <= max_width:
            return candidate

    return suffix


def _format_raid_label(start_ts: int) -> str:
    if not start_ts:
        return "?"
    try:
        dt = datetime.fromtimestamp(start_ts)
        return f"{dt.strftime('%a')} {dt.day}/{dt.month}"
    except Exception:
        return "?"


def _cell_color(status: str | None) -> str:
    return STATUS_COLORS.get(status, STATUS_COLORS["unknown"])


def _attendance_pct_color(pct: int) -> str:
    if pct >= 90:
        return "#4ade80"
    if pct >= 75:
        return "#facc15"
    return "#f87171"


def _draw_centered_text(draw, xy_box, text, font, fill):
    x1, y1, x2, y2 = xy_box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x1 + ((x2 - x1) - tw) / 2
    ty = y1 + ((y2 - y1) - th) / 2 - 1
    draw.text((tx, ty), text, font=font, fill=fill)


def render_attendance_report_image(
    guild_id: int | str,
    *,
    finalized_only: bool = True,
    limit_raids: int | None = 12,
    title: str | None = None,
) -> BytesIO:
    matrix = build_attendance_matrix(
        guild_id,
        finalized_only=finalized_only,
        limit_raids=limit_raids,
    )
    stats = get_attendance_overview_stats(matrix)

    raids = matrix.get("raids", [])
    players = matrix.get("players", [])

    title_text = title or "Attendance"
    subtitle = (
        f"Raids: {stats['raid_count']}  •  "
        f"Players: {stats['player_count']}  •  "
        f"Avg Att%: {stats['average_attendance_pct']}%"
    )

    width = (
        LEFT_PADDING
        + LEFT_NAME_WIDTH
        + PCT_WIDTH
        + (len(raids) * CELL_WIDTH)
        + RIGHT_PADDING
    )
    height = (
        TOP_TITLE_HEIGHT
        + HEADER_HEIGHT
        + (len(players) * ROW_HEIGHT)
        + BOTTOM_PADDING
    )

    width = max(width, 560)
    height = max(height, 180)

    image = Image.new("RGB", (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    # Title
    draw.text((LEFT_PADDING, 6), title_text, font=FONT_TITLE, fill=TEXT_PRIMARY)
    draw.text((LEFT_PADDING, 26), subtitle, font=FONT_SMALL, fill=TEXT_MUTED)

    table_top = TOP_TITLE_HEIGHT
    header_y1 = table_top
    header_y2 = table_top + HEADER_HEIGHT

    # Header background
    draw.rectangle(
        [0, header_y1, width, header_y2],
        fill=HEADER_BG,
        outline=GRID_BORDER,
    )

    x = LEFT_PADDING

    # Name header
    draw.rectangle(
        [x, header_y1, x + LEFT_NAME_WIDTH, header_y2],
        fill=HEADER_BG,
        outline=GRID_BORDER,
    )
    _draw_centered_text(
        draw,
        (x, header_y1, x + LEFT_NAME_WIDTH, header_y2),
        "Name",
        FONT_HEADER,
        TEXT_PRIMARY,
    )
    x += LEFT_NAME_WIDTH

    # Att% header
    draw.rectangle(
        [x, header_y1, x + PCT_WIDTH, header_y2],
        fill=HEADER_BG,
        outline=GRID_BORDER,
    )
    _draw_centered_text(
        draw,
        (x, header_y1, x + PCT_WIDTH, header_y2),
        "Att%",
        FONT_HEADER,
        TEXT_PRIMARY,
    )
    x += PCT_WIDTH

    # Raid headers
    for raid in raids:
        draw.rectangle(
            [x, header_y1, x + CELL_WIDTH, header_y2],
            fill=HEADER_BG,
            outline=GRID_BORDER,
        )

        label = _fit_text(
            draw,
            _format_raid_label(raid.get("start_ts", 0)),
            CELL_WIDTH - 6,
            FONT_SMALL,
        )

        _draw_centered_text(
            draw,
            (x, header_y1, x + CELL_WIDTH, header_y2),
            label,
            FONT_SMALL,
            TEXT_PRIMARY,
        )
        x += CELL_WIDTH

    # Body rows
    start_y = header_y2
    for index, player in enumerate(players):
        row_y1 = start_y + (index * ROW_HEIGHT)
        row_y2 = row_y1 + ROW_HEIGHT

        row_bg = ROW_ALT_1 if index % 2 == 0 else ROW_ALT_2

        x = LEFT_PADDING

        # Name cell
        draw.rectangle(
            [x, row_y1, x + LEFT_NAME_WIDTH, row_y2],
            fill=row_bg,
            outline=GRID_BORDER,
        )
        display_name = _fit_text(
            draw,
            player.get("name", "Unknown"),
            LEFT_NAME_WIDTH - 10,
            FONT_BODY,
        )
        draw.text(
            (x + 8, row_y1 + 8),
            display_name,
            font=FONT_BODY,
            fill=TEXT_PRIMARY,
        )
        x += LEFT_NAME_WIDTH

        # Attendance %
        draw.rectangle(
            [x, row_y1, x + PCT_WIDTH, row_y2],
            fill=row_bg,
            outline=GRID_BORDER,
        )
        pct = int(player.get("attendance_pct", 0))
        _draw_centered_text(
            draw,
            (x, row_y1, x + PCT_WIDTH, row_y2),
            f"{pct}%",
            FONT_BODY_BOLD,
            _attendance_pct_color(pct),
        )
        x += PCT_WIDTH

        # Raid status cells
        raid_statuses = player.get("raid_statuses", {})
        for raid in raids:
            raid_id = str(raid.get("raid_id"))
            status = raid_statuses.get(raid_id)
            color = _cell_color(status)

            draw.rectangle(
                [x, row_y1, x + CELL_WIDTH, row_y2],
                fill=color,
                outline=GRID_BORDER,
            )
            x += CELL_WIDTH

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output