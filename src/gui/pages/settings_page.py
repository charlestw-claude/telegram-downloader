"""Settings page — displays current configuration."""

from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    """Display current configuration (read-only)."""

    def __init__(self, bridge, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.config = bridge.config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Telegram API group
        api_group = QGroupBox("Telegram API")
        api_form = QFormLayout(api_group)
        api_form.addRow("API ID:", QLabel(str(self.config.api_id) if self.config.api_id else "Not set"))
        api_form.addRow("API Hash:", QLabel("****" if self.config.api_hash else "Not set"))
        api_form.addRow("Phone:", QLabel(self.config.phone or "Not set"))
        layout.addWidget(api_group)

        # Paths group
        paths_group = QGroupBox("Paths")
        paths_form = QFormLayout(paths_group)
        paths_form.addRow("Download path:", QLabel(str(self.config.download_path.resolve())))
        paths_form.addRow("Database:", QLabel(str(self.config.db_path.resolve())))
        paths_form.addRow("Log directory:", QLabel(str(self.config.log_dir.resolve())))
        layout.addWidget(paths_group)

        # Download settings group
        dl_group = QGroupBox("Download Settings")
        dl_form = QFormLayout(dl_group)
        dl_form.addRow("Max concurrent:", QLabel(str(self.config.max_concurrent_downloads)))
        dl_form.addRow("Max retries:", QLabel(str(self.config.max_retries)))
        dl_form.addRow("Retry delay:", QLabel(f"{self.config.retry_delay}s"))
        dl_form.addRow("Check interval:", QLabel(f"{self.config.check_interval}s"))
        dl_form.addRow("Log level:", QLabel(self.config.log_level))
        layout.addWidget(dl_group)

        # Action buttons
        buttons = QHBoxLayout()
        open_dl_btn = QPushButton("Open Downloads Folder")
        open_dl_btn.clicked.connect(lambda: self._open_folder(self.config.download_path))
        buttons.addWidget(open_dl_btn)

        open_log_btn = QPushButton("Open Log Folder")
        open_log_btn.clicked.connect(lambda: self._open_folder(self.config.log_dir))
        buttons.addWidget(open_log_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

        # Info
        info = QLabel("To change settings, edit the .env file and restart the application.")
        info.setStyleSheet("color: #888; margin-top: 10px;")
        layout.addWidget(info)

        layout.addStretch()

    def _open_folder(self, path) -> None:
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
