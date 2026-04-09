# Changelog

## [0.1.0] - 2026-04-10
### Added
- Core types and configuration system with .env support
- Media downloader module (video, image, animation)
- Media resolver for extracting content from Telegram messages
- Subscription manager for channel/chat monitoring
- Download queue with concurrency control and retry logic
- Scheduler for periodic subscription checks
- SQLite database for persistent storage
- CLI interface with commands: download, subscribe, unsubscribe, list, status, run, config
- File organization by sender ID (downloads/{sender_id}/videos/ and images/)
- Automatic deduplication of downloads
