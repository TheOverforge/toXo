
"""Thin entry-point — bootstraps the Qt application and delegates to app layer."""
import sys
import platform

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import QIcon

from app.bootstrap import MainWindow
from shared.i18n import set_language
from shared.config.paths import IMAGES_DIR
from shared.ui.widgets import load_custom_fonts

_APP_KEY = "toXo_single_instance"


def _set_dark_titlebar(window, dark: bool = True):
    """Use Windows DWM API to set title bar and border colour based on theme."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        mode = ctypes.c_int(1 if dark else 0)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(mode), ctypes.sizeof(mode),
        )

        DWMWA_CAPTION_COLOR = 35
        DWMWA_BORDER_COLOR = 34
        color = ctypes.c_uint32(0x000F0D0D if dark else 0x00FBF6F3)
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(color), ctypes.sizeof(color),
        )
        dwm.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(color), ctypes.sizeof(color),
        )
    except Exception:
        pass


def main():
    app = QApplication(sys.argv)

    # Single-instance guard: if another instance is running, wake it and exit
    socket = QLocalSocket()
    socket.connectToServer(_APP_KEY)
    if socket.waitForConnected(300):
        socket.disconnectFromServer()
        sys.exit(0)

    server = QLocalServer()
    QLocalServer.removeServer(_APP_KEY)
    server.listen(_APP_KEY)

    app.setStyle("Fusion")
    load_custom_fonts()
    set_language(QSettings("todo_app", "todo_mvp").value("language", "ru"))
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(IMAGES_DIR / "app_icon.png")))
    w = MainWindow()
    w.setWindowTitle("toXo")
    w.showMaximized()
    _theme = QSettings("todo_app", "todo_mvp").value("theme", "dark")
    _set_dark_titlebar(w, dark=_theme in ("dark", "glass"))

    # When a second instance tries to connect — bring this window to front
    def _on_new_connection():
        incoming = server.nextPendingConnection()
        if incoming:
            incoming.disconnectFromServer()
        w.showNormal()
        w.showMaximized()
        w.activateWindow()
        w.raise_()

    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
