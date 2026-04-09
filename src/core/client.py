"""Telegram client wrapper for shared access."""

from __future__ import annotations

from telethon import TelegramClient

from src.core.config import Config


def create_client(config: Config) -> TelegramClient:
    """Create and return a TelegramClient instance."""
    return TelegramClient(
        config.session_name,
        config.api_id,
        config.api_hash,
    )
