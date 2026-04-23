# SMM Bot

Telegram bot for generating Instagram/TikTok content using Google Gemini AI.

## Features

- **3 account personas** — Travel, Kids Art, Dog
- **Post / Carousel / Reels** — format-aware captions, hashtags, overlay text
- **Reel formats** — Ken Burns, Fast cut, Hook+slides (auto-recommended by Gemini)
- **Photo filters** — Vintage, Bright, B&W, Warm, Cool
- **Text overlays** — Banner bottom, Banner top, Shadow style
- **YouTube CTA** — Kids Art account can append a topic-specific YouTube line
- **Cover generator** — `/cover` command creates a 9:16 reel cover with Impact font
- **Multi-key Gemini rotation** — cycles through API keys when daily quota is hit

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Choose account type and begin |
| `/cover` | Generate a reel cover image |

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` → `.env` and fill in your values:

```env
BOT_TOKEN=your_telegram_bot_token
GEMINI_API_KEYS=key1,key2,key3
```

Run:

```bash
python run.py
```

