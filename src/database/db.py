"""SQLite database manager for persistent storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from src.core.types import (
    DownloadResult,
    DownloadStatus,
    MediaItem,
    MediaType,
    SubscriptionConfig,
    SubscriptionStatus,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    id TEXT PRIMARY KEY,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    sender_id INTEGER,
    sender_name TEXT,
    media_type TEXT NOT NULL,
    file_name TEXT,
    file_size INTEGER DEFAULT 0,
    mime_type TEXT,
    output_path TEXT,
    status TEXT NOT NULL DEFAULT 'completed',
    error TEXT,
    duration_seconds REAL DEFAULT 0,
    caption TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(chat_id, message_id, media_type)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL UNIQUE,
    chat_title TEXT,
    chat_username TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    media_types TEXT NOT NULL DEFAULT '["video","image"]',
    min_file_size INTEGER,
    max_file_size INTEGER,
    last_checked_message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue_tasks (
    id TEXT PRIMARY KEY,
    message_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    file_id TEXT,
    file_size INTEGER,
    file_name TEXT,
    mime_type TEXT,
    sender_id INTEGER,
    sender_name TEXT,
    date TEXT,
    caption TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(chat_id, message_id, media_type)
);

CREATE INDEX IF NOT EXISTS idx_downloads_chat_id ON downloads(chat_id);
CREATE INDEX IF NOT EXISTS idx_downloads_sender_id ON downloads(sender_id);
CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_tasks(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
"""


