import random
import time


FAKE_NAMES = [
    "Thorgrim", "Leafhealz", "Shadowzap", "Bonkadin", "Totemlord",
    "Frostzug", "Moonbeef", "Sneakstab", "Pyroblastz", "Soulrot",
    "Mendrina", "Bearjuice", "Shockbot", "Arrowqt", "Smitey",
    "Hexella", "Clawbert", "Shieldbro", "Dotsdot", "Windbonk",
    "Holytoast", "Darkmoo", "Stonepaw", "Critlord", "Glimmer",
]


def build_fake_users() -> dict:
    tanks = [
        ("Death Knight", "Blood", "Tank"),
        ("Warrior", "ProtectionWarrior", "Tank"),
        ("Druid", "Guardian", "Tank"),
        ("Paladin", "ProtectionPaladin", "Tank"),
        ("Monk", "Brewmaster", "Tank"),
    ]

    healers = [
        ("Paladin", "HolyPaladin", "Healer"),
        ("Druid", "RestorationDruid", "Healer"),
        ("Priest", "Discipline", "Healer"),
        ("Priest", "HolyPriest", "Healer"),
        ("Shaman", "RestorationShaman", "Healer"),
        ("Monk", "Mistweaver", "Healer"),
    ]

    dps = [
        ("Warrior", "Arms", "Melee"),
        ("Warrior", "Fury", "Melee"),
        ("Druid", "Balance", "Ranged"),
        ("Druid", "Feral", "Melee"),
        ("Paladin", "Retribution", "Melee"),
        ("Monk", "Windwalker", "Melee"),
        ("Priest", "Shadow", "Ranged"),
        ("Mage", "Arcane", "Ranged"),
        ("Mage", "Fire", "Ranged"),
        ("Mage", "Frost", "Ranged"),
        ("Warlock", "Affliction", "Ranged"),
        ("Warlock", "Demonology", "Ranged"),
        ("Warlock", "Destruction", "Ranged"),
        ("Hunter", "Beast Mastery", "Ranged"),
        ("Hunter", "Marksmanship", "Ranged"),
        ("Hunter", "Survival", "Ranged"),
        ("Rogue", "Assassination", "Melee"),
        ("Rogue", "Combat", "Melee"),
        ("Rogue", "Subtlety", "Melee"),
        ("Shaman", "Elemental", "Ranged"),
        ("Shaman", "Enhancement", "Melee"),
        ("Death Knight", "FrostDK", "Melee"),
        ("Death Knight", "Unholy", "Melee"),
    ]

    # 10 signed + 4 extras = 12 total users
    tank_count = 2
    healer_count = 3
    dps_count = 5

    selected_tanks = random.sample(tanks, k=tank_count)
    selected_healers = random.sample(healers, k=healer_count)
    selected_dps = random.sample(dps, k=dps_count)

    selected_players = (
        [("sign", player) for player in selected_tanks]
        + [("sign", player) for player in selected_healers]
        + [("sign", player) for player in selected_dps]
    )

    extra_statuses = ["late", "tentative", "absence", "bench"]
    extra_pool = random.sample(dps + healers + tanks, k=4)

    selected_players += list(zip(extra_statuses, extra_pool))

    used_names = random.sample(FAKE_NAMES, k=len(selected_players))

    users = {}
    now = time.time()

    for i, (status, (player_class, spec, role)) in enumerate(selected_players):
        fake_user_id = f"demo_{i}"
        users[fake_user_id] = {
            "display_name": used_names[i],
            "class": player_class,
            "spec": spec,
            "role": role,
            "status": status,
            "timestamp": now + i,
        }

    return users