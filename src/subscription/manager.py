"""Subscription manager - CRUD operations for monitored channels/chats."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from telethon import TelegramClient

from src.core.types import MediaType, SubscriptionConfig, SubscriptionStatus
from src.database.db import DatabaseManager
from src.resolver.resolver import MediaResolver

logger = logging.getLogger("telegram_downloader.subscription")


class SubscriptionManager:
    """Manages subscriptions to Telegram channels and chats.

    Provides CRUD operations for subscriptions. Each subscription
    represents a channel or chat to monitor for new media.
    """

    def __init__(
        self,
        client: TelegramClient,
        db: DatabaseManager,
    ) -> None:
        self.client = client
        self.db = db
        self._resolver = MediaResolver(client)

    async def add(
        self,
        chat_id: int | str,
        media_types: list[MediaType] | None = None,
        min_file_size: int | None = None,
        max_file_size: int | None = None,
    ) -> SubscriptionConfig:
        """Add a new subscription.

        Args:
            chat_id: Numeric ID or username (e.g., '@channel_name').
            media_types: Types of media to download. Default: video + image.
            min_file_size: Minimum file size filter (bytes).
            max_file_size: Maximum file size filter (bytes).

        Returns:
            The created SubscriptionConfig.

        Raises:
            ValueError: If chat is not found or already subscribed.
        """
        # Resolve chat info
        chat_info = await self._resolver.get_chat_info(chat_id)
        if not chat_info:
            raise ValueError(f"Chat not found: {chat_id}")

        numeric_id = chat_info["id"]

        # Check for existing subscription
        existing = await self.db.get_subscription(numeric_id)
        if existing:
            raise ValueError(
                f"Already subscribed to {chat_info['title']} (id={numeric_id})"
            )

        if media_types is None:
            media_types = [MediaType.VIDEO, MediaType.IMAGE]

        sub = SubscriptionConfig(
            id=str(uuid.uuid4())[:8],
            chat_id=numeric_id,
            chat_title=chat_info.get("title"),
            chat_username=chat_info.get("username"),
            media_types=media_types,
            min_file_size=min_file_size,
            max_file_size=max_file_size,
        )

        await self.db.add_subscription(sub)
        logger.info("Subscribed to %s (id=%d)", sub.chat_title, sub.chat_id)
        return sub

    async def remove(self, chat_id: int | str) -> bool:
        """Remove a subscription.

        Args:
            chat_id: Numeric ID or username.

        Returns:
            True if subscription was found and removed.
        """
        # Resolve username to ID if needed
        if isinstance(chat_id, str):
            chat_info = await self._resolver.get_chat_info(chat_id)
            if not chat_info:
                return False
            chat_id = chat_info["id"]

        removed = await self.db.remove_subscription(chat_id)
        if removed:
            logger.info("Unsubscribed from chat %d", chat_id)
        return removed

    async def pause(self, chat_id: int) -> None:
        """Pause a subscription (stop checking for new media)."""
        await self.db.update_subscription_status(chat_id, SubscriptionStatus.PAUSED)
        logger.info("Paused subscription for chat %d", chat_id)

    async def resume(self, chat_id: int) -> None:
        """Resume a paused subscription."""
        await self.db.update_subscription_status(chat_id, SubscriptionStatus.ACTIVE)
        logger.info("Resumed subscription for chat %d", chat_id)

    async def list_all(self) -> list[SubscriptionConfig]:
        """Get all subscriptions."""
        return await self.db.get_all_subscriptions()

    async def list_active(self) -> list[SubscriptionConfig]:
        """Get active subscriptions only."""
        return await self.db.get_active_subscriptions()

    async def get(self, chat_id: int) -> SubscriptionConfig | None:
        """Get a specific subscription by chat ID."""
        return await self.db.get_subscription(chat_id)

    async def update(
        self,
        chat_id: int,
        media_types: list[MediaType] | None = None,
        min_file_size: int | None = None,
        max_file_size: int | None = None,
    ) -> SubscriptionConfig | None:
        """Update subscription settings.

        Returns the updated subscription, or None if not found.
        """
        sub = await self.db.get_subscription(chat_id)
        if not sub:
            return None

        if media_types is not None:
            sub.media_types = media_types
        if min_file_size is not None:
            sub.min_file_size = min_file_size
        if max_file_size is not None:
            sub.max_file_size = max_file_size

        sub.updated_at = datetime.now()
        await self.db.add_subscription(sub)
        logger.info("Updated subscription for chat %d", chat_id)
        return sub
