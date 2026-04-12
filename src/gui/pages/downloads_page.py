"""Downloads page — scan channels and download with real-time progress."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.types import DownloadStatus, MediaType


class DownloadsPage(QWidget):
    """Download management with real-time progress display."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._progress_bars: dict[str, ProgressRow] = {}
        self._build_ui()

        bridge.progress_updated.connect(self._on_progress)
        bridge.download_completed.connect(self._on_completed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Downloads")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Download form
        form = QHBoxLayout()

        form.addWidget(QLabel("Channel:"))
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("@channel_name or numeric ID")
        self.chat_input.setMinimumWidth(200)
        form.addWidget(self.chat_input)

        form.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 10000)
        self.limit_spin.setValue(50)
        self.limit_spin.setSpecialValueText("No limit")
        form.addWidget(self.limit_spin)

        self.videos_cb = QCheckBox("Videos")
        self.videos_cb.setChecked(True)
        form.addWidget(self.videos_cb)

        self.images_cb = QCheckBox("Images")
        self.images_cb.setChecked(True)
        form.addWidget(self.images_cb)

        self.scan_btn = QPushButton("Scan & Download")
        self.scan_btn.setStyleSheet(
            "background-color: #2980b9; color: white; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold;"
        )
        self.scan_btn.clicked.connect(self._start_download)
        form.addWidget(self.scan_btn)

        layout.addLayout(form)

        # Status line
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; margin: 5px 0;")
        layout.addWidget(self.status_label)

        # Process queue button
        queue_row = QHBoxLayout()
        self.process_btn = QPushButton("Process Pending Queue")
        self.process_btn.clicked.connect(self._process_queue)
        queue_row.addWidget(self.process_btn)
        queue_row.addStretch()
        layout.addLayout(queue_row)

        # Progress area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #ddd; border-radius: 4px;")

        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setAlignment(Qt.AlignTop)
        self.progress_layout.setSpacing(4)

        self.empty_label = QLabel("No active downloads. Enter a channel above to start.")
        self.empty_label.setStyleSheet("color: #aaa; padding: 40px;")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.progress_layout.addWidget(self.empty_label)

        scroll.setWidget(self.progress_container)
        layout.addWidget(scroll, 1)

    def _start_download(self) -> None:
        chat_id = self.chat_input.text().strip()
        if not chat_id:
            return
        if not self.bridge.resolver:
            self.status_label.setText("Not connected to Telegram")
            return

        # Parse chat_id
        target = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id

        media_types = []
        if self.videos_cb.isChecked():
            media_types.append(MediaType.VIDEO)
        if self.images_cb.isChecked():
            media_types.append(MediaType.IMAGE)

        limit = self.limit_spin.value() if self.limit_spin.value() > 0 else None

        self.scan_btn.setEnabled(False)
        self.status_label.setText(f"Scanning {chat_id}...")

        self.bridge.submit(
            self._scan_and_enqueue(target, media_types, limit),
            on_result=self._on_scan_complete,
            on_error=self._on_scan_error,
        )

    async def _scan_and_enqueue(self, target, media_types, limit):
        """Scan channel and enqueue items. Runs on asyncio thread."""
        items = await self.bridge.resolver.resolve_chat(
            chat_id=target,
            media_types=media_types,
            limit=limit,
        )
        if not items:
            return {"found": 0, "enqueued": 0}

        task_ids = await self.bridge.queue.enqueue_many(items)
        return {"found": len(items), "enqueued": len(task_ids)}

    def _on_scan_complete(self, result: dict) -> None:
        self.scan_btn.setEnabled(True)
        found = result["found"]
        enqueued = result["enqueued"]
        dupes = found - enqueued
        self.status_label.setText(
            f"Found {found} items, enqueued {enqueued} new ({dupes} duplicates)"
        )
        if enqueued > 0:
            self._process_queue()

    def _on_scan_error(self, error: Exception) -> None:
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("color: #e74c3c; margin: 5px 0;")

    def _process_queue(self) -> None:
        if not self.bridge.queue:
            return
        self.process_btn.setEnabled(False)
        self.status_label.setText("Processing queue...")
        self.bridge.submit(
            self.bridge.queue.process_queue(),
            on_result=self._on_queue_done,
            on_error=lambda e: self.bridge.error_occurred.emit(str(e)),
        )

    def _on_queue_done(self, results) -> None:
        self.process_btn.setEnabled(True)
        completed = sum(1 for r in results if r.status == DownloadStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == DownloadStatus.FAILED)
        self.status_label.setText(
            f"Queue done: {completed} completed, {failed} failed"
        )
        self.status_label.setStyleSheet("color: #27ae60; margin: 5px 0;")

    def _on_progress(self, progress) -> None:
        """Update progress bar for a download task."""
        self.empty_label.hide()

        task_id = progress.task_id
        if task_id not in self._progress_bars:
            row = ProgressRow(progress.file_name or "unknown", progress.media_type.value)
            self._progress_bars[task_id] = row
            self.progress_layout.addWidget(row)

        row = self._progress_bars[task_id]
        if progress.total_bytes > 0:
            pct = int(progress.downloaded_bytes / progress.total_bytes * 100)
            row.progress_bar.setValue(pct)
            row.size_label.setText(
                f"{self._fmt_size(progress.downloaded_bytes)} / {self._fmt_size(progress.total_bytes)}"
            )

    def _on_completed(self, result) -> None:
        """Mark a download as completed."""
        task_id = result.task_id
        if task_id in self._progress_bars:
            row = self._progress_bars[task_id]
            if result.status == DownloadStatus.COMPLETED:
                row.progress_bar.setValue(100)
                row.status_label.setText("Completed")
                row.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            elif result.status == DownloadStatus.FAILED:
                row.status_label.setText(f"Failed: {result.error or 'unknown'}")
                row.status_label.setStyleSheet("color: #e74c3c;")

    @staticmethod
    def _fmt_size(size_bytes) -> str:
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class ProgressRow(QWidget):
    """Single download progress bar widget."""

    def __init__(self, filename: str, media_type: str, parent=None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        type_label = QLabel(media_type)
        type_label.setFixedWidth(50)
        type_label.setStyleSheet("color: #2980b9; font-weight: bold;")
        layout.addWidget(type_label)

        name_label = QLabel(filename)
        name_label.setFixedWidth(250)
        name_label.setToolTip(filename)
        layout.addWidget(name_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar, 1)

        self.size_label = QLabel("")
        self.size_label.setFixedWidth(150)
        self.size_label.setStyleSheet("color: #888;")
        layout.addWidget(self.size_label)

        self.status_label = QLabel("Downloading")
        self.status_label.setFixedWidth(120)
        self.status_label.setStyleSheet("color: #2980b9;")
        layout.addWidget(self.status_label)
