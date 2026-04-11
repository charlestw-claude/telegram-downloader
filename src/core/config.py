"""Application configuration management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration loaded from environment and defaults."""

    # Telegram API
    api_id: int = 0
    api_hash: str = ""
    phone: str | None = None
    session_name: str = "telegram_downloader"

    # Paths
    download_path: Path = field(default_factory=lambda: Path("./downloads"))
    db_path: Path = field(default_factory=lambda: Path("./telegram_downloader.db"))
    log_dir: Path = field(default_factory=lambda: Path("./logs"))

    # Download settings
    max_concurrent_downloads: int = 3
    max_retries: int = 3
    retry_delay: float = 5.0  # seconds

    # Scheduler
    check_interval: int = 300  # seconds (5 minutes)

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> Config:
        """Load configuration from .env file and environment variables."""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        api_id_str = os.getenv("TELEGRAM_API_ID", "0")
        try:
            api_id = int(api_id_str)
        except ValueError:
            api_id = 0

        max_concurrent_str = os.getenv("MAX_CONCURRENT_DOWNLOADS", "3")
        try:
            max_concurrent = int(max_concurrent_str)
        except ValueError:
            max_concurrent = 3

        return cls(
            api_id=api_id,
            api_hash=os.getenv("TELEGRAM_API_HASH", ""),
            phone=os.getenv("TELEGRAM_PHONE"),
            download_path=Path(os.getenv("DOWNLOAD_PATH", "./downloads")),
            db_path=Path(os.getenv("DB_PATH", "./telegram_downloader.db")),
            log_dir=Path(os.getenv("LOG_DIR", "./logs")),
            max_concurrent_downloads=max_concurrent,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if not self.api_id:
            errors.append("TELEGRAM_API_ID is required")
        if not self.api_hash:
            errors.append("TELEGRAM_API_HASH is required")
        if self.max_concurrent_downloads < 1:
            errors.append("MAX_CONCURRENT_DOWNLOADS must be at least 1")
        if self.check_interval <= 0:
            errors.append("CHECK_INTERVAL must be positive")
        return errors

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
