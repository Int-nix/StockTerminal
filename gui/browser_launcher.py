"""Shared StockTerminal browser window manager."""

from PySide6.QtCore import QObject, Qt, QUrl
from gui.browser import StockTerminalBrowser


class BrowserLauncher(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = None

    def open_url(self, url):
        if isinstance(url, QUrl):
            url = url.toString()

        if not isinstance(url, str):
            return False

        url = url.strip()
        parsed = QUrl(url)

        if parsed.scheme().lower() not in ("http", "https") or not parsed.host():
            return False

        if self.browser is None:
            browser = StockTerminalBrowser(initial_url=url)
            browser.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            browser.destroyed.connect(self.browser_closed)
            self.browser = browser
        else:
            self.browser.add_tab(url)

        if self.browser.isMinimized():
            self.browser.showNormal()
        else:
            self.browser.show()

        self.browser.raise_()
        self.browser.activateWindow()
        return True

    def browser_closed(self, *args):
        self.browser = None
