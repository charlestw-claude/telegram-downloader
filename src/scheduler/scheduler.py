"""Download scheduler - periodic subscription checks for new media."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from telethon import TelegramClient

from src.core.types import SubscriptionConfig, SubscriptionStatus
from src.database.db import DatabaseManager
from src.queue.download_queue import DownloadQueue
from src.resolver.resolver import MediaResolver

logger = logging.getLogger("telegram_downloader.scheduler")


class DownloadScheduler:
    """Periodically checks subscribed channels/chats for new media.

    Runs a background loop that:
    1. Gets all active subscriptions
    2. Scans each for new messages since last check
    3. Enqueues found media into the download queue
    """

    def __init__(
        self,
        client: TelegramClient,
        db: DatabaseManager,
        queue: DownloadQueue,
        check_interval: int = 300,
        error_retry_interval: int = 3,
    ) -> None:
        self.client = client
        self.db = db
        self.queue = queue
        self.check_interval = check_interval
        self.error_retry_interval = error_retry_interval

        self._resolver = MediaResolver(client)
        self._running = False
        self._task: asyncio.Task | None = None
        self._error_counts: dict[int, int] = {}  # chat_id -> consecutive error count
        self._check_cycle: int = 0

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (interval=%ds)", self.check_interval)

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def check_now(self) -> int:
        """Run an immediate check on all active subscriptions.

        Also retries errored subscriptions periodically.
        Returns total number of new media items enqueued.
        """
        self._check_cycle += 1

        subs = await self.db.get_active_subscriptions()

        # Periodically retry errored subscriptions
        if self._check_cycle % self.error_retry_interval == 0:
            errored = await self.db.get_all_subscriptions()
            for sub in errored:
                if sub.status == SubscriptionStatus.ERROR:
                    logger.info(
                        "Auto-retrying errored subscription: %s (chat_id=%d)",
                        sub.chat_title,
                        sub.chat_id,
                    )
                    await self.db.update_subscription_status(
                        sub.chat_id, SubscriptionStatus.ACTIVE
                    )
                    subs.append(sub)

        if not subs:
            logger.info("No active subscriptions to check")
            return 0

        total_enqueued = 0
        for sub in subs:
            count = await self._check_subscription(sub)
            total_enqueued += count

        logger.info("Check complete: %d new items enqueued", total_enqueued)
        return total_enqueued

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self.check_now()
            except Exception as e:
                logger.error("Scheduler check failed: %s", e)

            # Wait for next interval
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    async def _check_subscription(self, sub: SubscriptionConfig) -> int:
        """Check a single subscription for new media.

        Returns number of items enqueued.
        """
        try:
            logger.debug(
                "Checking subscription: %s (chat_id=%d, last_msg=%s)",
                sub.chat_title,
                sub.chat_id,
                sub.last_checked_message_id,
            )

            items = await self._resolver.resolve_chat(
                chat_id=sub.chat_id,
                media_types=sub.media_types,
                min_id=sub.last_checked_message_id,
                min_file_size=sub.min_file_size,
                max_file_size=sub.max_file_size,
            )

            if not items:
                return 0

            # Enqueue items
            task_ids = await self.queue.enqueue_many(items)

            # Update last checked message ID to the highest found
            max_msg_id = max(item.message_id for item in items)
            await self.db.update_last_checked(sub.chat_id, max_msg_id)

            logger.info(
                "Subscription %s: found %d items, enqueued %d new",
                sub.chat_title,
                len(items),
                len(task_ids),
            )
            return len(task_ids)

        except Exception as e:
            logger.error(
                "Failed to check subscription %s (chat_id=%d): %s",
                sub.chat_title,
                sub.chat_id,
                e,
            )
            await self.db.update_subscription_status(
                sub.chat_id, SubscriptionStatus.ERROR
            )
            return 0

    @property
    def is_running(self) -> bool:
        return self._running
