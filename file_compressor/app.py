from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __version__
from .gui import MainWindow

ICON_PATH = Path(__file__).resolve().parent / "resources" / "icon.png"


def _set_windows_app_id() -> None:
    # Without an explicit AppUserModelID, Windows groups the window under python.exe
    # and shows the Python icon in the taskbar when running from source.
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FileCompressor.App")


def main() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("File Compressor")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("file-compressor")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
