"""Main application window with sidebar navigation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.async_bridge import AsyncBridge
from src.gui.pages.downloads_page import DownloadsPage
from src.gui.pages.history_page import HistoryPage
from src.gui.pages.scheduler_page import SchedulerPage
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.subscriptions_page import SubscriptionsPage
from src.gui.widgets.status_bar import StatusBar

NAV_ITEMS = [
    ("Downloads", "Active downloads and queue"),
    ("Subscriptions", "Manage channel subscriptions"),
    ("History", "Download history"),
    ("Scheduler", "Auto-download scheduler"),
    ("Settings", "Configuration"),
]


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, bridge: AsyncBridge) -> None:
        super().__init__()
        self.bridge = bridge

        self.setWindowTitle("Telegram Downloader")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        self._build_ui()

        # Connect signals
        bridge.connection_failed.connect(self._on_connection_failed)
        bridge.error_occurred.connect(self._on_error)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content area (sidebar + pages)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Pages (create before sidebar so nav_list can connect to stack)
        self.stack = QStackedWidget()

        # Sidebar
        sidebar = self._build_sidebar()
        content_layout.addWidget(sidebar)
        self.pages = {
            "downloads": DownloadsPage(self.bridge),
            "subscriptions": SubscriptionsPage(self.bridge),
            "history": HistoryPage(self.bridge),
            "scheduler": SchedulerPage(self.bridge),
            "settings": SettingsPage(self.bridge),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        content_layout.addWidget(self.stack, 1)
        main_layout.addWidget(content, 1)

        # Status bar
        self.status_bar = StatusBar(self.bridge)
        self.status_bar.setStyleSheet(
            "background-color: #f0f0f0; border-top: 1px solid #ccc;"
        )
        main_layout.addWidget(self.status_bar)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(
            "background-color: #2c3e50; color: white;"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("Telegram\nDownloader")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("", 14, QFont.Bold))
        title.setStyleSheet(
            "color: white; padding: 20px 10px; "
            "border-bottom: 1px solid #34495e;"
        )
        layout.addWidget(title)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #bdc3c7;
                padding: 12px 20px;
                border-bottom: 1px solid #34495e;
            }
            QListWidget::item:selected {
                background-color: #34495e;
                color: white;
                font-weight: bold;
            }
            QListWidget::item:hover:!selected {
                background-color: #3d566e;
            }
        """)

        for name, tooltip in NAV_ITEMS:
            item = QListWidgetItem(name)
            item.setToolTip(tooltip)
            self.nav_list.addItem(item)

        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        layout.addWidget(self.nav_list, 1)
        return sidebar

    def _on_connection_failed(self, msg: str) -> None:
        QMessageBox.warning(self, "Connection Failed", msg)

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)

    def closeEvent(self, event) -> None:
        """Clean shutdown on window close."""
        self.bridge.stop_loop()
        self.bridge.wait(5000)
        event.accept()
