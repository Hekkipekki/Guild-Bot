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


_BG = (17, 18, 20)
_PANEL = (28, 30, 33)
_HEADER = (45, 47, 51)
_GRID = (76, 79, 84)
_TEXT = (235, 235, 235)
_MUTED = (170, 173, 178)
_ROLE_ORDER = ("DPS", "Tank", "Healer")
_ROLE_LABELS = {"DPS": "Damage Dealers", "Tank": "Tanks", "Healer": "Healers"}


def render_player_ranking_graphic(
    result: WarcraftLogsPlayerPerformanceResult,
    *,
    max_bosses: int = 10,
) -> bytes:
    """Render a Warcraft Logs-style role and boss ranking table as PNG bytes."""

    bosses = _ordered_bosses(result.players)[:max_bosses]
    grouped = {
        role: tuple(player for player in result.player_summaries if player.role_category == role)
        for role in _ROLE_ORDER
    }

    name_width = 230
    avg_width = 80
    boss_width = 126
    margin = 28
    table_width = name_width + avg_width + boss_width * max(len(bosses), 1)
    width = margin * 2 + table_width

    title_height = 84
    section_gap = 28
    header_height = 58
    row_height = 42
    section_heights = [
        header_height + row_height * len(grouped[role]) + 34
        for role in _ROLE_ORDER
        if grouped[role]
    ]
    height = title_height + margin + sum(section_heights) + section_gap * max(len(section_heights) - 1, 0) + margin

    image = Image.new("RGB", (width, max(height, 260)), _BG)
    draw = ImageDraw.Draw(image)
    title_font = _font(28, bold=True)
    section_font = _font(22, bold=True)
    header_font = _font(15, bold=True)
    body_font = _font(17)
    body_bold = _font(17, bold=True)
    small_font = _font(13)

    draw.text((margin, 22), f"{result.report_title} — Player Rankings", fill=_TEXT, font=title_font)
    draw.text(
        (margin, 57),
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
        y += 34
        _draw_header(draw, margin, y, bosses, name_width, avg_width, boss_width, header_height, header_font)
        y += header_height

        for player in players:
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
    labels = ["Name", "Avg"] + list(bosses or ("Bosses",))
    cursor = x
    for label, width in zip(labels, widths):
        draw.rectangle((cursor, y, cursor + width, y + height), fill=_HEADER, outline=_GRID)
        _draw_centered(draw, (cursor, y, cursor + width, y + height), _shorten(label, 17), font, _TEXT)
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
) -> None:
    draw.rectangle((x, y, x + name_width, y + height), fill=_PANEL, outline=_GRID)
    spec = f" ({player.primary_spec})" if player.primary_spec else ""
    draw.text((x + 10, y + 11), _shorten(player.name + spec, 25), fill=_TEXT, font=bold_font)

    cursor = x + name_width
    draw.rectangle((cursor, y, cursor + avg_width, y + height), fill=_PANEL, outline=_GRID)
    avg_text = "—" if player.average_parse is None else f"{player.average_parse:.0f}"
    _draw_centered(draw, (cursor, y, cursor + avg_width, y + height), avg_text, bold_font, _parse_color(player.average_parse))
    cursor += avg_width

    rows_by_boss = _best_rows_by_boss(player.rows)
    for boss in bosses or ("Bosses",):
        draw.rectangle((cursor, y, cursor + boss_width, y + height), fill=_PANEL, outline=_GRID)
        row = rows_by_boss.get(boss.casefold())
        text = "—" if row is None or row.rank_percent is None else f"{row.rank_percent:.0f}"
        _draw_centered(
            draw,
            (cursor, y, cursor + boss_width, y + height),
            text,
            font,
            _parse_color(None if row is None else row.rank_percent),
        )
        cursor += boss_width


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
        return (229, 204, 128)
    if value >= 95:
        return (255, 128, 0)
    if value >= 75:
        return (163, 53, 238)
    if value >= 50:
        return (0, 112, 255)
    if value >= 25:
        return (30, 255, 0)
    return (102, 102, 102)


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
