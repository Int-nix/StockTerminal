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
        # SIDEBAR
        # ======================================

        self.sidebar = QFrame()

        self.sidebar.setObjectName(
            "Sidebar"
        )

        self.sidebar.setFixedWidth(
            220
        )

        sidebar_layout = QVBoxLayout(
            self.sidebar
        )

        sidebar_layout.setContentsMargins(
            15, 25, 15, 20
        )

        sidebar_layout.setSpacing(8)

        logo = QLabel(
            "STOCK TERMINAL"
        )

        logo.setStyleSheet(
            "font-size: 19px;"
            "font-weight: bold;"
            "color: #60A5FA;"
        )

        sidebar_layout.addWidget(
            logo
        )

        sidebar_layout.addSpacing(
            30
        )

        # ======================================
        # PAGE STACK
        # ======================================

        self.pages = QStackedWidget()

        navigation = [
            ("Dashboard", 0),
            ("Stock Explorer", 1),
            ("Stock Screener", 2),
            ("News Research", 3),
            ("Watchlist", 4),
            ("Paper Trading", 5)
        ]

        for name, index in navigation:
            button = QPushButton(name)

            button.setObjectName(
                "Navigation"
            )

            button.clicked.connect(
                lambda checked=False, i=index:
                self.change_page(i)
            )

            sidebar_layout.addWidget(
                button
            )

        sidebar_layout.addStretch()

        account_name = (
            self.account_session["username"]
            if self.account_session else "Guest"
        )
        self.account_label = QLabel(f"Account: {account_name}")
        self.account_label.setObjectName("Muted")
        self.account_label.setToolTip(
            "Signed in through the Windows launcher" if self.account_session
            else "Local guest mode"
        )
        sidebar_layout.addWidget(self.account_label)


        version = QLabel(
            f"Version {APP_VERSION}"
        )

        version.setObjectName(
            "Muted"
        )

        sidebar_layout.addWidget(
            version
        )

        main_layout.addWidget(
            self.sidebar
        )

        main_layout.addWidget(
            self.pages,
            1
        )

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

    def change_page(self, index):
        self.pages.setCurrentIndex(index)

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
