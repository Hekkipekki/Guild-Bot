from __future__ import annotations

import io
from collections import Counter
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceResult,
    WarcraftLogsPlayerSummary,
)


_BG = (15, 16, 18)
_PANEL = (29, 31, 35)
_PANEL_ALT = (34, 36, 40)
_HEADER = (48, 51, 56)
_GRID = (83, 87, 94)
_TEXT = (244, 244, 245)
_MUTED = (183, 186, 192)
_ROLE_ORDER = ("DPS", "Tank", "Healer")
_ROLE_LABELS = {"DPS": "Damage Dealers", "Tank": "Tanks", "Healer": "Healers"}


def render_player_ranking_graphic(
    result: WarcraftLogsPlayerPerformanceResult,
    *,
    max_bosses: int = 10,
) -> bytes:
    """Render a readable Warcraft Logs-style role and boss ranking table."""

    bosses = _ordered_bosses(result.players)[:max_bosses]
    grouped = {
        role: tuple(player for player in result.player_summaries if player.role_category == role)
        for role in _ROLE_ORDER
    }

    name_width = 250
    avg_width = 82
    boss_width = 126
    margin = 30
    table_width = name_width + avg_width + boss_width * max(len(bosses), 1)
    width = margin * 2 + table_width

    title_height = 106
    section_gap = 34
    header_height = 74
    row_height = 56
    section_heights = [
        38 + header_height + row_height * len(grouped[role])
        for role in _ROLE_ORDER
        if grouped[role]
    ]
    height = (
        title_height
        + sum(section_heights)
        + section_gap * max(len(section_heights) - 1, 0)
        + margin
    )

    image = Image.new("RGB", (width, max(height, 300)), _BG)
    draw = ImageDraw.Draw(image)
    title_font = _font(32, bold=True)
    section_font = _font(23, bold=True)
    header_font = _font(17, bold=True)
    body_font = _font(20)
    body_bold = _font(20, bold=True)
    spec_font = _font(15)
    small_font = _font(16)

    draw.text(
        (margin, 22),
        f"{result.report_title} — Player Rankings",
        fill=_TEXT,
        font=title_font,
    )
    draw.text(
        (margin, 66),
        "Average parse and boss-by-boss percentile • higher is better",
        fill=_MUTED,
        font=small_font,
    )

    y = title_height
    for role in _ROLE_ORDER:
        players = grouped[role]
        if not players:
            continue

        draw.text((margin, y), _ROLE_LABELS[role], fill=_TEXT, font=section_font)
        y += 38
        _draw_header(
            draw,
            margin,
            y,
            bosses,
            name_width,
            avg_width,
            boss_width,
            header_height,
            header_font,
        )
        y += header_height

        for index, player in enumerate(players):
            _draw_player_row(
                draw,
                margin,
                y,
                player,
                bosses,
                name_width,
                avg_width,
                boss_width,
                row_height,
                body_font,
                body_bold,
                spec_font,
                alternate=bool(index % 2),
            )
            y += row_height

        y += section_gap

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _draw_header(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    bosses: tuple[str, ...],
    name_width: int,
    avg_width: int,
    boss_width: int,
    height: int,
    font: ImageFont.ImageFont,
) -> None:
    widths = [name_width, avg_width] + [boss_width] * max(len(bosses), 1)
    labels = ["Player", "Avg"] + list(bosses or ("Bosses",))
    cursor = x
    for label, width in zip(labels, widths):
        draw.rectangle((cursor, y, cursor + width, y + height), fill=_HEADER, outline=_GRID)
        _draw_multiline_centered(
            draw,
            (cursor, y, cursor + width, y + height),
            _header_lines(label),
            font,
            _TEXT,
        )
        cursor += width


