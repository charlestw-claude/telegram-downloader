"""Media resolver - extracts media items from Telegram messages and channels."""

from __future__ import annotations

import logging
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import (
    Document,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
)

from src.core.types import MediaItem, MediaType

logger = logging.getLogger("telegram_downloader.resolver")


class MediaResolver:
    """Extracts and classifies media from Telegram messages.

    This module is responsible for:
    - Iterating messages in a chat/channel
    - Identifying media content (videos, images, animations)
    - Extracting metadata (file size, dimensions, sender, etc.)
    - Filtering by media type and size constraints
    """

    def __init__(self, client: TelegramClient) -> None:
        self.client = client

    @staticmethod
    def _classify_document(doc: Document) -> MediaType | None:
        """Classify a document by its MIME type and attributes."""
        mime = doc.mime_type or ""

        if mime.startswith("video/"):
            # Check if it's a GIF animation (round video or gif)
            for attr in doc.attributes:
                attr_name = type(attr).__name__
                if attr_name == "DocumentAttributeAnimated":
                    return MediaType.ANIMATION
            return MediaType.VIDEO

        if mime == "image/gif":
            return MediaType.ANIMATION

        if mime.startswith("image/"):
            return MediaType.IMAGE

        return None

    @staticmethod
    def _extract_document_metadata(doc: Document) -> dict:
        """Extract metadata from a Document object."""
        metadata: dict = {
            "file_id": str(doc.id),
            "file_size": doc.size,
            "mime_type": doc.mime_type,
        }

        for attr in doc.attributes:
            attr_name = type(attr).__name__
            if attr_name == "DocumentAttributeFilename":
                metadata["file_name"] = attr.file_name
            elif attr_name == "DocumentAttributeVideo":
                metadata["width"] = attr.w
                metadata["height"] = attr.h
                metadata["duration"] = attr.duration

        return metadata

    def _message_to_media_items(self, message) -> list[MediaItem]:
        """Extract media items from a single Telegram message."""
        items: list[MediaItem] = []

        if not message.media:
            return items

        sender_id = message.sender_id
        sender_name = None
        if message.sender:
            sender_name = getattr(message.sender, "username", None) or getattr(
                message.sender, "first_name", None
            )

        base_kwargs = {
            "message_id": message.id,
            "chat_id": message.chat_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "date": message.date,
            "caption": message.text,
        }

        # Photo
        if isinstance(message.media, MessageMediaPhoto) and isinstance(
            message.media.photo, Photo
        ):
            photo = message.media.photo
            # Get largest photo size
            largest = max(photo.sizes, key=lambda s: getattr(s, "size", 0), default=None)
            file_size = getattr(largest, "size", None) if largest else None
            w = getattr(largest, "w", None) if largest else None
            h = getattr(largest, "h", None) if largest else None

            items.append(
                MediaItem(
                    **base_kwargs,
                    media_type=MediaType.IMAGE,
                    file_id=str(photo.id),
                    file_size=file_size,
                    width=w,
                    height=h,
                )
            )

        # Document (video, animation, image-as-file)
        elif isinstance(message.media, MessageMediaDocument) and isinstance(
            message.media.document, Document
        ):
            doc = message.media.document
            media_type = self._classify_document(doc)

            if media_type:
                doc_meta = self._extract_document_metadata(doc)
                items.append(
                    MediaItem(
                        **base_kwargs,
                        media_type=media_type,
                        **doc_meta,
                    )
                )

        return items

    async def resolve_message(self, chat_id: int, message_id: int) -> list[MediaItem]:
        """Extract media from a specific message."""
        message = await self.client.get_messages(chat_id, ids=message_id)
        if not message:
            return []
        return self._message_to_media_items(message)

    async def resolve_chat(
        self,
        chat_id: int,
        media_types: list[MediaType] | None = None,
        min_id: int | None = None,
        limit: int | None = None,
        min_file_size: int | None = None,
        max_file_size: int | None = None,
        timeout: float | None = 300.0,
    ) -> list[MediaItem]:
        """Scan a chat/channel for media items.

        Args:
            chat_id: Telegram chat or channel ID.
            media_types: Filter by media types. None = all types.
            min_id: Only get messages newer than this ID.
            limit: Maximum number of messages to scan. None = no limit.
            min_file_size: Minimum file size in bytes.
            max_file_size: Maximum file size in bytes.
            timeout: Scan timeout in seconds. None = no timeout.

        Returns:
            List of MediaItem objects found.
        """
        import asyncio

        allowed_types = set(media_types) if media_types else None
        items: list[MediaItem] = []
        scanned = 0

        logger.info("Scanning chat %s for media (min_id=%s, limit=%s)", chat_id, min_id, limit)

        async def _scan():
            nonlocal scanned
            async for message in self.client.iter_messages(
                chat_id,
                min_id=min_id or 0,
                limit=limit,
            ):
                scanned += 1
                if scanned % 500 == 0:
                    logger.debug("Scanned %d messages...", scanned)

                message_items = self._message_to_media_items(message)

                for item in message_items:
                    if allowed_types and item.media_type not in allowed_types:
                        continue
                    if min_file_size and item.file_size and item.file_size < min_file_size:
                        continue
                    if max_file_size and item.file_size and item.file_size > max_file_size:
                        continue
                    items.append(item)

        try:
            if timeout:
                await asyncio.wait_for(_scan(), timeout=timeout)
            else:
                await _scan()
        except asyncio.TimeoutError:
            logger.warning(
                "Scan timed out after %.0fs (scanned %d messages, found %d items)",
                timeout,
                scanned,
                len(items),
            )

        logger.info(
            "Found %d media items in %d messages from chat %s",
            len(items),
            scanned,
            chat_id,
        )
        return items

    async def get_chat_info(self, chat_id: int | str) -> dict | None:
        """Get basic info about a chat/channel.

        Args:
            chat_id: Numeric ID or username (e.g., '@channel_name').

        Returns:
            Dict with id, title, username, or None if not found.
        """
        try:
            entity = await self.client.get_entity(chat_id)
            return {
                "id": entity.id,
                "title": getattr(entity, "title", None)
                or getattr(entity, "first_name", None),
                "username": getattr(entity, "username", None),
            }
        except Exception as e:
            logger.error("Failed to get chat info for %s: %s", chat_id, e)
            return None
