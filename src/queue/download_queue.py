"""Download queue - manages concurrent downloads with retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from src.core.types import (
    DownloadProgress,
    DownloadResult,
    DownloadStatus,
    MediaItem,
    MediaType,
)
from src.database.db import DatabaseManager
from src.downloader.downloader import MediaDownloader

logger = logging.getLogger("telegram_downloader.queue")

# Event callbacks
OnProgressCallback = Callable[[DownloadProgress], None]
OnCompleteCallback = Callable[[DownloadResult], None]


class DownloadQueue:
    """Manages download tasks with concurrency control and retry logic.

    Features:
    - Configurable concurrent download limit
    - Automatic retry with configurable delay
    - Deduplication via database checks
    - Progress and completion callbacks
    """

    def __init__(
        self,
        downloader: MediaDownloader,
        db: DatabaseManager,
        max_concurrent: int = 3,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        self.downloader = downloader
        self.db = db
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._on_progress: OnProgressCallback | None = None
        self._on_complete: OnCompleteCallback | None = None
        self._running = False

    def on_progress(self, callback: OnProgressCallback) -> None:
        """Register a progress callback."""
        self._on_progress = callback

    def on_complete(self, callback: OnCompleteCallback) -> None:
        """Register a completion callback."""
        self._on_complete = callback

    async def enqueue(self, media: MediaItem) -> str | None:
        """Add a media item to the download queue.

        Returns task ID, or None if the item is a duplicate.
        """
        # Check if already downloaded
        if await self.db.is_downloaded(media.chat_id, media.message_id, media.media_type):
            logger.debug(
                "Skipping duplicate: chat=%d msg=%d type=%s",
                media.chat_id,
                media.message_id,
                media.media_type.value,
            )
            return None

        task_id = await self.db.enqueue_task(media)
        logger.info(
            "Enqueued: %s from chat %d msg %d (task=%s)",
            media.media_type.value,
            media.chat_id,
            media.message_id,
            task_id,
        )
        return task_id

    async def enqueue_many(self, items: list[MediaItem]) -> list[str]:
        """Enqueue multiple media items. Returns list of task IDs (excludes duplicates)."""
        task_ids = []
        for item in items:
            task_id = await self.enqueue(item)
            if task_id:
                task_ids.append(task_id)
        return task_ids

    async def process_queue(self) -> list[DownloadResult]:
        """Process all pending tasks in the queue.

        Runs downloads concurrently up to max_concurrent limit.
        Returns list of results for all processed tasks.
        """
        self._running = True
        results: list[DownloadResult] = []

        while self._running:
            pending = await self.db.get_pending_tasks(limit=self.max_concurrent * 2)
            if not pending:
                break

            tasks = []
            for task_row in pending:
                media = self._row_to_media(task_row)
                task = asyncio.create_task(
                    self._process_single(task_row["id"], media)
                )
                tasks.append(task)

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in batch_results:
                if isinstance(result, DownloadResult):
                    results.append(result)
                elif isinstance(result, Exception):
                    logger.error("Task failed with exception: %s", result)

        self._running = False
        return results

    async def _process_single(self, task_id: str, media: MediaItem) -> DownloadResult:
        """Process a single download task with semaphore and retry."""
        async with self._semaphore:
            await self.db.update_task_status(task_id, DownloadStatus.DOWNLOADING)

            for attempt in range(self.max_retries + 1):
                # Progress callback wrapper
                def make_progress_cb(tid: str, m: MediaItem):
                    def cb(downloaded: int, total: int) -> None:
                        if self._on_progress:
                            progress = downloaded / total if total > 0 else 0
                            self._on_progress(
                                DownloadProgress(
                                    task_id=tid,
                                    file_name=m.file_name or "",
                                    media_type=m.media_type,
                                    status=DownloadStatus.DOWNLOADING,
                                    progress=progress,
                                    downloaded_bytes=downloaded,
                                    total_bytes=total,
                                )
                            )
                    return cb

                result = await self.downloader.download(
                    media, progress_callback=make_progress_cb(task_id, media)
                )

                if result.status == DownloadStatus.COMPLETED:
                    await self.db.update_task_status(task_id, DownloadStatus.COMPLETED)
                    await self.db.save_download(result)
                    if self._on_complete:
                        self._on_complete(result)
                    return result

                if result.status == DownloadStatus.SKIPPED:
                    await self.db.update_task_status(task_id, DownloadStatus.SKIPPED)
                    return result

                # Failed - retry if attempts remain
                if attempt < self.max_retries:
                    await self.db.increment_retry(task_id)
                    logger.warning(
                        "Retry %d/%d for task %s: %s",
                        attempt + 1,
                        self.max_retries,
                        task_id,
                        result.error,
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    await self.db.update_task_status(
                        task_id, DownloadStatus.FAILED, result.error
                    )
                    if self._on_complete:
                        self._on_complete(result)
                    return result

            # Should not reach here, but just in case
            return result  # type: ignore[possibly-undefined]

    def stop(self) -> None:
        """Signal the queue to stop processing after current batch."""
        self._running = False
        logger.info("Queue stop requested")

    @property
    def active_count(self) -> int:
        """Number of currently active downloads."""
        return self.max_concurrent - self._semaphore._value

    @staticmethod
    def _row_to_media(row: dict) -> MediaItem:
        """Convert a database row to MediaItem."""
        from datetime import datetime

        date = None
        if row.get("date"):
            date = datetime.fromisoformat(row["date"])

        return MediaItem(
            message_id=row["message_id"],
            chat_id=row["chat_id"],
            media_type=MediaType(row["media_type"]),
            file_id=row.get("file_id"),
            file_size=row.get("file_size"),
            file_name=row.get("file_name"),
            mime_type=row.get("mime_type"),
            sender_id=row.get("sender_id"),
            sender_name=row.get("sender_name"),
            date=date,
            caption=row.get("caption"),
        )
