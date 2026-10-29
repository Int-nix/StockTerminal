import sys

from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QProgressBar,
    QTabWidget,
    QTabBar,
    QMainWindow,
    QSizePolicy,
)

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage


# ==============================================
# CONFIGURATION
# ==============================================

HOME_URL = "https://finance.yahoo.com"

COLORS = {
    "background": "#0b1015",
    "surface": "#121a22",
    "surface_alt": "#17232d",
    "border": "#263541",
    "text": "#dce7ee",
    "muted": "#7f95a5",
    "green": "#00d084",
}


# ==============================================
# CUSTOM WEB ENGINE VIEW
# ==============================================

class StockWebView(QWebEngineView):

    def __init__(self, browser):
        super().__init__()

        self.browser = browser

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

    def createWindow(self, window_type):
        """
        When a website requests a new window,
        open it inside a StockTerminal Browser tab.
        """

        return self.browser.add_tab(
            url=None,
            switch=True
        ).web


# ==============================================
# BROWSER TAB
# ==============================================

class BrowserTab(QWidget):

    def __init__(self, browser, url=None):
        super().__init__()

        self.browser = browser

        # ==========================================
        # MAIN TAB LAYOUT
        # ==========================================

        self.main_layout = QVBoxLayout(self)

        self.main_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.main_layout.setSpacing(0)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        # ==========================================
        # NAVIGATION TOOLBAR
        # ==========================================

        self.toolbar = QWidget()
        self.toolbar.setObjectName("browserToolbar")

        self.toolbar.setFixedHeight(48)

        toolbar_layout = QHBoxLayout(self.toolbar)

        toolbar_layout.setContentsMargins(
            10, 5, 10, 5
        )

        toolbar_layout.setSpacing(6)

        # Navigation buttons

        self.back_button = QPushButton("◀")
        self.forward_button = QPushButton("▶")
        self.reload_button = QPushButton("↻")
        self.home_button = QPushButton("⌂")

        for button in (
            self.back_button,
            self.forward_button,
            self.reload_button,
            self.home_button,
        ):

            button.setFixedSize(34, 32)

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            toolbar_layout.addWidget(button)

        # ==========================================
        # ADDRESS BAR
        # ==========================================

        self.address = QLineEdit()

        self.address.setPlaceholderText(
            "Search or enter a website address..."
        )

        self.address.setFixedHeight(32)

        self.address.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        toolbar_layout.addWidget(
            self.address,
            1
        )

        # ==========================================
        # MAIN WEB VIEW
        # ==========================================

        self.web = StockWebView(browser)

        # ==========================================
        # LOADING PROGRESS BAR
        # ==========================================

        self.progress = QProgressBar()

        self.progress.setFixedHeight(3)

        self.progress.setTextVisible(False)

        self.progress.setRange(0, 100)

        self.progress.hide()

        # ==========================================
        # STATUS BAR
        # ==========================================

        self.status = QLabel("Ready")

        self.status.setObjectName(
            "browserStatus"
        )

        self.status.setFixedHeight(23)

        # ==========================================
        # LAYOUT ASSEMBLY
        # ==========================================

        self.main_layout.addWidget(
            self.toolbar,
            0
        )

        self.main_layout.addWidget(
            self.progress,
            0
        )

        # IMPORTANT:
        # Stretch factor 1 means the webpage receives
        # all remaining vertical space.

        self.main_layout.addWidget(
            self.web,
            1
        )

        self.main_layout.addWidget(
            self.status,
            0
        )

        # ==========================================
        # BUTTON CONNECTIONS
        # ==========================================

        self.back_button.clicked.connect(
            self.web.back
        )

        self.forward_button.clicked.connect(
            self.web.forward
        )

        self.reload_button.clicked.connect(
            self.web.reload
        )

        self.home_button.clicked.connect(
            self.go_home
        )

        self.address.returnPressed.connect(
            self.navigate
        )

        # ==========================================
        # WEB ENGINE SIGNALS
        # ==========================================

        self.web.urlChanged.connect(
            self.update_address
        )

        self.web.loadStarted.connect(
            self.loading_started
        )

        self.web.loadProgress.connect(
            self.update_progress
        )

        self.web.loadFinished.connect(
            self.finished_loading
        )

        self.web.titleChanged.connect(
            self.update_title
        )

        # ==========================================
        # INITIAL PAGE
        # ==========================================

        if url:
            self.load_url(url)

    # ==============================================
    # NAVIGATION
    # ==============================================

    def load_url(self, url):

        if isinstance(url, QUrl):
            self.web.setUrl(url)

        else:
            self.web.setUrl(
                QUrl(str(url))
            )

    def navigate(self):

        text = self.address.text().strip()

        if not text:
            return

        if "://" not in text:

            if "." in text and " " not in text:

                text = "https://" + text

            else:

                text = (
                    "https://www.google.com/search?q="
                    + quote_plus(text)
                )

        self.load_url(text)

    def go_home(self):

        self.load_url(HOME_URL)

    # ==============================================
    # ADDRESS BAR
    # ==============================================

    def update_address(self, url):

        self.address.setText(
            url.toString()
        )

        self.address.setCursorPosition(0)

        self.back_button.setEnabled(
            self.web.history().canGoBack()
        )

        self.forward_button.setEnabled(
            self.web.history().canGoForward()
        )

    # ==============================================
    # LOADING
    # ==============================================

    def loading_started(self):

        self.progress.show()

        self.progress.setValue(0)

        self.status.setText(
            "Loading page..."
        )

    def update_progress(self, progress):

        self.progress.setValue(progress)

        self.status.setText(
            f"Loading... {progress}%"
        )

    def finished_loading(self, success):

        self.progress.hide()

        if success:

            self.status.setText(
                "Page loaded"
            )

        else:

            self.status.setText(
                "Unable to load page"
            )

        self.back_button.setEnabled(
            self.web.history().canGoBack()
        )

        self.forward_button.setEnabled(
            self.web.history().canGoForward()
        )

    # ==============================================
    # TITLE
    # ==============================================

    def update_title(self, title):

        self.browser.update_tab_title(
            self,
            title
        )


