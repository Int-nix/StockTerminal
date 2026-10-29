"""StockTerminal market dashboard with categorized news."""

import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QTabBar,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QScrollArea
)

from config import COLORS
from core.market import IndexWorker
from core.news import CATEGORIES, NewsWorker
from core.movers import MoversWorker


def create_card(title, value="--", subtitle=""):
    frame = QFrame()
    frame.setObjectName("Card")

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 15, 18, 15)

    title_label = QLabel(title)
    title_label.setObjectName("Muted")

    value_label = QLabel(value)
    value_label.setStyleSheet(
        "font-size: 23px; font-weight: bold;"
    )

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("Muted")

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addWidget(subtitle_label)

    return frame, value_label, subtitle_label


class DashboardMixin:

    def build_dashboard(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 25, 30, 30)
        layout.setSpacing(16)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ==========================================
        # DASHBOARD HEADER
        # ==========================================

        title = QLabel("Market Dashboard")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Your investment research workspace"
        )
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        # ==========================================
        # MARKET INDEX CARDS
        # ==========================================

        cards = QHBoxLayout()
        self.dashboard_cards = {}

        for ticker, name in [
            ("^GSPC", "S&P 500"),
            ("^IXIC", "NASDAQ"),
            ("^DJI", "DOW JONES"),
            ("^GSPTSE", "TSX")
        ]:
            card, value, change = create_card(name)
            cards.addWidget(card)

            self.dashboard_cards[ticker] = (
                value,
                change
            )

        layout.addLayout(cards)

        # ==========================================
        # INDEX REFRESH
        # ==========================================

        refresh_row = QHBoxLayout()

        self.indices_status = QLabel(
            "Fetching index prices..."
        )
        self.indices_status.setObjectName("Muted")

        self.refresh_indices_button = QPushButton(
            "Refresh Indices"
        )
        self.refresh_indices_button.clicked.connect(
            self.refresh_indices
        )

        refresh_row.addWidget(self.indices_status)
        refresh_row.addStretch()
        refresh_row.addWidget(
            self.refresh_indices_button
        )

        layout.addLayout(refresh_row)

        # ==========================================
        # QUICK STOCK SEARCH
        # ==========================================

        section = QLabel("Quick Stock Search")
        section.setObjectName("SectionTitle")
        layout.addWidget(section)

        search_row = QHBoxLayout()

        self.dashboard_search = QLineEdit()
        self.dashboard_search.setPlaceholderText(
            "Enter ticker: AAPL, MSFT, NVDA, TD.TO..."
        )

        self.dashboard_search.returnPressed.connect(
            self.search_dashboard
        )

        search_button = QPushButton("Search Stock")
        search_button.setObjectName("Primary")
        search_button.clicked.connect(
            self.search_dashboard
        )

        search_row.addWidget(self.dashboard_search)
        search_row.addWidget(search_button)

        layout.addLayout(search_row)

        info = QLabel(
            "Search for a company to view its historical prices, "
            "candlestick chart and financial information."
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")
        layout.addWidget(info)

        # ==========================================
        # BIGGEST MOVERS TODAY
        # ==========================================

        movers_header = QHBoxLayout()
        movers_title = QLabel("Biggest Movers Today")
        movers_title.setObjectName("SectionTitle")
        movers_header.addWidget(movers_title)
        movers_header.addStretch()

        self.movers_direction = QComboBox()
        self.movers_direction.addItems(["Top Gainers", "Top Losers"])
        self.movers_direction.currentIndexChanged.connect(self.show_movers)
        movers_header.addWidget(self.movers_direction)

        self.movers_exchange = QComboBox()
        self.movers_exchange.addItems(["All Exchanges", "NASDAQ", "NYSE", "Other"])
        self.movers_exchange.currentIndexChanged.connect(self.show_movers)
        movers_header.addWidget(self.movers_exchange)

        self.movers_volume = QComboBox()
        self.movers_volume.addItems(["Any Volume", "100K+ Volume", "1M+ Volume", "10M+ Volume"])
        self.movers_volume.currentIndexChanged.connect(self.show_movers)
        movers_header.addWidget(self.movers_volume)

        self.movers_refresh_button = QPushButton("Refresh Movers")
        self.movers_refresh_button.clicked.connect(lambda: self.refresh_movers(force=True))
        movers_header.addWidget(self.movers_refresh_button)
        layout.addLayout(movers_header)

        self.movers_status = QLabel("Loading market movers...")
        self.movers_status.setObjectName("Muted")
        layout.addWidget(self.movers_status)

        self.movers_table = QTableWidget(0, 5)
        self.movers_table.setHorizontalHeaderLabels(
            ["Ticker", "Company", "Price", "Change %", "Volume"]
        )
        self.movers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.movers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.movers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.movers_table.setFixedHeight(350)
        self.movers_table.cellDoubleClicked.connect(self.open_mover_stock)
        layout.addWidget(self.movers_table)

        self.movers_cache = []
        self.movers_cache_time = 0.0
        self.movers_worker = None

        # ==========================================
        # TOP MARKET STORIES
        # ==========================================

        news_heading = QHBoxLayout()

        news_title = QLabel("Top Market Stories")
        news_title.setObjectName("SectionTitle")

        news_heading.addWidget(news_title)
        news_heading.addStretch()

        self.news_refresh_button = QPushButton(
            "Refresh Stories"
        )
        self.news_refresh_button.clicked.connect(
            lambda: self.refresh_news(force=True)
        )

        news_heading.addWidget(
            self.news_refresh_button
        )

        layout.addLayout(news_heading)

        # ==========================================
        # NEWS CATEGORY TABS
        # ==========================================

        self.news_tabs = QTabBar()
        self.news_tabs.setExpanding(False)

        for category in CATEGORIES:
            self.news_tabs.addTab(category)

        self.news_tabs.currentChanged.connect(
            self.news_tab_changed
        )

        layout.addWidget(self.news_tabs)

        # ==========================================
        # NEWS STATUS
        # ==========================================

        self.news_status = QLabel(
            "Loading the latest news..."
        )
        self.news_status.setObjectName("Muted")
        layout.addWidget(self.news_status)

        # ==========================================
        # NEWS ARTICLE LIST
        # ==========================================

        self.news_list = QListWidget()

        self.news_list.setAlternatingRowColors(False)
        self.news_list.setSpacing(4)

        self.news_list.setStyleSheet("""
            QListWidget {
                background-color: #172235;
                border: 1px solid #293548;
                border-radius: 8px;
                padding: 6px;
            }

            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #293548;
            }

            QListWidget::item:hover {
                background-color: #243449;
            }

            QListWidget::item:selected {
                background-color: #1D4ED8;
            }
        """)

        self.news_list.itemDoubleClicked.connect(
            self.open_news_story
        )

        self.news_list.setMinimumHeight(400)
        self.news_list.setFixedHeight(440)
        layout.addWidget(self.news_list)
        layout.addStretch()

        # ==========================================
        # NEWS STATE
        # ==========================================

        self.news_cache = {}
        self.news_worker = None
        self.news_pending_category = None


        self.pages.addWidget(page)

        # Load initial news after GUI construction.
        QTimer.singleShot(0, self.refresh_news)
        QTimer.singleShot(0, self.refresh_movers)

    # ==============================================
    # MARKET INDEX FUNCTIONS
    # ==============================================

    def refresh_indices(self):
        if self.index_workers:
            return

        self.refresh_indices_button.setEnabled(False)
        self.indices_status.setText(
            "Updating market indices..."
        )

        for ticker, (value_label, change_label) in (
            self.dashboard_cards.items()
        ):
            value_label.setText("Loading...")
            change_label.setText("Fetching latest close")

            worker = IndexWorker(ticker)
            self.index_workers[ticker] = worker

            worker.signals.finished.connect(
                lambda data, w=worker:
                self.index_loaded(data, w)
            )

            worker.signals.error.connect(
                lambda error, t=ticker, w=worker:
                self.index_failed(t, error, w)
            )

            self.threadpool.start(worker)

    def index_loaded(self, data, worker):
        ticker = data["ticker"]

        value_label, change_label = (
            self.dashboard_cards[ticker]
        )

        value_label.setText(
            f'{data["level"]:,.2f}'
        )

        change_label.setText(
            f'{data["change"]:+,.2f} '
            f'({data["percent"]:+.2f}%)  ·  {data["date"]}'
        )

        color = (
            COLORS["green"]
            if data["change"] >= 0
            else COLORS["red"]
        )

        change_label.setStyleSheet(
            f"color: {color}; font-size: 11px;"
        )

        self.index_workers.pop(ticker, None)
        self.finish_index_refresh()

    def index_failed(self, ticker, error, worker):
        value_label, change_label = (
            self.dashboard_cards[ticker]
        )

        value_label.setText("Unavailable")
        change_label.setText(
            "Retry with Refresh Indices"
        )
        change_label.setToolTip(error)

        change_label.setStyleSheet(
            "color: #94A3B8; font-size: 11px;"
        )

        self.index_workers.pop(ticker, None)
        self.finish_index_refresh()

    def finish_index_refresh(self):
        if not self.index_workers:
            self.refresh_indices_button.setEnabled(True)

            self.indices_status.setText(
                "Latest available daily close · not live quotes"
            )

    # ==============================================
    # QUICK STOCK SEARCH
    # ==============================================

    def search_dashboard(self):
        ticker = (
            self.dashboard_search.text()
            .strip()
            .upper()
        )

        if ticker:
            self.load_stock(ticker)
            self.change_page(1)

    # ==============================================
    # NEWS CATEGORY SELECTION
    # ==============================================

    def news_tab_changed(self, index):
        if index >= 0:
            self.refresh_news()

    # ==============================================
    # NEWS RETRIEVAL
    # ==============================================

    def refresh_news(self, force=False):
        index = self.news_tabs.currentIndex()

        if index < 0:
            return

        category = self.news_tabs.tabText(index)

        watchlist = (
            tuple(self.db.get_watchlist())
            if category == "Your Watchlist"
            else ()
        )

        cache_key = (category, watchlist)

        # Use cached stories for up to 10 minutes
        # unless the user explicitly requests a refresh.
        cached = self.news_cache.get(cache_key)

        if (
            not force
            and cached is not None
            and time.monotonic() - cached[0] < 600
        ):
            self.show_news(
                cached[1],
                category
            )
            return

        # Keep only one active news worker.
        if self.news_worker is not None:
            self.news_pending_category = category

            self.news_status.setText(
                "Waiting for current news request..."
            )
            return

        self.news_list.clear()

        self.news_status.setText(
            f"Loading {category.lower()} stories..."
        )

        self.news_refresh_button.setEnabled(False)

        worker = NewsWorker(
            category,
            watchlist
        )

        self.news_worker = worker

        worker.signals.finished.connect(
            lambda articles, w=worker, key=cache_key:
            self.news_loaded(articles, w, key)
        )

        worker.signals.error.connect(
            lambda message, w=worker:
            self.news_failed(message, w)
        )

        self.threadpool.start(worker)

    # ==============================================
    # NEWS LOADED
    # ==============================================

    def news_loaded(
        self,
        articles,
        worker,
        cache_key
    ):
        self.news_cache[cache_key] = (
            time.monotonic(),
            articles
        )

        if self.news_worker is worker:
            self.news_worker = None

        self.news_refresh_button.setEnabled(True)

        current_category = self.news_tabs.tabText(
            self.news_tabs.currentIndex()
        )

        if current_category == worker.category:
            self.show_news(
                articles,
                worker.category
            )

        self.load_pending_news()

    # ==============================================
    # NEWS ERROR
    # ==============================================

    def news_failed(self, message, worker):
        if self.news_worker is worker:
            self.news_worker = None

        self.news_refresh_button.setEnabled(True)

        current_category = self.news_tabs.tabText(
            self.news_tabs.currentIndex()
        )

        if current_category == worker.category:
            self.news_status.setText(
                f"Could not load stories: {message}"
            )

        self.load_pending_news()

    # ==============================================
    # PENDING NEWS REQUEST
    # ==============================================

    def load_pending_news(self):
        pending = self.news_pending_category
        self.news_pending_category = None

        current_category = self.news_tabs.tabText(
            self.news_tabs.currentIndex()
        )

        if pending and pending == current_category:
            self.refresh_news()

    # ==============================================
    # DISPLAY NEWS ARTICLES
    # ==============================================

    def show_news(self, articles, category):
        self.news_list.clear()

        if not articles:
            if category == "Your Watchlist":
                message = (
                    "No watchlist stories found. "
                    "Add stocks to your watchlist and refresh."
                )
            else:
                message = (
                    "No stories available for this category. "
                    "Try refreshing."
                )

            self.news_status.setText(message)
            return

        for article in articles:
            url = article.get("url", "")
            item = QListWidgetItem()
            item.setData(Qt.UserRole, url)
            item.setToolTip("Double-click or select Read Article")

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(12)

            details = QVBoxLayout()
            details.setSpacing(5)

            headline = QLabel(str(article.get("title", "Untitled")))
            headline.setWordWrap(True)
            headline.setStyleSheet("font-weight: 600; font-size: 13px;")
            details.addWidget(headline)

            metadata = QLabel(
                f"{article.get('source', 'Unknown source')}  ·  "
                f"{article.get('published', 'Date unavailable')}"
            )
            metadata.setObjectName("Muted")
            metadata.setWordWrap(True)
            details.addWidget(metadata)
            row_layout.addLayout(details, 1)

            read_button = QPushButton("Read Article")
            read_button.setEnabled(bool(url))
            read_button.setCursor(Qt.PointingHandCursor)
            read_button.setMinimumWidth(110)
            read_button.clicked.connect(
                lambda checked=False, link=url: self.browser_launcher.open_url(link)
            )
            row_layout.addWidget(read_button, 0, Qt.AlignVCenter)

            self.news_list.addItem(item)
            item.setSizeHint(row.sizeHint())
            self.news_list.setItemWidget(item, row)

        self.news_status.setText(
            f"{len(articles)} {category.lower()} stories · "
            "Read Article to open source · feeds may be delayed"
        )

    # ==============================================
    # OPEN NEWS ARTICLE FROM DASHBOARD
    # ==============================================

    def open_news_story(self, item):
        self.browser_launcher.open_url(item.data(Qt.UserRole))

    # ==============================================
    # MARKET MOVERS
    # ==============================================

    def refresh_movers(self, force=False):
        # Filtering always uses cached data; refresh only downloads when needed.
        if self.movers_worker is not None:
            return
        if not force and self.movers_cache and time.monotonic() - self.movers_cache_time < 300:
            self.show_movers()
            return

        self.movers_status.setText("Fetching Yahoo Finance movers in background...")
        self.movers_refresh_button.setEnabled(False)
        worker = MoversWorker()
        self.movers_worker = worker
        worker.signals.finished.connect(lambda data, w=worker: self.movers_loaded(data, w))
        worker.signals.error.connect(lambda error, w=worker: self.movers_failed(error, w))
        self.threadpool.start(worker)

    def movers_loaded(self, data, worker):
        if worker is not self.movers_worker:
            return
        self.movers_worker = None
        self.movers_refresh_button.setEnabled(True)
        self.movers_cache = data
        self.movers_cache_time = time.monotonic()
        self.movers_updated_at = datetime.now().strftime("%H:%M")
        self.show_movers()

    def movers_failed(self, error, worker):
        if worker is not self.movers_worker:
            return
        self.movers_worker = None
        self.movers_refresh_button.setEnabled(True)
        self.movers_status.setText(f"Movers unavailable: {error}")

    def show_movers(self, *_):
        direction = "Gainers" if self.movers_direction.currentIndex() == 0 else "Losers"
        exchange_filter = self.movers_exchange.currentText()
        volume_filter = self.movers_volume.currentIndex()
        min_volume = (0, 100_000, 1_000_000, 10_000_000)[volume_filter]
        exchange_codes = {
            "NASDAQ": {"NMS", "NGM", "NCM", "NAS", "NASDAQ"},
            "NYSE": {"NYQ", "NYSE"},
        }

        filtered = []
        for stock in self.movers_cache:
            if stock["direction"] != direction:
                continue
            if (stock["volume"] or 0) < min_volume:
                continue
            exchange = stock["exchange"].upper()
            if exchange_filter in exchange_codes and exchange not in exchange_codes[exchange_filter]:
                continue
            if exchange_filter == "Other" and exchange in (exchange_codes["NASDAQ"] | exchange_codes["NYSE"]):
                continue
            filtered.append(stock)

        filtered.sort(key=lambda stock: stock["change"], reverse=(direction == "Gainers"))
        self.movers_table.setSortingEnabled(False)
        self.movers_table.setRowCount(len(filtered))
        for row, stock in enumerate(filtered):
            price = f'${stock["price"]:,.2f}' if stock["price"] is not None else "--"
            volume = f'{stock["volume"]:,.0f}' if stock["volume"] is not None else "--"
            values = [stock["symbol"], stock["name"], price, f'{stock["change"]:+.2f}%', volume]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.movers_table.setItem(row, column, item)
        self.movers_table.setSortingEnabled(False)
        updated = getattr(self, "movers_updated_at", "--")
        self.movers_status.setText(
            f"{len(filtered)} {direction.lower()} shown · Yahoo Finance US screener · "
            f"updated {updated} · quotes may be delayed · double-click a ticker to explore"
        )

    def open_mover_stock(self, row, column):
        item = self.movers_table.item(row, 0)
        if item is None:
            return
        self.load_stock(item.text())
        self.change_page(1)
