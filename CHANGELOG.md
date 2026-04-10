# Changelog

## [0.2.0] - 2026-04-10
### Added
- CLI `pause` command to pause subscription monitoring
- CLI `resume` command to resume paused subscriptions
- CLI `history` command with download record viewing, filtering, and export (CSV/JSON)
- `--min-size` / `--max-size` options for download and subscribe commands
- Rich progress bars with download speed and file size display
- Scan timeout (default 300s) for resolver to prevent hangs on large channels
- Auto-recovery for errored subscriptions in scheduler
- Unit tests for core types, config, database, and downloader modules

### Fixed
- Replace deprecated `asyncio.get_event_loop()` with `asyncio.run()`
- Fix variable shadowing in downloader progress callback
- Add phone number prompt fallback when TELEGRAM_PHONE is not set
- Use enum comparisons instead of fragile string comparisons
- Use full UUID for task IDs instead of truncated 8-char version
- Fix semaphore private attribute access in queue active count
- Fix possibly-undefined variable in download retry loop

### Changed
- Remove unused `aiofiles` dependency

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
