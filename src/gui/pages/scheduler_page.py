"""Scheduler page — control the auto-download scheduler."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import logging


class SchedulerPage(QWidget):
    """Scheduler control and monitoring page."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._build_ui()

        # Poll scheduler state
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._timer.start(2000)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Scheduler")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Status card
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self.status_indicator = QLabel("Stopped")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #888; padding: 20px;"
        )
        status_layout.addWidget(self.status_indicator)

        self.info_label = QLabel(
            f"Check interval: {self.bridge.config.check_interval}s"
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.info_label)

        layout.addWidget(status_group)

        # Controls
        controls = QHBoxLayout()

        self.start_btn = QPushButton("Start Scheduler")
        self.start_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 10px 20px; "
            "border-radius: 4px; font-weight: bold; font-size: 14px;"
        )
        self.start_btn.clicked.connect(self._start)
        controls.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Scheduler")
        self.stop_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 10px 20px; "
            "border-radius: 4px; font-weight: bold; font-size: 14px;"
        )
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        controls.addWidget(self.stop_btn)

        self.check_btn = QPushButton("Check Now")
        self.check_btn.setStyleSheet(
            "background-color: #2980b9; color: white; padding: 10px 20px; "
            "border-radius: 4px; font-weight: bold; font-size: 14px;"
        )
        self.check_btn.clicked.connect(self._check_now)
        controls.addWidget(self.check_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Log area
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 12px;")
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group, 1)

    def _update_status(self) -> None:
        if self.bridge.scheduler and self.bridge.scheduler.is_running:
            self.status_indicator.setText("Running")
            self.status_indicator.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #27ae60; padding: 20px;"
            )
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_indicator.setText("Stopped")
            self.status_indicator.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #888; padding: 20px;"
            )
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def _start(self) -> None:
        if not self.bridge.scheduler:
            self._log("Scheduler not available (not connected)")
            return
        self.bridge.submit(
            self.bridge.scheduler.start(),
            on_result=lambda _: self._log("Scheduler started"),
            on_error=lambda e: self._log(f"Failed to start: {e}"),
        )

    def _stop(self) -> None:
        if not self.bridge.scheduler:
            return
        self.bridge.submit(
            self.bridge.scheduler.stop(),
            on_result=lambda _: self._log("Scheduler stopped"),
        )

    def _check_now(self) -> None:
        if not self.bridge.scheduler:
            self._log("Scheduler not available (not connected)")
            return
        self._log("Running manual check...")
        self.bridge.submit(
            self.bridge.scheduler.check_now(),
            on_result=lambda count: self._log(f"Check complete: {count} new items enqueued"),
            on_error=lambda e: self._log(f"Check failed: {e}"),
        )

    def _log(self, message: str) -> None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
