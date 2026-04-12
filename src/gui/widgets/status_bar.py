"""Bottom status bar showing connection, scheduler, and queue state."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StatusBar(QWidget):
    """Status bar at the bottom of the main window."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.connection_label = QLabel("Connecting...")
        self.scheduler_label = QLabel("Scheduler: Stopped")
        self.queue_label = QLabel("Queue: 0 active")

        self.connection_label.setStyleSheet("color: #888;")
        self.scheduler_label.setStyleSheet("color: #888;")
        self.queue_label.setStyleSheet("color: #888;")

        layout.addWidget(self.connection_label)
        layout.addStretch()
        layout.addWidget(self.scheduler_label)
        layout.addStretch()
        layout.addWidget(self.queue_label)

        # Periodic update
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(2000)

        # Signals
        bridge.connected.connect(self._on_connected)
        bridge.disconnected.connect(self._on_disconnected)
        bridge.connection_failed.connect(self._on_connection_failed)

    def _on_connected(self) -> None:
        self.connection_label.setText("Connected")
        self.connection_label.setStyleSheet("color: #27ae60; font-weight: bold;")

    def _on_disconnected(self) -> None:
        self.connection_label.setText("Disconnected")
        self.connection_label.setStyleSheet("color: #e74c3c;")

    def _on_connection_failed(self, msg: str) -> None:
        self.connection_label.setText("Not Authorized")
        self.connection_label.setStyleSheet("color: #e74c3c;")

    def _update(self) -> None:
        # Scheduler state
        if self.bridge.scheduler and self.bridge.scheduler.is_running:
            self.scheduler_label.setText("Scheduler: Running")
            self.scheduler_label.setStyleSheet("color: #27ae60;")
        else:
            self.scheduler_label.setText("Scheduler: Stopped")
            self.scheduler_label.setStyleSheet("color: #888;")

        # Queue state
        if self.bridge.queue:
            count = self.bridge.queue.active_count
            self.queue_label.setText(f"Queue: {count} active")
            if count > 0:
                self.queue_label.setStyleSheet("color: #2980b9;")
            else:
                self.queue_label.setStyleSheet("color: #888;")
