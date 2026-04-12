# uts-event-bot
The UTS event bot notifies upcoming events everyweek to an internal discord server

# UTS Event Notifier Bot for Discord

A Discord bot that automatically fetches weekly event information from [ActivateUTS](https://www.activateuts.com.au/events/?orderby=featured) and posts them to your server. Ideal for UTS students to stay updated with campus events!

## Features

- Scrapes the latest events from ActivateUTS every week.
- Posts formatted messages to a designated Discord channel.
- Easy to customise and deploy on your own server.

## Folder Structure

uts-korean-student-bot/
├── main.py                      # ▶ common runner (routes to each bot)
├── main_uts_events.py           # UTS Events bot entry
├── main_prosple.py              # Prosple Jobs bot entry
├── bots/
│   ├── uts_events.py            # UTS events scraper (this week)
│   └── prosple.py               # Prosple jobs scraper
├── utils/
│   ├── dedupe.py
│   └── notify.py
├── sent/
│   ├── sent_events.json
│   └── sent_prosple.json
├── .github/
│   └── workflows/
│       └── weekly-bots.yml      # run both bots at Sun 10:00 Sydney
├── .env
├── .env.example
├── requirements.txt
└── README.md

## 📸 Example Output

🎉 Upcoming UTS Events This Week!

📆 6 Aug | 📌 Free Coffee at The Loft
🔗 https://www.activateuts.com.au/events/free-coffee-the-loft

📆 7 Aug | 📌 Board Games & Pizza Night
🔗 https://www.activateuts.com.au/events/board-games-night


## 🔧 Setup

### 1. Clone the repository

```bash
git clone https://github.com/yunas-son-dev/uts-event-bot.git
cd uts-event-bot


