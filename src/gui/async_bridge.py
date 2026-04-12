"""Async/Qt bridge — runs asyncio loop on a QThread for backend operations."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Coroutine

from PySide6.QtCore import QThread, Signal

from src.core.config import Config
from src.core.logger import setup_logger

logger = logging.getLogger("telegram_downloader.gui.bridge")


class AsyncBridge(QThread):
    """Bridges Qt main thread with asyncio backend.

    All backend components (client, db, queue, etc.) live on this thread's
    asyncio event loop. The Qt main thread submits coroutines via submit()
    and receives results through Qt signals.
    """

    connected = Signal()
    disconnected = Signal()
    connection_failed = Signal(str)
    error_occurred = Signal(str)
    progress_updated = Signal(object)   # DownloadProgress
    download_completed = Signal(object)  # DownloadResult

    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._loop: asyncio.AbstractEventLoop | None = None

        # Backend components (initialized in run())
        self.client = None
        self.db = None
        self.downloader = None
        self.resolver = None
        self.queue = None
        self.subscription = None
        self.scheduler = None

    def run(self) -> None:
        """QThread entry — creates asyncio loop and initializes backend."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._initialize())
            # Emit connected after loop starts so submit() works in handlers
            self._loop.call_soon(self._emit_connected)
            self._loop.run_forever()
        except Exception as e:
            logger.error("Bridge loop crashed: %s", e)
            self.error_occurred.emit(str(e))
        finally:
            self._loop.run_until_complete(self._shutdown())
            self._loop.close()
            self._loop = None

    def _emit_connected(self) -> None:
        """Emit connected signal from within the running loop."""
        if self.client and self.resolver:
            self.connected.emit()

    async def _initialize(self) -> None:
        """Initialize all backend components on the asyncio thread."""
        from src.core.client import create_client
        from src.database.db import DatabaseManager
        from src.downloader.downloader import MediaDownloader
        from src.queue.download_queue import DownloadQueue
        from src.resolver.resolver import MediaResolver
        from src.scheduler.scheduler import DownloadScheduler
        from src.subscription.manager import SubscriptionManager

        self.config.ensure_directories()
        setup_logger(level=self.config.log_level, log_dir=self.config.log_dir)

        # Database
        self.db = DatabaseManager(self.config.db_path)
        await self.db.connect()

        # Telegram client
        self.client = create_client(self.config)
        await self.client.connect()

        if not await self.client.is_user_authorized():
            self.connection_failed.emit(
                "Telegram session not authorized.\n"
                "Please run 'telegram-dl download @telegram --limit 1' first to authenticate."
            )
            return

        me = await self.client.get_me()
        logger.info("Connected as %s (id=%d)", me.first_name, me.id)

        # Backend modules
        self.downloader = MediaDownloader(self.client, self.config.download_path)
        self.resolver = MediaResolver(self.client)
        self.queue = DownloadQueue(
            self.downloader,
            self.db,
            max_concurrent=self.config.max_concurrent_downloads,
            max_retries=self.config.max_retries,
            retry_delay=self.config.retry_delay,
        )
        self.subscription = SubscriptionManager(self.client, self.db)
        self.scheduler = DownloadScheduler(
            self.client,
            self.db,
            self.queue,
            check_interval=self.config.check_interval,
        )

        # Wire progress/completion signals
        self.queue.on_progress(lambda p: self.progress_updated.emit(p))
        self.queue.on_complete(lambda r: self.download_completed.emit(r))

    async def _shutdown(self) -> None:
        """Clean shutdown of all backend components."""
        try:
            if self.scheduler and self.scheduler.is_running:
                await self.scheduler.stop()
            if self.db:
                await self.db.close()
            if self.client and self.client.is_connected():
                await self.client.disconnect()
        except Exception as e:
            logger.error("Error during shutdown: %s", e)

        self.disconnected.emit()

    def submit(
        self,
        coro: Coroutine,
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> Future | None:
        """Submit a coroutine to the asyncio loop from the Qt main thread.

        Args:
            coro: The coroutine to run.
            on_result: Optional callback for the result (called from asyncio thread).
            on_error: Optional callback for errors (called from asyncio thread).

        Returns:
            A concurrent.futures.Future, or None if loop isn't running.
        """
        if not self._loop or not self._loop.is_running():
            return None

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)

        if on_result or on_error:
            def _done(f: Future):
                try:
                    result = f.result()
                    if on_result:
                        on_result(result)
                except Exception as e:
                    if on_error:
                        on_error(e)
                    else:
                        self.error_occurred.emit(str(e))

            future.add_done_callback(_done)

        return future

    def stop_loop(self) -> None:
        """Signal the asyncio loop to stop."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
