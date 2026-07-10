from __future__ import annotations

import io
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from services.warcraftlogs.player_performance_service import (
    WarcraftLogsPlayerPerformance,
    WarcraftLogsPlayerPerformanceResult,
    WarcraftLogsPlayerSummary,
)

_BG = (15, 16, 18)
_PANEL = (29, 31, 35)
_PANEL_ALT = (35, 37, 42)
_HEADER = (51, 54, 60)
_GRID = (96, 100, 108)
_TEXT = (250, 250, 252)
_MUTED = (192, 195, 202)
_ROLE_ORDER = ("DPS", "Tank", "Healer")
_ROLE_LABELS = {"DPS": "Damage Dealers", "Tank": "Tanks", "Healer": "Healers"}
_ICON_DIR_CANDIDATES = ("assets", "images", "icons", "data/assets", "data/images")


def render_player_ranking_graphic(
    result: WarcraftLogsPlayerPerformanceResult,
    *,
    max_bosses: int = 10,
    bosses_per_panel: int = 5,
) -> bytes:
    """Render a Discord-readable ranking image using stacked boss panels.

    A single ten-boss table becomes too wide and Discord scales it down. Splitting
    bosses into stacked five-column panels keeps character names and parse values
    readable without opening the attachment separately.
    """

    bosses = _ordered_bosses(result.players)[:max_bosses]
    boss_panels = tuple(
        bosses[index : index + bosses_per_panel]
        for index in range(0, max(len(bosses), 1), bosses_per_panel)
    ) or ((),)
    grouped = {
        role: tuple(player for player in result.player_summaries if player.role_category == role)
        for role in _ROLE_ORDER
    }

    name_width = 330
    avg_width = 100
    boss_width = 170
    margin = 34
    table_width = name_width + avg_width + boss_width * bosses_per_panel
    width = margin * 2 + table_width

    title_height = 116
    panel_title_height = 38
    section_title_height = 42
    header_height = 86
    row_height = 72
    role_gap = 28
    panel_gap = 46

    panel_height = panel_title_height
    for role in _ROLE_ORDER:
        if grouped[role]:
            panel_height += section_title_height + header_height + row_height * len(grouped[role]) + role_gap
    height = title_height + len(boss_panels) * panel_height + panel_gap * max(len(boss_panels) - 1, 0) + margin

    image = Image.new("RGB", (width, max(height, 360)), _BG)
    draw = ImageDraw.Draw(image)
    title_font = _font(36, bold=True)
    subtitle_font = _font(18)
    panel_font = _font(22, bold=True)
    section_font = _font(25, bold=True)
    header_font = _font(18, bold=True)
    name_font = _font(23, bold=True)
    spec_font = _font(17, bold=True)
    parse_font = _font(24, bold=True)

    draw.text((margin, 24), f"{result.report_title} — Player Rankings", fill=_TEXT, font=title_font)
    draw.text(
        (margin, 76),
        "Average parse and boss-by-boss percentile • higher is better",
        fill=_MUTED,
        font=subtitle_font,
    )

    y = title_height
    total_panels = len(boss_panels)
    for panel_index, panel_bosses in enumerate(boss_panels, start=1):
        if total_panels > 1:
            draw.text(
                (margin, y),
                f"Bosses {panel_index} of {total_panels}",
                fill=_MUTED,
                font=panel_font,
            )
        y += panel_title_height

        for role in _ROLE_ORDER:
            players = grouped[role]
            if not players:
                continue
            draw.text((margin, y), _ROLE_LABELS[role], fill=_TEXT, font=section_font)
            y += section_title_height
            _draw_header(
                draw,
                margin,
                y,
                panel_bosses,
                name_width,
                avg_width,
                boss_width,
                bosses_per_panel,
                header_height,
                header_font,
            )
            y += header_height
            for index, player in enumerate(players):
                _draw_player_row(
                    image,
                    draw,
                    margin,
                    y,
                    player,
                    panel_bosses,
                    name_width,
                    avg_width,
                    boss_width,
                    bosses_per_panel,
                    row_height,
                    name_font,
                    spec_font,
                    parse_font,
                    alternate=bool(index % 2),
                )
                y += row_height
            y += role_gap
        y += panel_gap

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
    bosses_per_panel: int,
    height: int,
    font: ImageFont.ImageFont,
) -> None:
    labels = ["Player", "Avg", *bosses]
    while len(labels) < 2 + bosses_per_panel:
        labels.append("")
    widths = [name_width, avg_width] + [boss_width] * bosses_per_panel
    cursor = x
    for label, width in zip(labels, widths):
        draw.rectangle((cursor, y, cursor + width, y + height), fill=_HEADER, outline=_GRID, width=2)
        if label:
            _draw_multiline_centered(draw, (cursor, y, cursor + width, y + height), _header_lines(label), font, _TEXT)
        cursor += width


