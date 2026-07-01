from pathlib import Path

# ============================================================
# Application config
# ============================================================
# Runtime/app-level settings belong here.
# Local/live secrets and environment flags belong in secrets_local.py.
#
# Local DEV secrets_local.py:
#   TOKEN = "DEV_TOKEN"
#   DEV_MODE = True
#   TEST_GUILD_ID = 123456789123456789
#
# PebbleHost LIVE secrets_local.py:
#   TOKEN = "LIVE_TOKEN"
#   DEV_MODE = False
#   TEST_GUILD_ID = None
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = BASE_DIR / "files"

try:
    from secrets_local import TOKEN
except ImportError:
    TOKEN = None

try:
    from secrets_local import DEV_MODE
except ImportError:
    DEV_MODE = False

try:
    from secrets_local import TEST_GUILD_ID
except ImportError:
    TEST_GUILD_ID = None


PACKS = {
    "SoO_01_08": {
        "label": "SoO Boss 1–8",
        "file": "files/Fojji-T1601-08-Siege-of-Orgrimmar_v3.0.2.txt",
        "title": "Fojji - Siege of Orgrimmar[01–08]",
        "version": "v3.0.2",
    },
    "SoO_09_14": {
        "label": "SoO Boss 9–14",
        "file": "files/Fojji-T1609-14-Siege-of-Orgrimmar-v3.0.5.txt",
        "title": "Fojji - Siege of Orgrimmar [09–14]",
        "version": "v3.0.5",
    },
    "SoO_frames": {
        "label": "Siege of Orgrimmar Raid Frames",
        "file": "files/Fojji-T16Raid_Frame_Siege_of_Orgrimmar-v3.0.2.txt",
        "title": "Fojji - Siege of Orgrimmar Raid Frames",
        "version": "v3.0.2",
    },
    "SoO_assignments": {
        "label": "Fojji - Raid Assignments [SOO][Raid Leader][1.0.0]",
        "file": "files/Fojji - Raid Assignments [SoO][Raid Leader][1.0.0].txt",
        "title": "Fojji - Raid Assignments [SOO][Raid Leader]",
        "version": "v1.0.0",
    },
}

CLASSES = [
    "Death Knight",
    "Warrior",
    "Druid",
    "Paladin",
    "Monk",
    "Priest",
    "Mage",
    "Warlock",
    "Hunter",
    "Rogue",
    "Shaman",
]

CLASS_SPECS = {
    "Death Knight": {
        "Blood": "Tank",
        "FrostDK": "Melee",
        "Unholy": "Melee",
    },
    "Warrior": {
        "Arms": "Melee",
        "Fury": "Melee",
        "ProtectionWarrior": "Tank",
    },
    "Druid": {
        "Balance": "Ranged",
        "Feral": "Melee",
        "Guardian": "Tank",
        "RestorationDruid": "Healer",
    },
    "Paladin": {
        "HolyPaladin": "Healer",
        "ProtectionPaladin": "Tank",
        "Retribution": "Melee",
    },
    "Monk": {
        "Brewmaster": "Tank",
        "Mistweaver": "Healer",
        "Windwalker": "Melee",
    },
    "Priest": {
        "Discipline": "Healer",
        "HolyPriest": "Healer",
        "Shadow": "Ranged",
    },
    "Mage": {
        "Arcane": "Ranged",
        "Fire": "Ranged",
        "Frost": "Ranged",
    },
    "Warlock": {
        "Affliction": "Ranged",
        "Demonology": "Ranged",
        "Destruction": "Ranged",
    },
    "Hunter": {
        "Beast Mastery": "Ranged",
        "Marksmanship": "Ranged",
        "Survival": "Ranged",
    },
    "Rogue": {
        "Assassination": "Melee",
        "Combat": "Melee",
        "Subtlety": "Melee",
    },
    "Shaman": {
        "Elemental": "Ranged",
        "Enhancement": "Melee",
        "RestorationShaman": "Healer",
    },
}

ROLE_LIMITS = {
    "Tank": 2,
    "Healer": 3,
    "DPS": 9,
}

