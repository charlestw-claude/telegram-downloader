"""Subscriptions page — manage channel subscriptions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.types import MediaType, SubscriptionStatus


class SubscriptionsPage(QWidget):
    """Subscription management page."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._build_ui()
        bridge.connected.connect(self._refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Subscriptions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("+ Add Subscription")
        add_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold;"
        )
        add_btn.clicked.connect(self._add_subscription)
        header.addWidget(add_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Chat ID", "Title", "Username", "Status", "Media Types", "Last Checked", "Actions"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def _refresh(self) -> None:
        if not self.bridge.subscription:
            return
        self.bridge.submit(
            self.bridge.subscription.list_all(),
            on_result=self._populate_table,
        )

    def _populate_table(self, subs) -> None:
        self.table.setRowCount(len(subs))
        for row, sub in enumerate(subs):
            self.table.setItem(row, 0, QTableWidgetItem(str(sub.chat_id)))
            self.table.setItem(row, 1, QTableWidgetItem(sub.chat_title or "-"))
            self.table.setItem(row, 2, QTableWidgetItem(
                f"@{sub.chat_username}" if sub.chat_username else "-"
            ))

            status_item = QTableWidgetItem(sub.status.value)
            color_map = {"active": "#27ae60", "paused": "#f39c12", "error": "#e74c3c"}
            status_item.setForeground(
                __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(
                    color_map.get(sub.status.value, "#333")
                )
            )
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(
                ", ".join(mt.value for mt in sub.media_types)
            ))
            self.table.setItem(row, 5, QTableWidgetItem(
                str(sub.last_checked_message_id or "-")
            ))

            # Action buttons
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)

            if sub.status == SubscriptionStatus.ACTIVE:
                pause_btn = QPushButton("Pause")
                pause_btn.setStyleSheet("color: #f39c12;")
                pause_btn.clicked.connect(lambda _, cid=sub.chat_id: self._pause(cid))
                actions_layout.addWidget(pause_btn)
            elif sub.status in (SubscriptionStatus.PAUSED, SubscriptionStatus.ERROR):
                resume_btn = QPushButton("Resume")
                resume_btn.setStyleSheet("color: #27ae60;")
                resume_btn.clicked.connect(lambda _, cid=sub.chat_id: self._resume(cid))
                actions_layout.addWidget(resume_btn)

            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("color: #e74c3c;")
            del_btn.clicked.connect(lambda _, cid=sub.chat_id: self._delete(cid))
            actions_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 6, actions)

    def _add_subscription(self) -> None:
        dialog = AddSubscriptionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["chat_id"]:
                return

            media_types = []
            if data["videos"]:
                media_types.append(MediaType.VIDEO)
            if data["images"]:
                media_types.append(MediaType.IMAGE)

            self.bridge.submit(
                self.bridge.subscription.add(
                    data["chat_id"],
                    media_types=media_types or None,
                    min_file_size=data["min_size"] or None,
                    max_file_size=data["max_size"] or None,
                ),
                on_result=lambda _: self._refresh(),
                on_error=lambda e: self.bridge.error_occurred.emit(str(e)),
            )

    def _pause(self, chat_id: int) -> None:
        self.bridge.submit(
            self.bridge.subscription.pause(chat_id),
            on_result=lambda _: self._refresh(),
        )

    def _resume(self, chat_id: int) -> None:
        self.bridge.submit(
            self.bridge.subscription.resume(chat_id),
            on_result=lambda _: self._refresh(),
        )

    def _delete(self, chat_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm", f"Remove subscription for chat {chat_id}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.bridge.submit(
                self.bridge.subscription.remove(chat_id),
                on_result=lambda _: self._refresh(),
            )


class AddSubscriptionDialog(QDialog):
    """Dialog for adding a new subscription."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Subscription")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("@channel_name or numeric ID")
        layout.addRow("Channel:", self.chat_input)

        self.videos_cb = QCheckBox("Videos")
        self.videos_cb.setChecked(True)
        self.images_cb = QCheckBox("Images")
        self.images_cb.setChecked(True)
        media_layout = QHBoxLayout()
        media_layout.addWidget(self.videos_cb)
        media_layout.addWidget(self.images_cb)
        layout.addRow("Media types:", media_layout)

        self.min_size = QSpinBox()
        self.min_size.setRange(0, 2_000_000_000)
        self.min_size.setSuffix(" bytes")
        self.min_size.setSpecialValueText("No minimum")
        layout.addRow("Min file size:", self.min_size)

        self.max_size = QSpinBox()
        self.max_size.setRange(0, 2_000_000_000)
        self.max_size.setSuffix(" bytes")
        self.max_size.setSpecialValueText("No maximum")
        layout.addRow("Max file size:", self.max_size)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        chat_id = self.chat_input.text().strip()
        if chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)
        return {
            "chat_id": chat_id,
            "videos": self.videos_cb.isChecked(),
            "images": self.images_cb.isChecked(),
            "min_size": self.min_size.value() if self.min_size.value() > 0 else None,
            "max_size": self.max_size.value() if self.max_size.value() > 0 else None,
        }
