"""Media downloader - handles downloading individual media files from Telegram."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from telethon import TelegramClient

from src.core.types import (
    DownloadResult,
    DownloadStatus,
    MediaItem,
    MediaType,
)

logger = logging.getLogger("telegram_downloader.downloader")

# Progress callback type: (downloaded_bytes, total_bytes) -> None
ProgressCallback = Callable[[int, int], None]


class MediaDownloader:
    """Downloads media files from Telegram messages.

    This module handles single media downloads only. It does not manage
    queues, subscriptions, or scheduling - those are handled by their
    respective modules.
    """

    def __init__(
        self,
        client: TelegramClient,
        download_path: Path,
    ) -> None:
        self.client = client
        self.download_path = download_path

    def _get_output_dir(self, media: MediaItem) -> Path:
        """Build output directory: downloads/{sender_id}/{media_type}s/"""
        sender_dir = str(media.sender_id) if media.sender_id else "unknown"

        if media.media_type == MediaType.VIDEO:
            type_dir = "videos"
        elif media.media_type == MediaType.IMAGE:
            type_dir = "images"
        else:
            type_dir = "animations"

        output_dir = self.download_path / sender_dir / type_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _build_filename(self, media: MediaItem) -> str:
        """Build a descriptive filename for the media."""
        # Use original filename if available
        if media.file_name:
            return media.file_name

        # Generate filename from metadata
        timestamp = ""
        if media.date:
            timestamp = media.date.strftime("%Y%m%d_%H%M%S")
        else:
            timestamp = str(media.message_id)

        ext = self._get_extension(media)
        return f"{media.chat_id}_{timestamp}_{media.message_id}{ext}"

    @staticmethod
    def _get_extension(media: MediaItem) -> str:
        """Determine file extension from media type and mime."""
        if media.mime_type:
            mime_to_ext = {
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/x-matroska": ".mkv",
                "video/webm": ".webm",
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "image/gif": ".gif",
                "video/x-msvideo": ".avi",
            }
            ext = mime_to_ext.get(media.mime_type)
            if ext:
                return ext

        # Fallback by media type
        type_to_ext = {
            MediaType.VIDEO: ".mp4",
            MediaType.IMAGE: ".jpg",
            MediaType.ANIMATION: ".gif",
        }
        return type_to_ext.get(media.media_type, "")

    async def download(
        self,
        media: MediaItem,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download a single media item.

        Args:
            media: The media item to download.
            progress_callback: Optional callback for progress updates.

        Returns:
            DownloadResult with status and file path.
        """
        start_time = time.monotonic()
        task_id = f"{media.chat_id}_{media.message_id}"

        try:
            output_dir = self._get_output_dir(media)
            filename = self._build_filename(media)
            output_path = output_dir / filename

            # Skip if file already exists with same size
            if output_path.exists() and media.file_size:
                existing_size = output_path.stat().st_size
                if existing_size == media.file_size:
                    logger.info("Skipping (already exists): %s", filename)
                    return DownloadResult(
                        task_id=task_id,
                        media=media,
                        status=DownloadStatus.SKIPPED,
                        output_path=output_path,
                        file_size=existing_size,
                        duration_seconds=time.monotonic() - start_time,
                    )

            logger.info(
                "Downloading %s from chat %d, message %d",
                media.media_type.value,
                media.chat_id,
                media.message_id,
            )

            # Build Telethon progress callback
            def _make_progress_cb(cb: ProgressCallback):
                def _on_progress(received: int, total: int) -> None:
                    cb(received, total)
                return _on_progress

            telethon_progress = _make_progress_cb(progress_callback) if progress_callback else None

            # Download using Telethon
            message = await self.client.get_messages(media.chat_id, ids=media.message_id)
            if not message or not message.media:
                return DownloadResult(
                    task_id=task_id,
                    media=media,
                    status=DownloadStatus.FAILED,
                    error="Message not found or has no media",
                    duration_seconds=time.monotonic() - start_time,
                )

            downloaded_path = await self.client.download_media(
                message,
                file=str(output_path),
                progress_callback=telethon_progress,
            )

            if not downloaded_path:
                return DownloadResult(
                    task_id=task_id,
                    media=media,
                    status=DownloadStatus.FAILED,
                    error="Download returned no path",
                    duration_seconds=time.monotonic() - start_time,
                )

            actual_path = Path(downloaded_path)
            file_size = actual_path.stat().st_size

            logger.info("Downloaded: %s (%d bytes)", actual_path.name, file_size)

            return DownloadResult(
                task_id=task_id,
                media=media,
                status=DownloadStatus.COMPLETED,
                output_path=actual_path,
                file_size=file_size,
                duration_seconds=time.monotonic() - start_time,
            )

        except Exception as e:
            logger.error("Download failed for message %d: %s", media.message_id, e)
            return DownloadResult(
                task_id=task_id,
                media=media,
                status=DownloadStatus.FAILED,
                error=str(e),
                duration_seconds=time.monotonic() - start_time,
            )
