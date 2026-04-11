"""Tests for database module."""

import pytest
from datetime import datetime
from pathlib import Path

from src.core.types import (
    DownloadResult,
    DownloadStatus,
    MediaItem,
    MediaType,
    SubscriptionConfig,
    SubscriptionStatus,
)
from src.database.db import DatabaseManager


@pytest.fixture
async def db(tmp_path):
    """Create a test database."""
    db_mgr = DatabaseManager(tmp_path / "test.db")
    await db_mgr.connect()
    yield db_mgr
    await db_mgr.close()


@pytest.fixture
def sample_media():
    return MediaItem(
        message_id=42,
        chat_id=100,
        media_type=MediaType.VIDEO,
        file_id="vid123",
        file_size=1024,
        file_name="test.mp4",
        mime_type="video/mp4",
        sender_id=999,
        sender_name="testuser",
        date=datetime.now(),
        caption="Test video",
    )


@pytest.fixture
def sample_subscription():
    return SubscriptionConfig(
        id="sub1",
        chat_id=100,
        chat_title="Test Channel",
        chat_username="testchannel",
    )


# ── Download tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_query_download(db, sample_media):
    result = DownloadResult(
        task_id="t1",
        media=sample_media,
        status=DownloadStatus.COMPLETED,
        output_path=Path("/tmp/test.mp4"),
        file_size=1024,
        duration_seconds=2.0,
    )
    await db.save_download(result)

    downloads = await db.get_downloads()
    assert len(downloads) == 1
    assert downloads[0]["file_name"] == "test.mp4"
    assert downloads[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_is_downloaded(db, sample_media):
    assert not await db.is_downloaded(100, 42, MediaType.VIDEO)

    result = DownloadResult(
        task_id="t1",
        media=sample_media,
        status=DownloadStatus.COMPLETED,
        file_size=1024,
    )
    await db.save_download(result)

    assert await db.is_downloaded(100, 42, MediaType.VIDEO)
    assert not await db.is_downloaded(100, 42, MediaType.IMAGE)
    assert not await db.is_downloaded(100, 99, MediaType.VIDEO)


@pytest.mark.asyncio
async def test_is_downloaded_skipped(db, sample_media):
    """Skipped downloads should also count as downloaded."""
    result = DownloadResult(
        task_id="t1",
        media=sample_media,
        status=DownloadStatus.SKIPPED,
        file_size=1024,
    )
    await db.save_download(result)

    assert await db.is_downloaded(100, 42, MediaType.VIDEO)


@pytest.mark.asyncio
async def test_download_count(db, sample_media):
    assert await db.get_download_count() == 0

    result = DownloadResult(
        task_id="t1",
        media=sample_media,
        status=DownloadStatus.COMPLETED,
        file_size=1024,
    )
    await db.save_download(result)

    assert await db.get_download_count() == 1
    assert await db.get_download_count(status=DownloadStatus.COMPLETED) == 1
    assert await db.get_download_count(status=DownloadStatus.FAILED) == 0


@pytest.mark.asyncio
async def test_download_filters(db):
    for i in range(3):
        media = MediaItem(
            message_id=i,
            chat_id=100 if i < 2 else 200,
            media_type=MediaType.VIDEO,
            sender_id=999,
        )
        result = DownloadResult(
            task_id=f"t{i}",
            media=media,
            status=DownloadStatus.COMPLETED,
            file_size=1024,
        )
        await db.save_download(result)

    all_downloads = await db.get_downloads()
    assert len(all_downloads) == 3

    chat_100 = await db.get_downloads(chat_id=100)
    assert len(chat_100) == 2

    chat_200 = await db.get_downloads(chat_id=200)
    assert len(chat_200) == 1


# ── Subscription tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_and_get_subscription(db, sample_subscription):
    await db.add_subscription(sample_subscription)

    sub = await db.get_subscription(100)
    assert sub is not None
    assert sub.chat_title == "Test Channel"
    assert sub.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_active_subscriptions(db, sample_subscription):
    await db.add_subscription(sample_subscription)

    paused_sub = SubscriptionConfig(
        id="sub2",
        chat_id=200,
        chat_title="Paused Channel",
        status=SubscriptionStatus.PAUSED,
    )
    await db.add_subscription(paused_sub)

    active = await db.get_active_subscriptions()
    assert len(active) == 1
    assert active[0].chat_id == 100


@pytest.mark.asyncio
async def test_update_subscription_status(db, sample_subscription):
    await db.add_subscription(sample_subscription)

    await db.update_subscription_status(100, SubscriptionStatus.PAUSED)
    sub = await db.get_subscription(100)
    assert sub.status == SubscriptionStatus.PAUSED


@pytest.mark.asyncio
async def test_remove_subscription(db, sample_subscription):
    await db.add_subscription(sample_subscription)
    assert await db.remove_subscription(100) is True
    assert await db.get_subscription(100) is None
    assert await db.remove_subscription(100) is False


@pytest.mark.asyncio
async def test_update_last_checked(db, sample_subscription):
    await db.add_subscription(sample_subscription)

    await db.update_last_checked(100, 500)
    sub = await db.get_subscription(100)
    assert sub.last_checked_message_id == 500


# ── Queue task tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_task(db, sample_media):
    task_id = await db.enqueue_task(sample_media)
    assert task_id is not None
    assert len(task_id) == 36  # Full UUID length


@pytest.mark.asyncio
async def test_get_pending_tasks(db, sample_media):
    await db.enqueue_task(sample_media)

    pending = await db.get_pending_tasks()
    assert len(pending) == 1
    assert pending[0]["message_id"] == 42
    assert pending[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_update_task_status(db, sample_media):
    task_id = await db.enqueue_task(sample_media)

    await db.update_task_status(task_id, DownloadStatus.COMPLETED)

    pending = await db.get_pending_tasks()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_increment_retry(db, sample_media):
    task_id = await db.enqueue_task(sample_media)
    await db.increment_retry(task_id)

    pending = await db.get_pending_tasks()
    assert pending[0]["retry_count"] == 1
