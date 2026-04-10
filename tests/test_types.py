"""Tests for core type definitions."""

from datetime import datetime

from src.core.types import (
    DownloadResult,
    DownloadStatus,
    DownloadTask,
    MediaItem,
    MediaType,
    SubscriptionConfig,
    SubscriptionStatus,
)


def test_media_type_values():
    assert MediaType.VIDEO.value == "video"
    assert MediaType.IMAGE.value == "image"
    assert MediaType.ANIMATION.value == "animation"


def test_download_status_values():
    assert DownloadStatus.PENDING.value == "pending"
    assert DownloadStatus.DOWNLOADING.value == "downloading"
    assert DownloadStatus.COMPLETED.value == "completed"
    assert DownloadStatus.FAILED.value == "failed"
    assert DownloadStatus.SKIPPED.value == "skipped"


def test_media_item_defaults():
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO)
    assert item.file_id is None
    assert item.file_size is None
    assert item.sender_id is None
    assert item.caption is None


def test_media_item_full():
    now = datetime.now()
    item = MediaItem(
        message_id=42,
        chat_id=100,
        media_type=MediaType.IMAGE,
        file_id="abc123",
        file_size=1024,
        file_name="photo.jpg",
        mime_type="image/jpeg",
        width=800,
        height=600,
        sender_id=999,
        sender_name="testuser",
        date=now,
        caption="A photo",
    )
    assert item.message_id == 42
    assert item.file_size == 1024
    assert item.width == 800


def test_download_task_defaults():
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO)
    task = DownloadTask(id="t1", media=item)
    assert task.status == DownloadStatus.PENDING
    assert task.progress == 0.0
    assert task.retry_count == 0


def test_subscription_config_defaults():
    sub = SubscriptionConfig(id="s1", chat_id=100)
    assert sub.status == SubscriptionStatus.ACTIVE
    assert MediaType.VIDEO in sub.media_types
    assert MediaType.IMAGE in sub.media_types
    assert sub.min_file_size is None


def test_download_result():
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO)
    result = DownloadResult(
        task_id="t1",
        media=item,
        status=DownloadStatus.COMPLETED,
        file_size=2048,
        duration_seconds=1.5,
    )
    assert result.status == DownloadStatus.COMPLETED
    assert result.file_size == 2048
    assert result.error is None
