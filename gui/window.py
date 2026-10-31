"""Main StockTerminal window and page navigation."""

from PySide6.QtCore import Qt, QThreadPool

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFrame,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox
)

from config import APP_NAME, APP_VERSION
from account_session import load_launcher_session

from core.database import Database
from core.watchlist_sync import AccountWatchlist, WatchlistSyncError
from core.market import MarketWorker

from gui.dashboard import DashboardMixin
from gui.explorer import ExplorerMixin
from gui.screener import ScreenerMixin
from gui.fundamentals import FundamentalsMixin
from gui.technical import TechnicalMixin
from gui.paper_trading import PaperTradingPage
from gui.theme import STYLESHEET
from gui.browser_launcher import BrowserLauncher
from gui.news_page import NewsPageMixin
from gui.research_notes import ResearchNotes


class StockTerminal(
    DashboardMixin,
    ExplorerMixin,
    TechnicalMixin,
    FundamentalsMixin,
    ScreenerMixin,
    NewsPageMixin,
    QMainWindow
):

    def __init__(self):
        super().__init__()

        self.db = Database()
        self.account_session = load_launcher_session()
        self.account_watchlist = None
        if self.account_session:
            self.account_watchlist = AccountWatchlist(self.account_session)
            try:
                self.account_watchlist.refresh()
            except WatchlistSyncError:
                pass  # Cached account data is available when offline.


        # One browser manager shared by every StockTerminal page.
        self.browser_launcher = BrowserLauncher(self)

        self.threadpool = (
            QThreadPool.globalInstance()
        )

        # ======================================
        # INITIAL STOCK STATE
        # ======================================

        # No stock is selected when StockTerminal
        # first launches.
        #
        # The user must search for a ticker or
        # select a stock from the watchlist.

        self.current_ticker = None

        # Default chart period, not a default stock.
        self.current_period = "1y"

        self.active_workers = set()
        self.index_workers = {}

        self.setWindowTitle(
            f"{APP_NAME} v{APP_VERSION}"
        )

        self.resize(1500, 900)
        self.setMinimumSize(1100, 700)

        self.setStyleSheet(
            STYLESHEET
        )

        self.build_interface()

        # ======================================
        # STARTUP
        # ======================================

        # Do not automatically search for AAPL
        # or any other individual stock.
        #
        # Market indices still load normally.

        self.refresh_indices()

    def build_interface(self):
        central = QWidget()

        self.setCentralWidget(
            central
        )

        main_layout = QHBoxLayout(
            central
        )

        main_layout.setContentsMargins(
            0, 0, 0, 0
        )

        main_layout.setSpacing(0)

        # ======================================
        # STOCKTERMINAL NAVIGATION / SIDEBAR
        # ======================================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(244)
        self.sidebar.setStyleSheet("""
            QFrame#Sidebar {
                background-color: #0a1423;
                border: none;
                border-right: 1px solid #22364d;
            }
            QFrame#Sidebar QLabel#BrandTitle {
                color: #f3f7ff; font-size: 17px; font-weight: 800;
                background: transparent; border: none;
            }
            QFrame#Sidebar QLabel#BrandSubtitle {
                color: #6f90b7; font-size: 10px; letter-spacing: 1px;
                background: transparent; border: none;
            }
            QFrame#Sidebar QLabel#NavSection {
                color: #7189a9; font-size: 10px; font-weight: 700;
                padding: 12px 10px 5px 10px; background: transparent;
                border: none;
            }
            QFrame#Sidebar QPushButton#Navigation {
                color: #a8bed8; background-color: transparent;
                border: 1px solid transparent; border-radius: 9px;
                padding: 12px 12px; text-align: left;
                font-size: 12px; font-weight: 600;
            }
            QFrame#Sidebar QPushButton#Navigation:hover {
                color: #f1f6ff; background-color: #172b45;
                border-color: #263d5b;
            }
            QFrame#Sidebar QPushButton#Navigation:checked {
                color: #ffffff; background-color: #194a8a;
                border: 1px solid #3277cf;
            }
            QFrame#Sidebar QFrame#AccountPanel {
                background-color: #101f33; border: 1px solid #243951;
                border-radius: 10px;
            }
            QFrame#Sidebar QLabel#AccountName {
                color: #f0f5ff; font-weight: 700; font-size: 12px;
                background: transparent; border: none;
            }
            QFrame#Sidebar QLabel#AccountMeta {
                color: #829bb8; font-size: 10px;
                background: transparent; border: none;
            }
            QFrame#Sidebar QPushButton#SidebarToggle {
                background: #152840; color: #a7c5e9;
                border: 1px solid #2b4462; border-radius: 7px;
                padding: 6px; font-weight: 700;
            }
            QFrame#Sidebar QPushButton#SidebarToggle:hover {
                background: #22456d; color: white;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(13, 18, 13, 16)
        sidebar_layout.setSpacing(5)

        brand_row = QHBoxLayout()
        brand_icon = QLabel("ST")
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setFixedSize(38, 38)
        brand_icon.setStyleSheet(
            "background:#1e5db3; color:white; border-radius:10px;"
            "font-size:15px; font-weight:900;"
        )
        brand_row.addWidget(brand_icon)
        brand_text = QWidget()
        brand_text_layout = QVBoxLayout(brand_text)
        brand_text_layout.setContentsMargins(7, 0, 0, 0)
        brand_text_layout.setSpacing(1)
        logo = QLabel("STOCKTERMINAL")
        logo.setObjectName("BrandTitle")
        tagline = QLabel("MARKET INTELLIGENCE")
        tagline.setObjectName("BrandSubtitle")
        brand_text_layout.addWidget(logo)
        brand_text_layout.addWidget(tagline)
        brand_row.addWidget(brand_text, 1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(26)

        # Page indices match the order in which pages are built below.
        self.pages = QStackedWidget()
        self.nav_buttons = {}
        self.nav_sections = []
        self.nav_labels = {}
        navigation_sections = [
            ("WORKSPACE", [
                ("Dashboard", "▦", 0),
                ("Stock Explorer", "⌕", 1),
                ("Stock Screener", "▤", 2),
                ("News Research", "◫", 3),
            ]),
            ("PORTFOLIO", [
                ("Watchlist", "☆", 4),
                ("Paper Trading", "◈", 5),
            ]),
        ]
        for section_name, entries in navigation_sections:
            section_label = QLabel(section_name)
            section_label.setObjectName("NavSection")
            sidebar_layout.addWidget(section_label)
            self.nav_sections.append(section_label)
            for name, symbol, index in entries:
                button = QPushButton(f"{symbol}    {name}")
                button.setObjectName("Navigation")
                button.setCheckable(True)
                button.setCursor(Qt.PointingHandCursor)
                button.setMinimumHeight(43)
                button.setToolTip(name)
                button.clicked.connect(
                    lambda checked=False, i=index: self.change_page(i)
                )
                sidebar_layout.addWidget(button)
                self.nav_buttons[index] = button
                self.nav_labels[index] = (name, symbol)

        self.nav_buttons[0].setChecked(True)
        sidebar_layout.addStretch(1)

        account_name = (
            self.account_session["username"]
            if self.account_session else "Guest"
        )
        account_panel = QFrame()
        account_panel.setObjectName("AccountPanel")
        account_layout = QVBoxLayout(account_panel)
        account_layout.setContentsMargins(12, 10, 12, 10)
        account_layout.setSpacing(4)
        self.account_label = QLabel(account_name)
        self.account_label.setObjectName("AccountName")
        self.account_label.setToolTip(
            "Signed in through the Windows launcher"
            if self.account_session else "Local guest mode"
        )
        account_layout.addWidget(self.account_label)
        version = QLabel(f"{'CONNECTED ACCOUNT' if self.account_session else 'LOCAL SESSION'}  ·  v{APP_VERSION}")
        version.setObjectName("AccountMeta")
        account_layout.addWidget(version)
        sidebar_layout.addWidget(account_panel)

        self.sidebar_toggle = QPushButton("◀  Collapse sidebar")
        self.sidebar_toggle.setObjectName("SidebarToggle")
        self.sidebar_toggle.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.sidebar_toggle)
        self.sidebar_brand_text = brand_text
        self.sidebar_account_panel = account_panel
        self.sidebar_collapsed = False

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages, 1)

        # ======================================
        # BUILD APPLICATION PAGES
        # ======================================

        self.build_dashboard()

        self.build_explorer()

        self.build_technical()

        self.build_fundamentals()

        # Move the actual analysis pages into Explorer's tabs.
        # Their widgets, workers and functionality stay intact.
        technical_page = self.pages.widget(2)
        fundamental_page = self.pages.widget(3)
        self.pages.removeWidget(technical_page)
        self.pages.removeWidget(fundamental_page)
        self.explorer_tabs.addTab(technical_page, "Technical Analysis")
        self.explorer_tabs.addTab(fundamental_page, "Fundamental Analysis")

        self.research_notes = ResearchNotes(self)
        self.explorer_tabs.addTab(self.research_notes, "Research Notes")

        self.build_screener()

        self.build_news_page()

        self.build_watchlist()

        # ======================================
        # PAPER TRADING — PAGE 6
        # ======================================

        self.paper_trading_page = PaperTradingPage(account_session=self.account_session)

        self.pages.addWidget(
            self.paper_trading_page
        )

        # ======================================
        # INITIAL EXPLORER STATE
        # ======================================

        # The Explorer should show a helpful
        # message instead of "Loading..."
        # when no ticker has been searched.

        self.company_label.setText(
            "Search for a stock to begin exploring."
        )

        self.statusBar().showMessage(
            "StockTerminal ready — no stock selected"
        )

    def closeEvent(self, event):
        # Flush edits even if the auto-save timer has not fired yet.
        self.research_notes.save_timer.stop()
        self.research_notes.save()
        super().closeEvent(event)

    # ==========================================
    # NAVIGATION
    # ==========================================

    def toggle_sidebar(self):
        """Collapse to icons or restore the full navigation labels."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        collapsed = self.sidebar_collapsed
        self.sidebar.setFixedWidth(70 if collapsed else 244)
        self.sidebar_brand_text.setVisible(not collapsed)
        self.sidebar_account_panel.setVisible(not collapsed)
        for label in self.nav_sections:
            label.setVisible(not collapsed)
        for index, button in self.nav_buttons.items():
            name, symbol = self.nav_labels[index]
            button.setText(symbol if collapsed else f"{symbol}    {name}")
            button.setStyleSheet(
                "text-align: center; padding: 10px 2px;" if collapsed else ""
            )
        self.sidebar_toggle.setText("▶" if collapsed else "◀  Collapse sidebar")

    def change_page(self, index):
        self.pages.setCurrentIndex(index)
        for page_index, button in self.nav_buttons.items():
            button.setChecked(page_index == index)

        if index == 1:
            self.explorer_analysis_tab_changed(
                self.explorer_tabs.currentIndex()
            )
        elif index == 4:
            self.refresh_watchlist_table()
        elif index == 5:
            self.paper_trading_page.refresh()

    # ==========================================
    # WATCHLIST PAGE
    # ==========================================

    def build_watchlist(self):
        page = QWidget()

        layout = QVBoxLayout(page)

        layout.setContentsMargins(
            30, 25, 30, 25
        )

        layout.setSpacing(15)

        title = QLabel(
            "My Watchlist"
        )

        title.setObjectName(
            "Title"
        )

        layout.addWidget(
            title
        )

        controls = QHBoxLayout()

        self.watchlist_input = QLineEdit()

        self.watchlist_input.setPlaceholderText(
            "Enter ticker to add..."
        )

        add_button = QPushButton(
            "Add Stock"
        )

        add_button.setObjectName(
            "Primary"
        )

        add_button.clicked.connect(
            self.add_watchlist_from_input
        )

        refresh_button = QPushButton(
            "Refresh Prices"
        )

        refresh_button.clicked.connect(
            self.refresh_watchlist_prices
        )

        remove_button = QPushButton(
            "Remove Selected"
        )

        remove_button.clicked.connect(
            self.remove_selected_watchlist
        )

        controls.addWidget(
            self.watchlist_input
        )

        controls.addWidget(
            add_button
        )

        controls.addWidget(
            refresh_button
        )

        controls.addWidget(
            remove_button
        )

        if self.account_watchlist:
            import_button = QPushButton("Import Local Watchlist")
            import_button.clicked.connect(self.import_local_watchlist)
            controls.addWidget(import_button)

        layout.addLayout(
            controls
        )

        self.watchlist_table = QTableWidget()

        self.watchlist_table.setColumnCount(
            3
        )

        self.watchlist_table.setHorizontalHeaderLabels([
            "Ticker",
            "Last Close",
            "Price Date"
        ])

        self.watchlist_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.watchlist_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.watchlist_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.watchlist_table.cellDoubleClicked.connect(
            self.open_watchlist_stock
        )

        layout.addWidget(
            self.watchlist_table
        )

        self.pages.addWidget(
            page
        )

        self.refresh_watchlist_table()

    # ==========================================
    # ACCOUNT WATCHLIST ADAPTER
    # ==========================================

    def _get_watchlist(self):
        if self.account_watchlist:
            return self.account_watchlist.get_watchlist()
        return self.db.get_watchlist()

    def _add_watchlist(self, ticker):
        if self.account_watchlist:
            try:
                self.account_watchlist.add(ticker)
            except WatchlistSyncError as exc:
                QMessageBox.warning(self, "Watchlist sync", str(exc))
                return False
        else:
            self.db.add_watchlist(ticker)
        return True

    def _remove_watchlist(self, ticker):
        if self.account_watchlist:
            try:
                self.account_watchlist.remove(ticker)
            except WatchlistSyncError as exc:
                QMessageBox.warning(self, "Watchlist sync", str(exc))
                return False
        else:
            self.db.remove_watchlist(ticker)
        return True

    def import_local_watchlist(self):
        """Explicit one-time import; never silently mix Guest and account stocks."""
        if not self.account_watchlist:
            return
        local = self.db.get_watchlist()
        if not local:
            QMessageBox.information(self, "Import watchlist", "No local stocks to import.")
            return
        answer = QMessageBox.question(
            self, "Import local watchlist",
            f"Merge {len(local)} local stock(s) into your account watchlist? "
            "Your local watchlist will be kept unchanged.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.account_watchlist.merge(local)
            self.refresh_watchlist_table()
            self.update_watchlist_button()
        except WatchlistSyncError as exc:
            QMessageBox.warning(self, "Import failed", str(exc))

    # ==========================================
    # REFRESH WATCHLIST TABLE
    # ==========================================

    def refresh_watchlist_table(self):
        tickers = self._get_watchlist()

        self.watchlist_table.setRowCount(
            len(tickers)
        )

        for row, ticker in enumerate(
            tickers
        ):
            price_data = (
                self.db.get_latest_price(
                    ticker
                )
            )

            price = "--"
            date = "--"

            if price_data:
                price = (
                    f"{price_data[0]:,.2f}"
                )

                date = price_data[1]

            values = [
                ticker,
                price,
                date
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                self.watchlist_table.setItem(
                    row,
                    column,
                    item
                )

    # ==========================================
    # ADD CURRENT STOCK TO WATCHLIST
    # ==========================================

    def add_current_to_watchlist(self):
        if not self.current_ticker:
            return

        if not self._add_watchlist(self.current_ticker):
            return

        self.update_watchlist_button()

        self.refresh_watchlist_table()

        self.statusBar().showMessage(
            f"{self.current_ticker} added to watchlist"
        )

    # ==========================================
    # UPDATE WATCHLIST BUTTON
    # ==========================================

    def update_watchlist_button(self):
        tickers = self._get_watchlist()

        if self.current_ticker in tickers:
            self.watchlist_button.setText(
                "Already in Watchlist"
            )

            self.watchlist_button.setEnabled(
                False
            )

        else:
            self.watchlist_button.setText(
                "Add to Watchlist"
            )

            self.watchlist_button.setEnabled(
                True
            )

    # ==========================================
    # ADD STOCK FROM WATCHLIST INPUT
    # ==========================================

    def add_watchlist_from_input(self):
        ticker = (
            self.watchlist_input.text()
            .strip()
            .upper()
        )

        if not ticker:
            return

        if not self._add_watchlist(ticker):
            return

        self.watchlist_input.clear()

        self.refresh_watchlist_table()

        self.statusBar().showMessage(
            f"{ticker} added to watchlist"
        )

    # ==========================================
    # REMOVE SELECTED WATCHLIST STOCK
    # ==========================================

    def remove_selected_watchlist(self):
        row = (
            self.watchlist_table.currentRow()
        )

        if row < 0:
            return

        item = (
            self.watchlist_table.item(
                row,
                0
            )
        )

        if item is None:
            return

        ticker = item.text()

        if not self._remove_watchlist(ticker):
            return

        self.refresh_watchlist_table()

        self.update_watchlist_button()

    # ==========================================
    # OPEN WATCHLIST STOCK
    # ==========================================

    def open_watchlist_stock(
        self,
        row,
        column
    ):
        item = (
            self.watchlist_table.item(
                row,
                0
            )
        )

        if item is None:
            return

        ticker = item.text()

        self.change_page(1)

        self.load_stock(
            ticker
        )

    # ==========================================
    # REFRESH WATCHLIST PRICES
    # ==========================================

    def refresh_watchlist_prices(self):
        tickers = (
            self._get_watchlist()
        )

        if not tickers:
            return

        self.statusBar().showMessage(
            "Refreshing watchlist prices..."
        )

        self.pending_watchlist = (
            len(tickers)
        )

        for ticker in tickers:
            worker = MarketWorker(
                ticker,
                "1mo"
            )

            self.active_workers.add(
                worker
            )

            worker.signals.finished.connect(
                lambda data, w=worker:
                self.watchlist_data_loaded(
                    data,
                    w
                )
            )

            worker.signals.error.connect(
                lambda error, w=worker:
                self.watchlist_refresh_error(
                    error,
                    w
                )
            )

            self.threadpool.start(
                worker
            )

    # ==========================================
    # WATCHLIST DATA LOADED
    # ==========================================

    def watchlist_data_loaded(
        self,
        data,
        worker
    ):
        self.active_workers.discard(
            worker
        )

        self.db.save_stock(
            data["ticker"],
            data["info"]
        )

        self.db.save_history(
            data["ticker"],
            data["history"]
        )

        self.pending_watchlist -= 1

        self.refresh_watchlist_table()

        if self.pending_watchlist <= 0:
            self.statusBar().showMessage(
                "Watchlist refresh complete"
            )

    # ==========================================
    # WATCHLIST REFRESH ERROR
    # ==========================================

    def watchlist_refresh_error(
        self,
        error,
        worker
    ):
        self.active_workers.discard(
            worker
        )

        self.pending_watchlist -= 1

        self.statusBar().showMessage(
            f"Watchlist error: {error}"
        )

    # ==========================================
    # PLACEHOLDER SUPPORT
    # ==========================================

    def build_placeholder(
        self,
        title,
        description
    ):
        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setContentsMargins(
            30, 30, 30, 30
        )

        heading = QLabel(
            title
        )

        heading.setObjectName(
            "Title"
        )

        description_label = QLabel(
            description
        )

        description_label.setObjectName(
            "Muted"
        )

        layout.addWidget(
            heading
        )

        layout.addWidget(
            description_label
        )

        layout.addStretch()

        self.pages.addWidget(
            page
        )
