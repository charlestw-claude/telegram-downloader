"""History page — browse download records with filtering."""

from __future__ import annotations

import csv
import io
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.types import MediaType


class HistoryPage(QWidget):
    """Download history with filtering and export."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._downloads = []
        self._build_ui()
        bridge.connected.connect(self._refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Download History")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Filters
        filters = QHBoxLayout()

        filters.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "video", "image"])
        filters.addWidget(self.type_combo)

        filters.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 500)
        self.limit_spin.setValue(50)
        filters.addWidget(self.limit_spin)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._refresh)
        filters.addWidget(search_btn)

        filters.addStretch()

        export_json_btn = QPushButton("Export JSON")
        export_json_btn.clicked.connect(lambda: self._export("json"))
        filters.addWidget(export_json_btn)

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(lambda: self._export("csv"))
        filters.addWidget(export_csv_btn)

        layout.addLayout(filters)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Chat ID", "Sender", "Type", "Filename", "Size", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Count label
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

    def _refresh(self) -> None:
        if not self.bridge.db:
            return

        media_type = None
        type_text = self.type_combo.currentText()
        if type_text != "All":
            media_type = MediaType(type_text)

        self.bridge.submit(
            self.bridge.db.get_downloads(
                media_type=media_type,
                limit=self.limit_spin.value(),
            ),
            on_result=self._populate_table,
        )

    def _populate_table(self, downloads: list[dict]) -> None:
        self._downloads = downloads
        self.table.setRowCount(len(downloads))
        self.count_label.setText(f"Showing {len(downloads)} records")

        for row, dl in enumerate(downloads):
            date_str = (dl.get("created_at") or "")[:19]
            self.table.setItem(row, 0, QTableWidgetItem(date_str))
            self.table.setItem(row, 1, QTableWidgetItem(str(dl.get("chat_id", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(
                dl.get("sender_name") or str(dl.get("sender_id") or "-")
            ))
            self.table.setItem(row, 3, QTableWidgetItem(dl.get("media_type", "")))
            self.table.setItem(row, 4, QTableWidgetItem(dl.get("file_name") or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(self._format_size(dl.get("file_size", 0))))

            status = dl.get("status", "unknown")
            status_item = QTableWidgetItem(status)
            if status == "completed":
                status_item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#27ae60"))
            elif status == "failed":
                status_item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#e74c3c"))
            self.table.setItem(row, 6, status_item)

    def _export(self, fmt: str) -> None:
        if not self._downloads:
            return

        ext = "json" if fmt == "json" else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", f"downloads.{ext}", f"{ext.upper()} Files (*.{ext})"
        )
        if not path:
            return

        if fmt == "json":
            content = json.dumps(self._downloads, indent=2, ensure_ascii=False, default=str)
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=self._downloads[0].keys())
            writer.writeheader()
            writer.writerows(self._downloads)
            content = buf.getvalue()

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _format_size(size_bytes) -> str:
        if not size_bytes:
            return "-"
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
