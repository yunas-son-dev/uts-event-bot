# uts-event-bot

A GitHub Actions-based bot that automatically delivers UTS campus events, IT job listings, academic calendar updates, and rotating Discord invite links for the UTS Korean IT student community.

## Features

- Weekly UTS Events — Scrapes ActivateUTS and posts next week's events every Sunday
- Weekly IT Jobs — Scrapes Sydney-based IT graduate roles and internships from Prosple
- Monthly Academic Calendar — Posts important UTS academic dates on the 1st of every month
- Discord Invite Rotation — Automatically refreshes the latest invite link for onboarding
- Deduplication — Uses GitHub Gist to prevent duplicate event and job posts

## Folder Structure

```text
uts-event-bot/
├── scraper.py
├── bots/
│   ├── acad_calendar.py
│   ├── discord_invite.py
│   ├── prosple.py
│   └── uts_events.py
├── utils/
│   ├── dedupe.py
│   └── notify.py
├── .github/
│   └── workflows/
│       ├── monthly_calendar.yml
│       ├── refresh_discord_invite.yml
│       └── weekly_scraper.yml
├── requirements.txt
├── .gitignore
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