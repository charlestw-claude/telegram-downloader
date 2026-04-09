# telegram-downloader — Project CLAUDE.md

## Project Overview

Telegram media downloader: auto-download, subscribe, and manage videos & images from Telegram channels and chats. Built with Python + Telethon.

## Tech Stack

- **Language**: Python 3.10+
- **Telegram API**: Telethon (User API)
- **Database**: SQLite (aiosqlite)
- **CLI**: Click + Rich
- **Config**: python-dotenv

## Architecture

Modular design with independently operable modules:

```
src/
├── core/           # Types, config, logger, client
├── downloader/     # Single media download (Telethon)
├── resolver/       # Message parsing, media extraction
├── subscription/   # Subscription CRUD management
├── scheduler/      # Periodic subscription checks
├── queue/          # Download queue with concurrency control
├── database/       # SQLite persistence
└── cli/            # Command-line interface
```

### Three-Layer Pattern (per charles-downloader)

1. **Resolver** → Extracts media from messages/channels
2. **Downloader** → Downloads single media files
3. **Manager** → Orchestrates via queue + scheduler

## Directory Structure for Downloads

```
downloads/
├── {sender_id}/
│   ├── videos/
│   └── images/
```

## Development

```bash
pip install -e ".[dev]"
```

## Sensitive Files

- `.env` — Telegram API credentials (never commit)
- `*.session` — Telethon session files (never commit)

<!-- snapshot: false -->