class DatabaseManager:
    """Async SQLite database manager."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # ── Downloads ──────────────────────────────────────────────

    async def save_download(self, result: DownloadResult) -> None:
        """Save a completed download record."""
        await self.db.execute(
            """INSERT OR REPLACE INTO downloads
            (id, message_id, chat_id, sender_id, sender_name, media_type,
             file_name, file_size, mime_type, output_path, status, error,
             duration_seconds, caption, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.task_id,
                result.media.message_id,
                result.media.chat_id,
                result.media.sender_id,
                result.media.sender_name,
                result.media.media_type.value,
                result.media.file_name,
                result.file_size,
                result.media.mime_type,
                str(result.output_path) if result.output_path else None,
                result.status.value,
                result.error,
                result.duration_seconds,
                result.media.caption,
                datetime.now().isoformat(),
            ),
        )
        await self.db.commit()

    async def is_downloaded(self, chat_id: int, message_id: int, media_type: MediaType) -> bool:
        """Check if a media item has already been downloaded."""
        cursor = await self.db.execute(
            """SELECT 1 FROM downloads
            WHERE chat_id = ? AND message_id = ? AND media_type = ? AND status = 'completed'""",
            (chat_id, message_id, media_type.value),
        )
        return await cursor.fetchone() is not None

    async def get_downloads(
        self,
        chat_id: int | None = None,
        sender_id: int | None = None,
        media_type: MediaType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Query download history with optional filters."""
        conditions = []
        params: list = []

        if chat_id is not None:
            conditions.append("chat_id = ?")
            params.append(chat_id)
        if sender_id is not None:
            conditions.append("sender_id = ?")
            params.append(sender_id)
        if media_type is not None:
            conditions.append("media_type = ?")
            params.append(media_type.value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM downloads {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_download_count(
        self, chat_id: int | None = None, status: DownloadStatus | None = None
    ) -> int:
        """Get count of downloads with optional filters."""
        conditions = []
        params: list = []

        if chat_id is not None:
            conditions.append("chat_id = ?")
            params.append(chat_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = await self.db.execute(f"SELECT COUNT(*) FROM downloads {where}", params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    # ── Subscriptions ─────────────────────────────────────────

    async def add_subscription(self, sub: SubscriptionConfig) -> None:
        """Add or update a subscription."""
        media_types_json = json.dumps([mt.value for mt in sub.media_types])
        await self.db.execute(
            """INSERT OR REPLACE INTO subscriptions
            (id, chat_id, chat_title, chat_username, status, media_types,
             min_file_size, max_file_size, last_checked_message_id,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sub.id,
                sub.chat_id,
                sub.chat_title,
                sub.chat_username,
                sub.status.value,
                media_types_json,
                sub.min_file_size,
                sub.max_file_size,
                sub.last_checked_message_id,
                sub.created_at.isoformat(),
                sub.updated_at.isoformat(),
            ),
        )
        await self.db.commit()

    async def get_subscription(self, chat_id: int) -> SubscriptionConfig | None:
        """Get subscription by chat_id."""
        cursor = await self.db.execute(
            "SELECT * FROM subscriptions WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_subscription(dict(row))

    async def get_active_subscriptions(self) -> list[SubscriptionConfig]:
        """Get all active subscriptions."""
        cursor = await self.db.execute(
            "SELECT * FROM subscriptions WHERE status = 'active' ORDER BY chat_title"
        )
        rows = await cursor.fetchall()
        return [self._row_to_subscription(dict(row)) for row in rows]

    async def get_all_subscriptions(self) -> list[SubscriptionConfig]:
        """Get all subscriptions."""
        cursor = await self.db.execute("SELECT * FROM subscriptions ORDER BY chat_title")
        rows = await cursor.fetchall()
        return [self._row_to_subscription(dict(row)) for row in rows]

    async def update_subscription_status(
        self, chat_id: int, status: SubscriptionStatus
    ) -> None:
        """Update subscription status."""
        await self.db.execute(
            "UPDATE subscriptions SET status = ?, updated_at = ? WHERE chat_id = ?",
            (status.value, datetime.now().isoformat(), chat_id),
        )
        await self.db.commit()

    async def update_last_checked(self, chat_id: int, message_id: int) -> None:
        """Update the last checked message ID for a subscription."""
        await self.db.execute(
            "UPDATE subscriptions SET last_checked_message_id = ?, updated_at = ? WHERE chat_id = ?",
            (message_id, datetime.now().isoformat(), chat_id),
        )
        await self.db.commit()

    async def remove_subscription(self, chat_id: int) -> bool:
        """Remove a subscription. Returns True if found and removed."""
        cursor = await self.db.execute(
            "DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    # ── Queue Tasks ───────────────────────────────────────────

    async def enqueue_task(self, media: MediaItem) -> str:
        """Add a media item to the download queue. Returns task ID."""
        task_id = str(uuid.uuid4())[:8]
        await self.db.execute(
            """INSERT OR IGNORE INTO queue_tasks
            (id, message_id, chat_id, media_type, file_id, file_size, file_name,
             mime_type, sender_id, sender_name, date, caption, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                task_id,
                media.message_id,
                media.chat_id,
                media.media_type.value,
                media.file_id,
                media.file_size,
                media.file_name,
                media.mime_type,
                media.sender_id,
                media.sender_name,
                media.date.isoformat() if media.date else None,
                media.caption,
                datetime.now().isoformat(),
            ),
        )
        await self.db.commit()
        return task_id

    async def get_pending_tasks(self, limit: int = 10) -> list[dict]:
        """Get pending download tasks."""
        cursor = await self.db.execute(
            "SELECT * FROM queue_tasks WHERE status = 'pending' ORDER BY created_at LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_task_status(
        self, task_id: str, status: DownloadStatus, error: str | None = None
    ) -> None:
        """Update queue task status."""
        await self.db.execute(
            "UPDATE queue_tasks SET status = ?, error = ? WHERE id = ?",
            (status.value, error, task_id),
        )
        await self.db.commit()

    async def increment_retry(self, task_id: str) -> None:
        """Increment retry count for a task."""
        await self.db.execute(
            "UPDATE queue_tasks SET retry_count = retry_count + 1 WHERE id = ?",
            (task_id,),
        )
        await self.db.commit()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_subscription(row: dict) -> SubscriptionConfig:
        """Convert a database row to SubscriptionConfig."""
        media_types_raw = json.loads(row["media_types"])
        media_types = [MediaType(mt) for mt in media_types_raw]

        return SubscriptionConfig(
            id=row["id"],
            chat_id=row["chat_id"],
            chat_title=row.get("chat_title"),
            chat_username=row.get("chat_username"),
            status=SubscriptionStatus(row["status"]),
            media_types=media_types,
            min_file_size=row.get("min_file_size"),
            max_file_size=row.get("max_file_size"),
            last_checked_message_id=row.get("last_checked_message_id"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