SPEC_EMOJIS = {
    "Blood": "<:Blood:1482050758114414853>",
    "FrostDK": "<:FrostDK:1482050821133963305>",
    "Unholy": "<:Unholy:1482050820059959397>",
    "Balance": "<:Balance:1482050818885812345>",
    "Feral": "<:Feral:1482050817417674924>",
    "Guardian": "<:Guardian:1482050756889805000>",
    "RestorationDruid": "<:RestorationDruid:1482050816092278957>",
    "Beast Mastery": "<:BeastMastery:1482050810857652446>",
    "BeastMastery": "<:BeastMastery:1482050810857652446>",
    "Marksmanship": "<:Marksmanship:1482050812825043114>",
    "Survival": "<:Survival:1482050814041391194>",
    "Arcane": "<:Arcane:1482050791450611793>",
    "Fire": "<:Fire:1482050790100045824>",
    "Frost": "<:Frost:1482050788753805362>",
    "Brewmaster": "<:Brewmaster:1482050787323412602>",
    "Mistweaver": "<:Mistweaver:1482050786002337973>",
    "Windwalker": "<:Windwalker:1482050784941047891>",
    "HolyPaladin": "<:HolyPaladin:1482050797096271943>",
    "ProtectionPaladin": "<:ProtectionPaladin:1482050755899691138>",
    "Retribution": "<:Retribution:1482050799210332210>",
    "Discipline": "<:Discipline:1482050792696451193>",
    "HolyPriest": "<:HolyPriest:1482050794244276305>",
    "Shadow": "<:Shadow:1482050795737190611>",
    "Assassination": "<:Assassination:1482050781443133572>",
    "Combat": "<:Combat:1482050780000292955>",
    "Subtlety": "<:Sublety:1482050782445437070>",
    "Sublety": "<:Sublety:1482050782445437070>",
    "Elemental": "<:Elemental:1482050809712611328>",
    "Enhancement": "<:Enmhancement:1482050808647520396>",
    "Enmhancement": "<:Enmhancement:1482050808647520396>",
    "RestorationShaman": "<:RestorationShaman:1482050807674441779>",
    "Affliction": "<:Affliction:1482050800539799634>",
    "Demonology": "<:Demonology:1482050801928110181>",
    "Destruction": "<:Destruction:1482050802976690197>",
    "Arms": "<:Arms:1482050804503281868>",
    "Fury": "<:Fury:1482050806357168319>",
    "ProtectionWarrior": "<:ProtectionWarrior:1482050759561318400>",
}

CLASS_EMOJIS = {
    "Death Knight": "<:DEATHKNIGHT:1482050742767452448>",
    "Warrior": "<:WARRIOR:1482050753450344571>",
    "Druid": "<:DRUID:1482050743723884584>",
    "Paladin": "<:PALADIN:1482050746407977084>",
    "Monk": "<:MONK:1482050741060374649>",
    "Priest": "<:PRIEST:1482050747909800026>",
    "Mage": "<:MAGE:1482050754599588061>",
    "Warlock": "<:WARLOCK:1482050752208965754>",
    "Hunter": "<:HUNTER:1482050745325981696>",
    "Rogue": "<:ROGUE:1482050749776269443>",
    "Shaman": "<:SHAMAN:1482050751034560564>",
}

SUMMARY_EMOJIS = {
    "Countdown": "<:Countdown:1482050770453921883>",
    "Absence": "<:Absence:1482050771800555640>",
    "Signups": "<:Signups:1482050773616693449>",
    "DPS": "<:DPS:1482050775311192187>",
    "Tank": "<:Tank:1482050777060085960>",
    "Healer": "<:Healer:1482050778683277514>",
    "Tentative": "<:Tentative:1482050766704349334>",
    "Late": "<:Late:1482050767803121755>",
    "Calendar": "<:Calendar:1482050769015537794>",
    "Bench": "<:Bench:1482050765278412942>",
}

BUTTON_EMOJIS = {
    "sign": "<:Sign:1482050762912825414>",
    "late": "<:Late:1482050767803121755>",
    "note": "<:Signups:1482050773616693449>",
    "bench": "<:Bench:1482050765278412942>",
    "tentative": "<:Tentative:1482050766704349334>",
    "absence": "<:Absence:1482050771800555640>",
    "config": "<:Config:1482050761507471390>",
    "leave": "<:Leave:1482050763973988392>",
    "create_raid": "<:create_raid:1482050739625787581>",
    "create_template": "<:create_template:1482050738342461510>",
    "submit_raid": "<:submit_raid:1482050736840900701>",
    "cancel_raid": "<:cancel_raid:1482050734672314518>",
    "spec": "<:Config:1482050761507471390>",
    "attendance": "<:create_template:1482050738342461510>",
    "comp": "<:create_raid:1482050739625787581>",
}