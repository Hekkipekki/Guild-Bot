# Guild Bot

Modern Discord raid management bot built for World of Warcraft guilds.

Guild Bot focuses on:
- Raid signups
- Raid compositions
- Attendance tracking
- Recurring raids
- Reminders
- WeakAura distribution
- Persistent interactive Discord UI

---

# Features

## Raid Signups
- Class/spec signup system
- Tank / Healer / DPS role tracking
- Bench / Late / Tentative / Absence statuses
- Persistent signup embeds
- Character saving per user

## Raid Builder
- Interactive `/raid` setup flow
- Title / description / leader editing
- Raid templates
- Recurring raids
- Automatic repost lifecycle

## Raid Composition
- Drag-style raid composition builder
- Group 1 / Group 2 / Bench support
- Attendance snapshot integration

## Attendance System
- WarcraftLogs-inspired attendance reports
- Automatic attendance snapshots from comps
- Attendance editing tools
- Visual attendance heatmap generation

## WeakAura Distribution
- Guild WeakAura panel support
- Multiple pack support
- Persistent WeakAura posts

## Multi Guild Support
- Per-guild configuration
- Separate raid teams/admins
- Separate WeakAura panels

---

# Tech Stack

- Python
- discord.py
- Pillow
- Matplotlib
- JSON persistence

---

# Installation

## Clone Repository

```bash
git clone https://github.com/Hekkipekki/Guild-Bot.git
cd Guild-Bot
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Create secrets_local.py

```python
TOKEN = "YOUR_DISCORD_BOT_TOKEN"

DEV_MODE = True or False

TEST_GUILD_ID = None or 'Server id'
```

## Start Bot

```bash
py bot.py
or click Start Bot.bat
```

---

# Development Setup

Recommended workflow:

```txt
Local Dev Bot
↓
GitHub
↓
PebbleHost Live Bot
```

## Local Development
- Separate DEV Discord bot
- Separate test server
- Unicode fallback emojis
- Guild-only command sync

## Live Deployment
- Hosted on PebbleHost
- Uses production Discord bot
- Uses application emojis
- Global command sync

---

# PebbleHost Deployment

1. Push latest changes to GitHub
2. Download latest repository ZIP
3. Upload to PebbleHost
4. Extract and overwrite files
5. Restart bot

Runtime files are intentionally excluded from Git:

```txt
data/signups.json
data/attendance.json
data/characters.json
data/guild_settings.json
data/raid_templates.json
secrets_local.py
```

---

# Commands

## Raid Commands

| Command | Description |
|---|---|
| `/raid` | Create raid signup |
| `/attendance` | Generate attendance report |
| `/setup` | Configure guild settings |

---

# Project Structure

```txt
cogs/       -> Slash commands & schedulers
services/   -> Business logic
views/      -> Discord UI views/buttons/modals
utils/      -> Shared helpers
data/       -> Runtime JSON storage
files/      -> WeakAura packs/assets
```

---

# Screenshots

_Add screenshots here later._

---

# Roadmap

- Web dashboard
- MySQL support
- Improved onboarding flow
- Raid analytics
- Multi-expansion support
- Guild recruitment tools

---

# License

Private project currently under active development.