from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AvoidableMechanic:
    boss_name: str
    ability_name: str
    aliases: tuple[str, ...] = ()

    @property
    def normalized_names(self) -> frozenset[str]:
        return frozenset(
            normalize_mechanic_name(value)
            for value in (self.ability_name, *self.aliases)
            if normalize_mechanic_name(value)
        )


# This registry is intentionally conservative. Only explicitly listed mechanics
# count toward avoidable DTPS. More encounters can be added without changing the
# event aggregation service.
_AVOIDABLE_MECHANICS: tuple[AvoidableMechanic, ...] = (
    AvoidableMechanic("Immerseus", "Swirl"),
    AvoidableMechanic("Immerseus", "Sha Corruption"),
    AvoidableMechanic("Fallen Protectors", "Noxious Poison"),
    AvoidableMechanic("Norushen", "Blind Hatred"),
    AvoidableMechanic("Sha of Pride", "Self-Reflection"),
    AvoidableMechanic("Sha of Pride", "Unstable Corruption"),
    AvoidableMechanic("Sha of Pride", "Ethereal Corruption"),
    AvoidableMechanic("Galakras", "Shadow Assault"),
    AvoidableMechanic("Iron Juggernaut", "Borer Drill"),
    AvoidableMechanic("Iron Juggernaut", "Cutter Laser"),
    AvoidableMechanic("Iron Juggernaut", "Demolisher Cannon"),
    AvoidableMechanic("Iron Juggernaut", "Mortar Blast"),
    AvoidableMechanic("Iron Juggernaut", "Ricochet", aliases=("Richochet",)),
    AvoidableMechanic("Kor'kron Dark Shaman", "Toxic Storm"),
    AvoidableMechanic("Kor'kron Dark Shaman", "Iron Tomb"),
    AvoidableMechanic("General Nazgrim", "Aftershock"),
)


def normalize_mechanic_name(value: str | None) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_boss_name(value: str | None) -> str:
    normalized = normalize_mechanic_name(value)
    aliases = {
        "the fallen protectors": "fallen protectors",
        "dark shamans": "kor kron dark shaman",
        "kor kron dark shamans": "kor kron dark shaman",
        "kor kron dark shaman": "kor kron dark shaman",
    }
    return aliases.get(normalized, normalized)


def mechanics_for_boss(boss_name: str | None) -> tuple[AvoidableMechanic, ...]:
    boss_key = normalize_boss_name(boss_name)
    return tuple(
        mechanic
        for mechanic in _AVOIDABLE_MECHANICS
        if normalize_boss_name(mechanic.boss_name) == boss_key
    )


def avoidable_ability_names(boss_name: str | None) -> frozenset[str]:
    names: set[str] = set()
    for mechanic in mechanics_for_boss(boss_name):
        names.update(mechanic.normalized_names)
    return frozenset(names)


def is_avoidable_damage(boss_name: str | None, ability_name: str | None) -> bool:
    ability_key = normalize_mechanic_name(ability_name)
    return bool(ability_key) and ability_key in avoidable_ability_names(boss_name)


def covered_bosses() -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for mechanic in _AVOIDABLE_MECHANICS:
        key = normalize_boss_name(mechanic.boss_name)
        if key in seen:
            continue
        seen.add(key)
        result.append(mechanic.boss_name)
    return tuple(result)
