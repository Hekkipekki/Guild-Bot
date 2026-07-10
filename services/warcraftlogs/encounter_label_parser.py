from __future__ import annotations

import re
from dataclasses import dataclass


_RAID_SIZE_PATTERN = re.compile(
    r"\s*\((?P<size>\d+)\s*(?:Player|Players|Man)\)\s*$",
    re.IGNORECASE,
)
_DIFFICULTIES = (
    "Mythic",
    "Heroic",
    "Normal",
    "Looking For Raid",
    "LFR",
)
_DIFFICULTY_PATTERN = re.compile(
    rf"\s+(?P<difficulty>{'|'.join(re.escape(value) for value in _DIFFICULTIES)})\s*$",
    re.IGNORECASE,
)
_DIFFICULTY_CANONICAL = {
    "mythic": "Mythic",
    "heroic": "Heroic",
    "normal": "Normal",
    "looking for raid": "Looking For Raid",
    "lfr": "Looking For Raid",
}


@dataclass(frozen=True)
class EncounterLabel:
    """Normalized encounter identity while preserving the Warcraft Logs label."""

    original_label: str
    encounter_name: str
    difficulty: str | None = None
    raid_size: int | None = None

    @property
    def display_label(self) -> str:
        return self.original_label


def parse_encounter_label(value: str | None) -> EncounterLabel:
    """Parse labels such as `Garrosh Hellscream Heroic (10 Player)`.

    Parsing is intentionally conservative: unknown suffixes remain part of the
    encounter name instead of being guessed as difficulty or raid size.
    """

    original = str(value or "").strip()
    if not original:
        return EncounterLabel(original_label="", encounter_name="Unknown encounter")

    remainder = original
    raid_size: int | None = None
    size_match = _RAID_SIZE_PATTERN.search(remainder)
    if size_match:
        raid_size = int(size_match.group("size"))
        remainder = remainder[: size_match.start()].rstrip()

    difficulty: str | None = None
    difficulty_match = _DIFFICULTY_PATTERN.search(remainder)
    if difficulty_match:
        raw_difficulty = difficulty_match.group("difficulty").lower()
        difficulty = _DIFFICULTY_CANONICAL[raw_difficulty]
        remainder = remainder[: difficulty_match.start()].rstrip()

    encounter_name = remainder or original
    return EncounterLabel(
        original_label=original,
        encounter_name=encounter_name,
        difficulty=difficulty,
        raid_size=raid_size,
    )