def _draw_player_row(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    player: WarcraftLogsPlayerSummary,
    bosses: tuple[str, ...],
    name_width: int,
    avg_width: int,
    boss_width: int,
    bosses_per_panel: int,
    height: int,
    name_font: ImageFont.ImageFont,
    spec_font: ImageFont.ImageFont,
    parse_font: ImageFont.ImageFont,
    *,
    alternate: bool,
) -> None:
    row_fill = _PANEL_ALT if alternate else _PANEL
    draw.rectangle((x, y, x + name_width, y + height), fill=row_fill, outline=_GRID, width=2)

    icon = _load_spec_icon(player.primary_spec, player.class_name, size=48)
    text_x = x + 16
    if icon is not None:
        image.paste(icon, (x + 12, y + (height - icon.height) // 2), icon)
        text_x = x + 72
    draw.text((text_x, y + 10), _shorten(player.name, 22), fill=_TEXT, font=name_font)
    identity = player.primary_spec or player.class_name or player.role_category
    draw.text((text_x, y + 42), _shorten(identity, 24), fill=_MUTED, font=spec_font)

    cursor = x + name_width
    _draw_parse_cell(draw, (cursor, y, cursor + avg_width, y + height), player.average_parse, parse_font, row_fill)
    cursor += avg_width

    rows_by_boss = _best_rows_by_boss(player.rows)
    for index in range(bosses_per_panel):
        boss = bosses[index] if index < len(bosses) else None
        row = rows_by_boss.get(boss.casefold()) if boss else None
        value = None if row is None else row.rank_percent
        _draw_parse_cell(draw, (cursor, y, cursor + boss_width, y + height), value, parse_font, row_fill)
        cursor += boss_width


def _draw_parse_cell(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: float | None,
    font: ImageFont.ImageFont,
    base_fill: tuple[int, int, int],
) -> None:
    draw.rectangle(box, fill=_parse_cell_fill(value, base_fill), outline=_GRID, width=2)
    text = "—" if value is None else f"{value:.0f}"
    _draw_centered(draw, box, text, font, _parse_color(value))


def _ordered_bosses(rows: Iterable[WarcraftLogsPlayerPerformance]) -> tuple[str, ...]:
    names = [row.encounter_name for row in rows if row.encounter_name]
    counts = Counter(names)
    order: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            order.append(name)
    order.sort(key=lambda name: (-counts[name], names.index(name)))
    return tuple(order)


def _best_rows_by_boss(rows: Iterable[WarcraftLogsPlayerPerformance]) -> dict[str, WarcraftLogsPlayerPerformance]:
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
        return (255, 225, 155)
    if value >= 95:
        return (255, 160, 45)
    if value >= 75:
        return (210, 125, 255)
    if value >= 50:
        return (90, 178, 255)
    if value >= 25:
        return (110, 255, 110)
    return (205, 207, 213)


def _parse_cell_fill(value: float | None, base_fill: tuple[int, int, int]) -> tuple[int, int, int]:
    if value is None:
        return base_fill
    accent = _parse_color(value)
    return tuple(int(base * 0.68 + color * 0.32) for base, color in zip(base_fill, accent))


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
    if len(value) <= 16:
        return (value,)
    words = value.split()
    midpoint = max(1, len(words) // 2)
    first = " ".join(words[:midpoint])
    second = " ".join(words[midpoint:])
    if len(first) <= 18 and len(second) <= 18:
        return (first, second)
    return (_shorten(value, 18),)


@lru_cache(maxsize=128)
def _load_spec_icon(spec_name: str | None, class_name: str | None, *, size: int) -> Image.Image | None:
    path = _find_spec_icon(spec_name, class_name)
    if path is None:
        return None
    try:
        icon = Image.open(path).convert("RGBA")
        icon.thumbnail((size, size), Image.Resampling.LANCZOS)
        return icon
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=128)
def _find_spec_icon(spec_name: str | None, class_name: str | None) -> Path | None:
    tokens = [_slug(spec_name), _slug(class_name)]
    tokens = [token for token in tokens if token]
    if not tokens:
        return None
    roots = [Path.cwd() / candidate for candidate in _ICON_DIR_CANDIDATES]
    extra_root = os.getenv("GUILD_BOT_ASSET_DIR")
    if extra_root:
        roots.insert(0, Path(extra_root))
    candidates: list[tuple[int, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.casefold() not in {".png", ".webp", ".jpg", ".jpeg"}:
                continue
            stem = _slug(path.stem)
            score = 0
            if tokens[0] and tokens[0] == stem:
                score += 100
            elif tokens[0] and tokens[0] in stem:
                score += 50
            if len(tokens) > 1 and tokens[1] and tokens[1] in stem:
                score += 10
            if score:
                candidates.append((score, path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _draw_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((left + (right - left - text_width) / 2, top + (bottom - top - text_height) / 2 - 2), text, fill=fill, font=font)


def _draw_multiline_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], lines: tuple[str, ...], font: ImageFont.ImageFont, fill: tuple[int, int, int]) -> None:
    left, top, right, bottom = box
    line_height = max(draw.textbbox((0, 0), line, font=font)[3] for line in lines)
    gap = 5
    total_height = line_height * len(lines) + gap * max(len(lines) - 1, 0)
    cursor_y = top + (bottom - top - total_height) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((left + (right - left - text_width) / 2, cursor_y), line, fill=fill, font=font)
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
