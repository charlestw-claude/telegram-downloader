"""Core type definitions for telegram-downloader."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class MediaType(str, enum.Enum):
    """Type of media content."""

    VIDEO = "video"
    IMAGE = "image"
    ANIMATION = "animation"  # GIFs


class DownloadStatus(str, enum.Enum):
    """Status of a download task."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # duplicate or filtered out


class SubscriptionStatus(str, enum.Enum):
    """Status of a subscription."""

    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class MediaItem:
    """Represents a single media file to download."""

    message_id: int
    chat_id: int
    media_type: MediaType
    file_id: str | None = None
    file_size: int | None = None
    file_name: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None  # seconds, for video/animation
    thumbnail_file_id: str | None = None
    sender_id: int | None = None
    sender_name: str | None = None
    date: datetime | None = None
    caption: str | None = None


@dataclass
class DownloadTask:
    """A queued download task."""

    id: str
    media: MediaItem
    status: DownloadStatus = DownloadStatus.PENDING
    output_path: Path | None = None
    progress: float = 0.0  # 0.0 - 1.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0


@dataclass
class SubscriptionConfig:
    """Configuration for a channel/chat subscription."""

    id: str
    chat_id: int
    chat_title: str | None = None
    chat_username: str | None = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    media_types: list[MediaType] = field(
        default_factory=lambda: [MediaType.VIDEO, MediaType.IMAGE]
    )
    min_file_size: int | None = None  # bytes, filter out small files
    max_file_size: int | None = None  # bytes, filter out large files
    last_checked_message_id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class DownloadProgress:
    """Progress information for an active download."""

    task_id: str
    file_name: str
    media_type: MediaType
    status: DownloadStatus
    progress: float  # 0.0 - 1.0
    downloaded_bytes: int
    total_bytes: int
    speed: float = 0.0  # bytes per second


@dataclass
class DownloadResult:
    """Result of a completed download."""

    task_id: str
    media: MediaItem
    status: DownloadStatus
    output_path: Path | None = None
    file_size: int = 0
    error: str | None = None
    duration_seconds: float = 0.0