# ==============================================
# STOCKTERMINAL BROWSER WINDOW
# ==============================================

class StockTerminalBrowser(QMainWindow):

    def __init__(self, initial_url=None):
        super().__init__()

        # ==========================================
        # WINDOW SETTINGS
        # ==========================================

        self.setWindowTitle(
            "StockTerminal Browser"
        )

        self.resize(
            1280,
            850
        )

        self.setMinimumSize(
            700,
            450
        )

        # ==========================================
        # CENTRAL WIDGET
        # ==========================================

        self.central = QWidget()

        self.central.setObjectName(
            "browserCentral"
        )

        self.central_layout = QVBoxLayout(
            self.central
        )

        self.central_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.central_layout.setSpacing(0)

        self.setCentralWidget(
            self.central
        )

        # ==========================================
        # TAB WIDGET
        # ==========================================

        self.tabs = QTabWidget()

        self.tabs.setDocumentMode(True)

        self.tabs.setTabsClosable(True)

        self.tabs.setMovable(True)

        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.tabs.tabCloseRequested.connect(
            self.close_tab
        )

        self.tabs.currentChanged.connect(
            self.update_title
        )

        # ==========================================
        # NEW TAB BUTTON
        # ==========================================

        self.new_tab_button = QPushButton("+")

        self.new_tab_button.setObjectName(
            "newTabButton"
        )

        self.new_tab_button.setFixedSize(
            32,
            27
        )

        self.new_tab_button.setToolTip(
            "New Tab (Ctrl+T)"
        )

        self.new_tab_button.clicked.connect(
            lambda: self.add_tab(HOME_URL)
        )

        self.tabs.setCornerWidget(
            self.new_tab_button,
            Qt.Corner.TopRightCorner
        )

        # ==========================================
        # ADD TABS TO LAYOUT
        # ==========================================

        self.central_layout.addWidget(
            self.tabs,
            1
        )

        # ==========================================
        # KEYBOARD SHORTCUTS
        # ==========================================

        self.setup_shortcuts()

        # ==========================================
        # INITIAL TAB
        # ==========================================

        self.add_tab(
            initial_url or HOME_URL
        )

        # ==========================================
        # STYLING
        # ==========================================

        self.apply_style()

    # ==============================================
    # NEW TAB
    # ==============================================

    def add_tab(
        self,
        url=None,
        switch=True
    ):

        tab = BrowserTab(
            self,
            url
        )

        index = self.tabs.addTab(
            tab,
            "New Tab"
        )

        if switch:

            self.tabs.setCurrentIndex(
                index
            )

        return tab

    # ==============================================
    # CLOSE TAB
    # ==============================================

    def close_tab(self, index):

        widget = self.tabs.widget(
            index
        )

        if widget is None:
            return

        self.tabs.removeTab(
            index
        )

        widget.deleteLater()

        if self.tabs.count() == 0:
            self.close()

    # ==============================================
    # UPDATE TAB TITLE
    # ==============================================

    def update_tab_title(
        self,
        tab,
        title
    ):

        index = self.tabs.indexOf(
            tab
        )

        if index < 0:
            return

        if not title:
            title = "New Tab"

        if len(title) > 28:
            display_title = title[:28] + "..."
        else:
            display_title = title

        self.tabs.setTabText(
            index,
            display_title
        )

        self.tabs.setTabToolTip(
            index,
            title
        )

        if self.tabs.currentWidget() is tab:

            self.setWindowTitle(
                f"{title} - StockTerminal Browser"
            )

    # ==============================================
    # UPDATE WINDOW TITLE
    # ==============================================

    def update_title(self, index=None):

        tab = self.tabs.currentWidget()

        if tab is None:

            self.setWindowTitle(
                "StockTerminal Browser"
            )

            return

        title = tab.web.title()

        if title:

            self.setWindowTitle(
                f"{title} - StockTerminal Browser"
            )

        else:

            self.setWindowTitle(
                "StockTerminal Browser"
            )

    # ==============================================
    # SHORTCUTS
    # ==============================================

    def setup_shortcuts(self):

        self.shortcuts = []

        shortcuts = [
            ("Ctrl+T", self.new_tab),
            ("Ctrl+W", self.close_current_tab),
            ("Ctrl+L", self.focus_address),
            ("Ctrl+R", self.reload_current_tab),
            ("F5", self.reload_current_tab),
        ]

        for key, callback in shortcuts:

            shortcut = QShortcut(
                QKeySequence(key),
                self
            )

            shortcut.activated.connect(
                callback
            )

            self.shortcuts.append(
                shortcut
            )

    def new_tab(self):

        self.add_tab(
            HOME_URL
        )

    def close_current_tab(self):

        index = self.tabs.currentIndex()

        if index >= 0:

            self.close_tab(
                index
            )

    def focus_address(self):

        tab = self.tabs.currentWidget()

        if tab:

            tab.address.setFocus()

            tab.address.selectAll()

    def reload_current_tab(self):

        tab = self.tabs.currentWidget()

        if tab:

            tab.web.reload()

    # ==============================================
    # STYLING
    # ==============================================

    def apply_style(self):

        self.setStyleSheet(f"""

            /* =====================================
               MAIN WINDOW
               ===================================== */

            QMainWindow {{
                background-color: {COLORS['background']};
            }}

            QWidget#browserCentral {{
                background-color: {COLORS['background']};
            }}

            /* =====================================
               NAVIGATION TOOLBAR
               ===================================== */

            QWidget#browserToolbar {{
                background-color: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border']};
            }}

            /* =====================================
               NAVIGATION BUTTONS
               ===================================== */

            QPushButton {{
                background-color: #1c2933;
                color: {COLORS['text']};

                border: 1px solid {COLORS['border']};
                border-radius: 5px;

                padding: 4px;
            }}

            QPushButton:hover {{
                background-color: #304653;
                color: {COLORS['green']};
            }}

            QPushButton:disabled {{
                color: #455764;
                background-color: #131d25;
            }}

            /* =====================================
               ADDRESS BAR
               ===================================== */

            QLineEdit {{
                background-color: #090e13;
                color: {COLORS['text']};

                border: 1px solid {COLORS['border']};
                border-radius: 5px;

                padding: 6px 10px;
            }}

            QLineEdit:focus {{
                border: 1px solid {COLORS['green']};
            }}

            /* =====================================
               TABS
               ===================================== */

            QTabWidget::pane {{
                border: none;
                background-color: {COLORS['background']};
            }}

            QTabBar {{
                background-color: #090e13;
            }}

            QTabBar::tab {{
                background-color: #17232d;
                color: #8da4b3;

                min-width: 100px;
                max-width: 220px;

                padding: 9px 16px;

                border-right: 1px solid #263541;
            }}

            QTabBar::tab:selected {{
                background-color: #253a45;
                color: {COLORS['green']};
            }}

            QTabBar::tab:hover {{
                background-color: #304653;
            }}

            /* =====================================
               NEW TAB BUTTON
               ===================================== */

            QPushButton#newTabButton {{
                background-color: #17232d;
                color: {COLORS['green']};

                border: 1px solid {COLORS['border']};
                border-radius: 4px;

                font-size: 18px;
                font-weight: bold;
            }}

            QPushButton#newTabButton:hover {{
                background-color: #304653;
            }}

            /* =====================================
               STATUS BAR
               ===================================== */

            QLabel#browserStatus {{
                background-color: {COLORS['surface']};
                color: {COLORS['muted']};

                padding-left: 12px;

                border-top: 1px solid {COLORS['border']};

                font-size: 11px;
            }}

            /* =====================================
               LOADING BAR
               ===================================== */

            QProgressBar {{
                border: none;
                background-color: #121a22;
            }}

            QProgressBar::chunk {{
                background-color: {COLORS['green']};
            }}

        """)


# ==============================================
# STANDALONE TEST
# ==============================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    browser = StockTerminalBrowser()

    browser.show()

    sys.exit(app.exec())