def _draw_player_row(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    player: WarcraftLogsPlayerSummary,
    bosses: tuple[str, ...],
    name_width: int,
    avg_width: int,
    boss_width: int,
    height: int,
    font: ImageFont.ImageFont,
    bold_font: ImageFont.ImageFont,
    spec_font: ImageFont.ImageFont,
    *,
    alternate: bool,
) -> None:
    row_fill = _PANEL_ALT if alternate else _PANEL
    draw.rectangle((x, y, x + name_width, y + height), fill=row_fill, outline=_GRID)
    draw.text((x + 12, y + 8), _shorten(player.name, 22), fill=_TEXT, font=bold_font)
    identity = player.primary_spec or player.class_name or player.role_category
    draw.text((x + 12, y + 33), _shorten(identity, 25), fill=_MUTED, font=spec_font)

    cursor = x + name_width
    _draw_parse_cell(
        draw,
        (cursor, y, cursor + avg_width, y + height),
        player.average_parse,
        bold_font,
        base_fill=row_fill,
    )
    cursor += avg_width

    rows_by_boss = _best_rows_by_boss(player.rows)
    for boss in bosses or ("Bosses",):
        row = rows_by_boss.get(boss.casefold())
        value = None if row is None else row.rank_percent
        _draw_parse_cell(
            draw,
            (cursor, y, cursor + boss_width, y + height),
            value,
            font,
            base_fill=row_fill,
        )
        cursor += boss_width


def _draw_parse_cell(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: float | None,
    font: ImageFont.ImageFont,
    *,
    base_fill: tuple[int, int, int],
) -> None:
    fill = _parse_cell_fill(value, base_fill)
    draw.rectangle(box, fill=fill, outline=_GRID)
    text = "—" if value is None else f"{value:.0f}"
    _draw_centered(draw, box, text, font, _parse_color(value))


def _ordered_bosses(rows: Iterable[WarcraftLogsPlayerPerformance]) -> tuple[str, ...]:
    names = [row.encounter_name for row in rows if row.encounter_name]
    counts = Counter(names)
    order: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        order.append(name)
    order.sort(key=lambda name: (-counts[name], names.index(name)))
    return tuple(order)


def _best_rows_by_boss(
    rows: Iterable[WarcraftLogsPlayerPerformance],
) -> dict[str, WarcraftLogsPlayerPerformance]:
    result: dict[str, WarcraftLogsPlayerPerformance] = {}
    for row in rows:
        if not row.encounter_name:
            continue
        key = row.encounter_name.casefold()
        current = result.get(key)
        if current is None or (row.rank_percent or -1) > (current.rank_percent or -1):
            result[key] = row
    return result


def _parse_color(value: float | None) -> tuple[int, int, int]:
    if value is None:
        return _MUTED
    if value >= 99:
        return (255, 222, 145)
    if value >= 95:
        return (255, 145, 35)
    if value >= 75:
        return (193, 103, 255)
    if value >= 50:
        return (62, 155, 255)
    if value >= 25:
        return (85, 255, 85)
    return (155, 158, 164)


def _parse_cell_fill(
    value: float | None,
    base_fill: tuple[int, int, int],
) -> tuple[int, int, int]:
    if value is None:
        return base_fill
    accent = _parse_color(value)
    # Keep the table dark while giving each parse band a visible cell tint.
    return tuple(int(base * 0.78 + color * 0.22) for base, color in zip(base_fill, accent))


def _header_lines(value: str) -> tuple[str, ...]:
    aliases = {
        "Kor'kron Dark Shaman": ("Kor'kron", "Dark Shaman"),
        "Fallen Protectors": ("Fallen", "Protectors"),
        "Iron Juggernaut": ("Iron", "Juggernaut"),
        "General Nazgrim": ("General", "Nazgrim"),
        "Sha of Pride": ("Sha of", "Pride"),
    }
    if value in aliases:
        return aliases[value]
    if len(value) <= 14:
        return (value,)
    words = value.split()
    if len(words) >= 2:
        midpoint = max(1, len(words) // 2)
        first = " ".join(words[:midpoint])
        second = " ".join(words[midpoint:])
        if len(first) <= 15 and len(second) <= 15:
            return (first, second)
    return (_shorten(value, 15),)


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(
        (left + (right - left - width) / 2, top + (bottom - top - height) / 2 - 1),
        text,
        fill=fill,
        font=font,
    )


def _draw_multiline_centered(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    lines: tuple[str, ...],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    left, top, right, bottom = box
    line_height = max(draw.textbbox((0, 0), line, font=font)[3] for line in lines)
    gap = 4
    total_height = line_height * len(lines) + gap * max(len(lines) - 1, 0)
    cursor_y = top + (bottom - top - total_height) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (left + (right - left - text_width) / 2, cursor_y),
            line,
            fill=fill,
            font=font,
        )
        cursor_y += line_height + gap


def _shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(limit - 1, 1)] + "…"


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
