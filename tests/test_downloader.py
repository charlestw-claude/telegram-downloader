"""Tests for downloader module."""

from datetime import datetime
from pathlib import Path

from src.core.types import MediaItem, MediaType
from src.downloader.downloader import MediaDownloader


class FakeClient:
    """Fake TelegramClient for testing."""
    pass


def test_get_output_dir(tmp_path):
    dl = MediaDownloader(FakeClient(), tmp_path)

    video = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO, sender_id=999)
    assert dl._get_output_dir(video) == tmp_path / "999" / "videos"

    image = MediaItem(message_id=2, chat_id=100, media_type=MediaType.IMAGE, sender_id=999)
    assert dl._get_output_dir(image) == tmp_path / "999" / "images"

    anim = MediaItem(message_id=3, chat_id=100, media_type=MediaType.ANIMATION, sender_id=999)
    assert dl._get_output_dir(anim) == tmp_path / "999" / "animations"


def test_get_output_dir_unknown_sender(tmp_path):
    dl = MediaDownloader(FakeClient(), tmp_path)
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO)
    assert dl._get_output_dir(item) == tmp_path / "unknown" / "videos"


def test_build_filename_with_original():
    dl = MediaDownloader(FakeClient(), Path("/tmp"))
    item = MediaItem(
        message_id=1, chat_id=100, media_type=MediaType.VIDEO, file_name="original.mp4"
    )
    assert dl._build_filename(item) == "original.mp4"


def test_build_filename_generated():
    dl = MediaDownloader(FakeClient(), Path("/tmp"))
    item = MediaItem(
        message_id=42,
        chat_id=100,
        media_type=MediaType.VIDEO,
        date=datetime(2026, 1, 15, 10, 30, 0),
        mime_type="video/mp4",
    )
    filename = dl._build_filename(item)
    assert filename == "100_20260115_103000_42.mp4"


def test_build_filename_no_date():
    dl = MediaDownloader(FakeClient(), Path("/tmp"))
    item = MediaItem(message_id=42, chat_id=100, media_type=MediaType.IMAGE)
    filename = dl._build_filename(item)
    assert "42" in filename
    assert filename.endswith(".jpg")


def test_get_extension_from_mime():
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO, mime_type="video/mp4")
    assert MediaDownloader._get_extension(item) == ".mp4"

    item.mime_type = "image/png"
    assert MediaDownloader._get_extension(item) == ".png"

    item.mime_type = "video/webm"
    assert MediaDownloader._get_extension(item) == ".webm"


def test_get_extension_fallback():
    item = MediaItem(message_id=1, chat_id=100, media_type=MediaType.VIDEO)
    assert MediaDownloader._get_extension(item) == ".mp4"

    item.media_type = MediaType.IMAGE
    assert MediaDownloader._get_extension(item) == ".jpg"

    item.media_type = MediaType.ANIMATION
    assert MediaDownloader._get_extension(item) == ".gif"
