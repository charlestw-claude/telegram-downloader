"""Desktop GUI application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.core.config import Config
from src.gui.async_bridge import AsyncBridge
from src.gui.main_window import MainWindow


def main(env_path: str | None = None) -> None:
    """Launch the desktop GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Telegram Downloader")
    app.setStyle("Fusion")

    # Load config
    config = Config.from_env(env_path)
    errors = config.validate()
    if errors:
        QMessageBox.critical(
            None,
            "Configuration Error",
            "Please fix your .env file:\n\n" + "\n".join(f"- {e}" for e in errors),
        )
        sys.exit(1)

    # Start async bridge
    bridge = AsyncBridge(config)
    bridge.start()

    # Create and show main window
    window = MainWindow(bridge)
    window.show()

    exit_code = app.exec()

    # Clean shutdown
    bridge.stop_loop()
    bridge.wait(10000)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
