# telegram-downloader

Auto-download, subscribe, and manage videos & images from Telegram channels and chats.

## Features

- **Download**: One-shot download of all media from a chat/channel
- **Subscribe**: Auto-monitor channels for new media
- **Queue**: Concurrent downloads with retry logic
- **Organize**: Files saved by sender ID (`downloads/{sender_id}/videos/` and `images/`)
- **Dedup**: Skip already-downloaded files

## Quick Start

### 1. Get Telegram API Credentials

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps)
2. Create an application
3. Note your `api_id` and `api_hash`

### 2. Install

```bash
git clone https://github.com/charlestw-claude/telegram-downloader.git
cd telegram-downloader
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API credentials
```

### 4. Use

```bash
# Download media from a channel
telegram-dl download @channel_name

# Subscribe to a channel
telegram-dl subscribe @channel_name

# List subscriptions
telegram-dl list

# Start auto-download daemon
telegram-dl run

# Show status
telegram-dl status
```

## Requirements

- Python 3.10+
- Telegram API credentials (api_id + api_hash)

## License

MIT
