# uts-event-bot

A GitHub Actions-based bot that automatically delivers UTS campus events, IT job listings, and academic calendar updates to a Discord server for UTS Korean international students.

## Features

- **Weekly UTS Events** — Scrapes [ActivateUTS](https://www.activateuts.com.au/events/) and posts next week's events every Monday at 10am Sydney time
- **Weekly IT Jobs** — Scrapes [Prosple](https://au.prosple.com) for new Sydney-based IT graduate roles and internships
- **Monthly Academic Calendar** — Posts UTS academic dates on the 1st of every month
- **Deduplication** — Tracks sent items via GitHub Gist to avoid reposting

## Folder Structure

```
uts-event-bot/
├── scraper.py                    # Weekly entry point (events + jobs)
├── bots/
│   ├── acad_calendar.py          # Monthly academic calendar scraper
│   ├── uts_events.py             # ActivateUTS weekly events scraper
│   └── prosple.py                # Prosple IT jobs scraper
├── utils/
│   ├── dedupe.py                 # GitHub Gist-backed deduplication
│   └── notify.py                 # Admin webhook notifications
├── .github/
│   └── workflows/
│       ├── weekly_scraper.yml    # Runs every Monday 10am Sydney (AEST)
│       └── monthly_calendar.yml  # Runs 1st of every month
├── .env                          # Local environment variables (not committed)
├── requirements.txt
└── README.md
```

## GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `EVENTS_WEBHOOK_URL` | Discord webhook for #uts-events channel |
| `PROSPLE_WEBHOOK_URL` | Discord webhook for #jobs channel |
| `ACADEMIC_WEBHOOK_URL` | Discord webhook for #academic-calendar channel |
| `ADMIN_WEBHOOK_URL` | Discord webhook for admin alerts |
| `GIST_TOKEN` | GitHub Personal Access Token with `gist` scope |
| `GIST_ID` | ID of the Gist storing deduplication data |

## Local Setup

```bash
git clone https://github.com/yunas-son-dev/uts-event-bot.git
cd uts-event-bot

pip install -r requirements.txt
playwright install chromium

# Copy and fill in your environment variables
cp .env.example .env

# Dry run (prints output, sends nothing)
python scraper.py --dry-run
python bots/acad_calendar.py --dry-run
```

## Example Output

**Events**
```
🎉 Upcoming UTS Events Next Week!

📅 14 Apr | 📌 Playmakers Game Night
🔗 https://www.activateuts.com.au/events/playmakers-game-night/
📝 Chill hangout playing multiplayer games in our discord server.

📅 18 Apr | 📌 SKIBUTS Tennis Open 2026
🔗 https://www.activateuts.com.au/events/skibuts-tennis-open-2026/
```

**Jobs**
```
💼 New IT Graduate Jobs & Internships in Sydney!

🏢 Google Au | Software Engineering Intern
📍 Sydney, NSW
💰 AUD 80k–95k
🗓 Start: Nov 2026
🔗 https://au.prosple.com/...
```