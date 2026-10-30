import math
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from datetime import datetime, timezone, time as clock_time
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

import pandas as pd
import yfinance as yf

from PySide6.QtCore import (
    Qt,
    QTimer,
    QObject,
    QRunnable,
    Signal
)


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QScrollArea,
    QFrame,
    QTabWidget,
    QGridLayout,
    QSizePolicy
)

from config import COLORS
from core.market import MarketWorker, QuoteWorker
from gui.dashboard import create_card
from gui.charts import StockChart


# ============================================================
# DATA VALIDATION HELPERS
# ============================================================

def valid_number(value, positive=False):
    """
    Convert a value to a finite float.

    Returns None for:
    - None
    - NaN
    - Infinity
    - Non-numeric values

    If positive=True, zero and negative values are rejected.
    """

    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        if positive and number <= 0:
            return None

        return number

    except (TypeError, ValueError, OverflowError):
        return None


def clean_price_history(history):
    """
    Return historical data with valid OHLC prices.

    Invalid price rows are removed.

    Invalid volume values are replaced with zero so
    the chart can still render available price data.
    """

    if history is None or history.empty:
        return pd.DataFrame()

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close"
    ]

    if not all(
        column in history.columns
        for column in required_columns
    ):
        return pd.DataFrame()

    cleaned = history.copy()

    cleaned = cleaned.sort_index()

    for column in required_columns:
        cleaned[column] = pd.to_numeric(
            cleaned[column],
            errors="coerce"
        )

    cleaned[required_columns] = (
        cleaned[required_columns].replace(
            [float("inf"), float("-inf")],
            float("nan")
        )
    )

    cleaned = cleaned.dropna(
        subset=required_columns
    )

    for column in required_columns:
        cleaned = cleaned[
            cleaned[column] > 0
        ]

    # Ensure each candle has a consistent OHLC range.
    cleaned = cleaned[
        (cleaned["High"] >= cleaned["Low"])
        & (cleaned["High"] >= cleaned["Open"])
        & (cleaned["High"] >= cleaned["Close"])
        & (cleaned["Low"] <= cleaned["Open"])
        & (cleaned["Low"] <= cleaned["Close"])
    ]

    if "Volume" not in cleaned.columns:
        cleaned["Volume"] = 0

    cleaned["Volume"] = pd.to_numeric(
        cleaned["Volume"],
        errors="coerce"
    )

    cleaned["Volume"] = (
        cleaned["Volume"]
        .replace(
            [float("inf"), float("-inf")],
            float("nan")
        )
        .fillna(0)
        .clip(lower=0)
    )

    return cleaned


def calculate_price_change(history):
    """
    Calculate percentage change using the last
    two valid closing prices.
    """

    if history is None or len(history) < 2:
        return None

    latest = valid_number(
        history["Close"].iloc[-1],
        positive=True
    )

    previous = valid_number(
        history["Close"].iloc[-2],
        positive=True
    )

    if latest is None or previous is None:
        return None

    return (
        (latest - previous)
        / previous
        * 100
    )


def format_market_cap(value):

    number = valid_number(value)

    if number is None:
        return "--"

    if abs(number) >= 1_000_000_000_000:
        return f"{number / 1_000_000_000_000:,.2f}T"

    if abs(number) >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.2f}B"

    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.2f}M"

    return f"{number:,.0f}"


# ============================================================
# NEWS HELPERS
# ============================================================

def parse_news_article(item):

    if not isinstance(item, dict):
        return None

    content = item.get("content") or item

    if not isinstance(content, dict):
        return None

    title = (
        content.get("title")
        or item.get("title")
    )

    provider = content.get("provider") or {}

    if isinstance(provider, dict):
        publisher = provider.get(
            "displayName",
            "Unknown"
        )
    else:
        publisher = str(provider)

    if publisher == "Unknown":
        publisher = item.get(
            "publisher",
            "Unknown"
        )

    url = ""

    for key in (
        "canonicalUrl",
        "clickThroughUrl"
    ):

        value = content.get(key)

        if isinstance(value, dict):
            url = value.get("url", "")

        elif isinstance(value, str):
            url = value

        if url:
            break

    if not url:
        url = (
            content.get("link")
            or item.get("link")
            or ""
        )

    published = content.get("pubDate")

    if not published:

        timestamp = item.get(
            "providerPublishTime"
        )

        if timestamp:

            try:
                published = datetime.fromtimestamp(
                    timestamp,
                    timezone.utc
                ).isoformat()

            except (
                TypeError,
                ValueError,
                OverflowError
            ):
                published = None

    if not title or not url:
        return None

    if not isinstance(url, str):
        return None

    if not url.startswith(
        ("https://", "http://")
    ):
        return None

    return {
        "title": str(title),
        "publisher": str(publisher),
        "published": published,
        "url": url
    }


def fetch_google_news(ticker, company_name=""):

    query = company_name or ticker

    query = f'"{query}" stock'

    params = urllib.parse.urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    })

    url = (
        "https://news.google.com/rss/search?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=12
    ) as response:

        data = response.read()

    root = ET.fromstring(data)

    articles = []

    for item in root.findall("./channel/item"):

        title = item.findtext(
            "title",
            ""
        )

        link = item.findtext(
            "link",
            ""
        )

        published = item.findtext(
            "pubDate",
            ""
        )

        source = item.find("source")

        publisher = (
            source.text
            if source is not None and source.text
            else "Google News"
        )

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "publisher": publisher,
            "published": published,
            "url": link
        })

        if len(articles) >= 10:
            break

    return articles


def format_news_date(value):

    if not value:
        return "Date unavailable"

    try:

        if isinstance(value, (int, float)):

            date = datetime.fromtimestamp(
                value,
                timezone.utc
            )

        elif "," in str(value):

            date = parsedate_to_datetime(
                str(value)
            )

        else:

            date = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00"
                )
            )

        return date.strftime(
            "%b %d, %Y"
        )

    except (
        ValueError,
        TypeError,
        OverflowError
    ):
        return str(value)


# ============================================================
# NEWS WORKER SIGNALS
# ============================================================

class NewsSignals(QObject):

    finished = Signal(
        str,
        object,
        str,
        int
    )

    error = Signal(
        str,
        str,
        int
    )


# ============================================================
# NEWS WORKER
# ============================================================

class NewsWorker(QRunnable):

    def __init__(
        self,
        ticker,
        company_name="",
        request_id=0
    ):

        super().__init__()

        self.setAutoDelete(False)

        self.ticker = ticker
        self.company_name = company_name
        self.request_id = request_id

        self.signals = NewsSignals()

    def run(self):

        errors = []

        # ----------------------------------------------------
        # SOURCE 1: YAHOO FINANCE
        # ----------------------------------------------------

        try:

            search = yf.Search(
                self.ticker,
                news_count=20
            )

            raw_news = search.news or []

            articles = []
            seen = set()

            for item in raw_news:

                article = parse_news_article(
                    item
                )

                if article is None:
                    continue

                url = article["url"]

                if url in seen:
                    continue

                seen.add(url)

                articles.append(
                    article
                )

                if len(articles) >= 10:
                    break

            if articles:

                self.signals.finished.emit(
                    self.ticker,
                    articles,
                    "Yahoo Finance",
                    self.request_id
                )

                return

            errors.append(
                "Yahoo Finance returned no articles"
            )

        except Exception as error:

            errors.append(
                f"Yahoo Finance: {error}"
            )

        # ----------------------------------------------------
        # SOURCE 2: GOOGLE NEWS
        # ----------------------------------------------------

        try:

            articles = fetch_google_news(
                self.ticker,
                self.company_name
            )

            if articles:

                self.signals.finished.emit(
                    self.ticker,
                    articles,
                    "Google News",
                    self.request_id
                )

                return

            errors.append(
                "Google News returned no articles"
            )

        except Exception as error:

            errors.append(
                f"Google News: {error}"
            )

        # ----------------------------------------------------
        # ALL SOURCES FAILED
        # ----------------------------------------------------

        self.signals.error.emit(
            self.ticker,
            " | ".join(errors),
            self.request_id
        )


# ============================================================
# STOCK EXPLORER
# ============================================================

class ExplorerMixin:

    # ========================================================
    # BUILD EXPLORER
    # ========================================================

    def build_explorer(self):
        """Finance-style explorer, preserving all original integration points."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("ExplorerContent")
        container.setStyleSheet("""
            QWidget#ExplorerContent { background: #0e1726; }
            QFrame#ExplorerPanel {
                background: #142033;
                border: 1px solid #283b54;
                border-radius: 12px;
            }
            QLabel#ExplorerEyebrow { color: #8fa3bd; font-size: 11px; }
            QLabel#ExplorerBigPrice { color: #f2f7ff; font-size: 33px; font-weight: 800; }
            QLabel#ExplorerStatValue { color: #edf4ff; font-size: 15px; font-weight: 700; }
            QLabel#ExplorerCompany { color: #f4f7ff; font-size: 24px; font-weight: 750; }
            QPushButton#ExplorerPeriod {
                color: #b9cbe2; background: #1b2a40;
                border: 1px solid #30445e; border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton#ExplorerPeriod:checked {
                background: #2563eb; color: white; border-color: #3b82f6;
            }
            QPushButton#ExplorerPeriod:hover { border-color: #4c91ff; }
        """)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(25, 22, 25, 25)
        layout.setSpacing(18)

        # Search bar and title.
        header = QHBoxLayout()
        title = QLabel("Stock Explorer")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Search ticker (AAPL, NVDA, TD.TO)...")
        self.ticker_input.setMinimumWidth(210)
        self.ticker_input.setMaximumWidth(360)
        self.ticker_input.returnPressed.connect(self.search_explorer)
        header.addWidget(self.ticker_input)
        search_button = QPushButton("Search")
        search_button.setObjectName("Primary")
        search_button.clicked.connect(self.search_explorer)
        header.addWidget(search_button)
        layout.addLayout(header)

        # Company identity and price summary.
        identity = QHBoxLayout()
        identity.setSpacing(20)
        name_col = QVBoxLayout()
        self.company_label = QLabel("Search for a stock to begin exploring.")
        self.company_label.setObjectName("ExplorerCompany")
        self.company_label.setWordWrap(True)
        name_col.addWidget(self.company_label)
        self.explorer_company_meta = QLabel("Company overview  •  Market research")
        self.explorer_company_meta.setObjectName("ExplorerEyebrow")
        self.explorer_company_meta.setWordWrap(True)
        name_col.addWidget(self.explorer_company_meta)
        identity.addLayout(name_col, 3)
        identity.addStretch(1)
        self.watchlist_button = QPushButton("☆ Add to Watchlist")
        self.watchlist_button.clicked.connect(self.add_current_to_watchlist)
        self.watchlist_button.setEnabled(False)
        identity.addWidget(self.watchlist_button, 0, Qt.AlignTop)
        layout.addLayout(identity)

        quote_row = QHBoxLayout()
        quote_col = QVBoxLayout()
        quote_col.setSpacing(2)
        self.price_value = QLabel("--")
        self.price_value.setObjectName("ExplorerBigPrice")
        self.price_change = QLabel("--")
        self.price_change.setStyleSheet("color: #94a3b8; font-size: 16px; font-weight: 700;")
        quote_col.addWidget(self.price_value)
        quote_col.addWidget(self.price_change)
        quote_row.addLayout(quote_col)
        quote_row.addStretch()
        self.explorer_price_note = QLabel("Latest available close · quotes may be delayed")
        self.explorer_price_note.setObjectName("ExplorerEyebrow")
        quote_row.addWidget(self.explorer_price_note, 0, Qt.AlignBottom)
        layout.addLayout(quote_row)

        # Main chart with finance-style time controls.
        chart_and_stats = QHBoxLayout()
        chart_and_stats.setSpacing(16)
        chart_col = QVBoxLayout()
        chart_col.setSpacing(10)
        period_row = QHBoxLayout()
        period_row.setSpacing(5)
        period_row.addWidget(QLabel("Period:"))
        self.period_combo = QComboBox()
        periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
        self.period_combo.addItems(periods)
        self.period_combo.setCurrentText("1y")
        self.period_combo.currentTextChanged.connect(self.period_changed)
        period_row.addWidget(self.period_combo)
        period_row.addStretch()
        period_row.addWidget(QLabel("Chart:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Candlestick", "Line"])
        self.chart_type_combo.currentTextChanged.connect(self._set_explorer_chart_type)
        period_row.addWidget(self.chart_type_combo)
        chart_col.addLayout(period_row)
        chart_panel = QFrame()
        chart_panel.setObjectName("ExplorerPanel")
        chart_panel_layout = QVBoxLayout(chart_panel)
        chart_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.chart = StockChart()
        self.chart.setMinimumHeight(390)
        chart_panel_layout.addWidget(self.chart)
        chart_col.addWidget(chart_panel)
        chart_and_stats.addLayout(chart_col, 7)

        stats_panel = QFrame()
        stats_panel.setObjectName("ExplorerPanel")
        stats_panel.setMinimumWidth(280)
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(17, 17, 17, 17)
        stats_layout.setSpacing(14)
        stats_heading = QLabel("Key Statistics")
        stats_heading.setStyleSheet("color: #f3f7ff; font-size: 17px; font-weight: 700;")
        stats_layout.addWidget(stats_heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(17)
        self.explorer_stats = {}
        stats = [
            ("Market Cap", "marketcap"), ("P/E Ratio", "pe"),
            ("Volume", "volume"), ("Avg. Volume", "avg_volume"),
            ("Previous Close", "previous_close"), ("52W High", "fifty_two_high"),
            ("52W Low", "fifty_two_low"), ("EPS (TTM)", "eps"),
            ("Dividend Yield", "dividend_yield"), ("Beta", "beta"),
            ("Revenue", "revenue"), ("Profit Margin", "profit_margin"),
        ]
        for i, (label_text, key) in enumerate(stats):
            cell = QVBoxLayout()
            cell.setSpacing(3)
            caption = QLabel(label_text)
            caption.setObjectName("ExplorerEyebrow")
            value = QLabel("--")
            value.setObjectName("ExplorerStatValue")
            cell.addWidget(caption)
            cell.addWidget(value)
            grid.addLayout(cell, i // 2, i % 2)
            self.explorer_stats[key] = value
        stats_layout.addLayout(grid)
        stats_layout.addStretch(1)
        chart_and_stats.addWidget(stats_panel, 4)
        layout.addLayout(chart_and_stats)

        # Compatibility with existing data-update methods.
        self.price_card = chart_panel
        self.marketcap_card = stats_panel
        self.marketcap_value = self.explorer_stats["marketcap"]
        self.pe_card = stats_panel
        self.pe_value = self.explorer_stats["pe"]
        self.volume_card = stats_panel
        self.volume_value = self.explorer_stats["volume"]

        lower = QHBoxLayout()
        lower.setSpacing(16)
        about_panel = QFrame()
        about_panel.setObjectName("ExplorerPanel")
        about_layout = QVBoxLayout(about_panel)
        about_layout.setContentsMargins(18, 16, 18, 16)
        about_title = QLabel("About the Company")
        about_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #f3f7ff;")
        about_layout.addWidget(about_title)
        self.explorer_description = QLabel("Search for a ticker to see the company profile.")
        self.explorer_description.setWordWrap(True)
        self.explorer_description.setStyleSheet("color: #bdcbe0; line-height: 1.4;")
        about_layout.addWidget(self.explorer_description)
        self.explorer_profile_meta = QLabel("")
        self.explorer_profile_meta.setWordWrap(True)
        self.explorer_profile_meta.setObjectName("ExplorerEyebrow")
        about_layout.addWidget(self.explorer_profile_meta)
        about_layout.addStretch()
        lower.addWidget(about_panel)
        layout.addLayout(lower)

        # Original company-news flow and browser integration retained.
        news_header = QHBoxLayout()
        news_title = QLabel("Latest Company News")
        news_title.setObjectName("SectionTitle")
        news_header.addWidget(news_title)
        news_header.addStretch()
        self.news_refresh_button = QPushButton("Refresh News")
        self.news_refresh_button.clicked.connect(self.refresh_company_news)
        self.news_refresh_button.setEnabled(False)
        news_header.addWidget(self.news_refresh_button)
        layout.addLayout(news_header)
        self.news_status = QLabel("Search for a company to view recent news.")
        self.news_status.setWordWrap(True)
        self.news_status.setObjectName("ExplorerEyebrow")
        layout.addWidget(self.news_status)
        self.news_container = QWidget()
        self.news_layout = QVBoxLayout(self.news_container)
        self.news_layout.setContentsMargins(0, 0, 0, 0)
        self.news_layout.setSpacing(10)
        layout.addWidget(self.news_container)
        layout.addStretch()
        scroll.setWidget(container)

        self.explorer_tabs = QTabWidget()
        self.explorer_tabs.setDocumentMode(True)
        self.explorer_tabs.addTab(scroll, "Overview")
        # window.py attaches the original Technical and Fundamental pages.
        self.explorer_tabs.currentChanged.connect(self.explorer_analysis_tab_changed)
        outer.addWidget(self.explorer_tabs)
        self.pages.addWidget(page)

        self.news_workers = set()
        self.news_current_ticker = None
        self.news_company_name = ""
        self.news_request_id = 0
        self.explorer_request_id = 0
        self.explorer_requested_ticker = None
        self.explorer_requested_period = None
        self.explorer_quote_worker = None
        self.explorer_quote_ticker = None
        self.explorer_quote_currency = "USD"
        self.explorer_quote_timer = QTimer(page)
        self.explorer_quote_timer.setInterval(30_000)
        self.explorer_quote_timer.timeout.connect(self.refresh_explorer_quote)
        self.explorer_quote_timer.start()

    def _set_explorer_chart_type(self, chart_type):
        self.chart.set_chart_type(chart_type)

    def _explorer_market_open(self):
        """Approximate North American regular session; holidays are not checked."""
        now = datetime.now(ZoneInfo("America/New_York"))
        return (now.weekday() < 5 and
                clock_time(9, 30) <= now.time() < clock_time(16, 0))

    def refresh_explorer_quote(self):
        ticker = self.explorer_requested_ticker
        if not ticker:
            return

        if self.explorer_quote_worker is not None:
            return

        worker = QuoteWorker(ticker)
        self.explorer_quote_worker = worker
        self.explorer_quote_ticker = ticker

        worker.signals.finished.connect(
            lambda data, w=worker: self._explorer_quote_loaded(data, w)
        )
        worker.signals.error.connect(
            lambda error, w=worker: self._explorer_quote_error(error, w)
        )
        self.threadpool.start(worker)

    def _explorer_quote_loaded(self, data, worker):
        if self.explorer_quote_worker is worker:
            self.explorer_quote_worker = None
        if data["ticker"] != self.explorer_requested_ticker:
            return
        price = data["price"]
        previous = data["previous_close"]
        self.price_value.setText(f"{price:,.2f} {self.explorer_quote_currency}")
        if previous and previous > 0:
            delta = price - previous
            pct = delta / previous * 100
            self.price_change.setText(f"{delta:+,.2f} ({pct:+.2f}%)")
            self.price_change.setStyleSheet(
                f'color: {COLORS["green"] if delta >= 0 else COLORS["red"]};'
            )
        stamp = data["bar_time"].astimezone().strftime("%H:%M:%S")
        self.explorer_price_note.setText(
            f"Auto-updating every 30s · latest provider bar {stamp} · may be delayed")

    def _explorer_quote_error(self, error, worker):
        if self.explorer_quote_worker is worker:
            self.explorer_quote_worker = None
        if self.explorer_quote_ticker == self.explorer_requested_ticker:
            self.explorer_price_note.setText(f"Quote update unavailable · {error}")

    def _update_explorer_profile(self, info):
        """Populate optional finance-style details from existing market info."""
        info = info or {}
        sector = info.get("sector") or "Sector unavailable"
        industry = info.get("industry") or "Industry unavailable"
        exchange = info.get("exchange") or ""
        self.explorer_company_meta.setText("  •  ".join(x for x in (sector, industry, exchange) if x))
        description = info.get("longBusinessSummary") or "No company description available."
        self.explorer_description.setText(str(description))
        location = ", ".join(str(x) for x in (info.get("city"), info.get("country")) if x)
        website = info.get("website") or ""
        employees = info.get("fullTimeEmployees")
        parts = []
        if location:
            parts.append("Headquarters: " + location)
        if employees is not None:
            try:
                parts.append("Employees: " + f"{int(employees):,}")
            except (TypeError, ValueError):
                pass
        if website:
            parts.append("Website: " + str(website))
        self.explorer_profile_meta.setText("   |   ".join(parts))

        def number(key, fmt=",.2f"):
            value = valid_number(info.get(key))
            return format(value, fmt) if value is not None else "--"

        def percent(key):
            value = valid_number(info.get(key))
            return f"{value * 100:.2f}%" if value is not None else "--"

        self.explorer_stats["avg_volume"].setText(number("averageVolume", ",.0f"))
        self.explorer_stats["previous_close"].setText(number("previousClose"))
        self.explorer_stats["fifty_two_high"].setText(number("fiftyTwoWeekHigh"))
        self.explorer_stats["fifty_two_low"].setText(number("fiftyTwoWeekLow"))
        self.explorer_stats["eps"].setText(number("trailingEps"))
        dividend_yield = valid_number(info.get("dividendYield"))

        if dividend_yield is not None:
            self.explorer_stats["dividend_yield"].setText(
                f"{dividend_yield:.2f}%"
            )
        else:
            self.explorer_stats["dividend_yield"].setText("--")
        self.explorer_stats["beta"].setText(number("beta"))
        self.explorer_stats["revenue"].setText(format_market_cap(info.get("totalRevenue")))
        self.explorer_stats["profit_margin"].setText(percent("profitMargins"))

    def explorer_analysis_tab_changed(self, index):
        """Load the selected stock only when an analysis tab opens."""
        ticker = self.explorer_requested_ticker
        if not ticker:
            return
        if index == 1 and self.technical_requested_ticker != ticker:
            self.load_technical(ticker)
        elif index == 2 and self.fund_requested_ticker != ticker:
            self.load_fundamentals(ticker)

    # ========================================================
    # SEARCH
    # ========================================================

    def search_explorer(self):

        ticker = (
            self.ticker_input.text()
            .strip()
            .upper()
        )

        if not ticker:
            return

        self.load_stock(
            ticker
        )

    # ========================================================
    # PERIOD CHANGE
    # ========================================================

    def period_changed(self, period):

        self.current_period = period

        # Reload the stock currently displayed in Explorer,
        # not an unrelated ticker selected on another page.

        ticker = self.explorer_requested_ticker

        if ticker:

            self.load_stock(
                ticker
            )

    # ========================================================
    # LOAD STOCK
    # ========================================================

    def load_stock(self, ticker):

        ticker = str(ticker).strip().upper()

        if not ticker:
            return

        previous_ticker = (
            self.news_current_ticker
        )

        # Update the application's active ticker.
        self.current_ticker = ticker

        # Preserve the previous ticker's notes and load this ticker's notes.
        if hasattr(self, "research_notes"):
            self.research_notes.set_ticker(ticker)

        # Track Explorer's own ticker separately.
        self.explorer_requested_ticker = ticker

        self.explorer_requested_period = (
            self.current_period
        )

        # Identify this request so older responses
        # cannot overwrite newer results.
        self.explorer_request_id += 1

        request_id = (
            self.explorer_request_id
        )

        self.ticker_input.setText(
            ticker
        )

        self.company_label.setText(
            f"Loading {ticker}..."
        )
        self.explorer_company_meta.setText("Loading company details...")
        self.explorer_description.setText("Loading company profile...")
        self.explorer_profile_meta.setText("")
        for value in self.explorer_stats.values():
            value.setText("--")

        # Clear previous metrics while loading.
        self.price_value.setText("--")
        self.price_change.setText("--")
        self.marketcap_value.setText("--")
        self.pe_value.setText("--")
        self.volume_value.setText("--")

        self.watchlist_button.setEnabled(
            False
        )

        self.statusBar().showMessage(
            f"Downloading market data for {ticker}..."
        )

        worker = MarketWorker(
            ticker,
            self.current_period
        )

        self.active_workers.add(
            worker
        )

        worker.signals.finished.connect(
            lambda data, w=worker, rid=request_id:
            self.stock_loaded(
                data,
                w,
                rid
            )
        )

        worker.signals.error.connect(
            lambda error, w=worker, rid=request_id:
            self.stock_error(
                error,
                w,
                rid
            )
        )

        self.threadpool.start(
            worker
        )

        # ----------------------------------------------------
        # LOAD NEWS WHEN TICKER CHANGES
        # ----------------------------------------------------

        if previous_ticker != ticker:

            self.news_current_ticker = ticker

            self.news_company_name = ""

            self.load_company_news(
                ticker
            )

    # ========================================================
    # STOCK LOADED
    # ========================================================

    def stock_loaded(
        self,
        data,
        worker,
        request_id=None
    ):

        self.active_workers.discard(
            worker
        )

        # ----------------------------------------------------
        # IGNORE OUTDATED RESPONSES
        # ----------------------------------------------------

        if (
            request_id is not None
            and request_id != self.explorer_request_id
        ):
            return

        ticker = data.get(
            "ticker",
            ""
        )

        history = data.get(
            "history"
        )

        info = data.get(
            "info"
        ) or {}

        period = data.get(
            "period",
            self.current_period
        )

        if (
            ticker != self.explorer_requested_ticker
            or period != self.explorer_requested_period
        ):
            return

        # ----------------------------------------------------
        # COMPANY INFORMATION
        # ----------------------------------------------------

        name = (
            info.get("longName")
            or info.get("shortName")
            or ticker
        )

        self.news_company_name = name
        self.explorer_quote_currency = info.get("currency") or "USD"
        self.explorer_price_note.setText(
            "Auto-updating every 30s during US/Canada regular hours · quotes may be delayed"
        )

        self.company_label.setText(
            f"{name} ({ticker})"
        )

        self._update_explorer_profile(info)

        # ----------------------------------------------------
        # VALIDATE HISTORICAL DATA
        # ----------------------------------------------------

        clean_history = clean_price_history(
            history
        )

        if clean_history.empty:

            self.price_value.setText(
                "Price unavailable"
            )

            self.price_change.setText("--")
            self.marketcap_value.setText("--")
            self.pe_value.setText("--")
            self.volume_value.setText("--")

            self.statusBar().showMessage(
                f"No valid price history for {ticker}"
            )

            return

        # ----------------------------------------------------
        # LATEST VALID CLOSING PRICE
        # ----------------------------------------------------

        latest = valid_number(
            clean_history["Close"].iloc[-1],
            positive=True
        )

        currency = (
            info.get("currency")
            or "USD"
        )
    # Historical prices are for the chart, not the live quote.
# Wait for QuoteWorker before displaying a market price.
        self.price_value.setText("Loading latest quote...")
        self.price_change.setText("--")

        self.explorer_price_note.setText(
            "Retrieving latest available market price..."
        )
        # ----------------------------------------------------
        # PRICE CHANGE
        # ----------------------------------------------------

        change = calculate_price_change(
            clean_history
        )
        self.update_watchlist_button()

        self.statusBar().showMessage(
            f"{ticker} loaded successfully"
        )

        self.refresh_explorer_quote()
        # ----------------------------------------------------
        # MARKET CAPITALIZATION
        # ----------------------------------------------------

        marketcap = info.get(
            "marketCap"
        )

        self.marketcap_value.setText(
            format_market_cap(
                marketcap
            )
        )

        # ----------------------------------------------------
        # P/E RATIO
        # ----------------------------------------------------

        pe = valid_number(
            info.get("trailingPE")
        )

        if pe is not None:

            self.pe_value.setText(
                f"{pe:.2f}"
            )

        else:

            self.pe_value.setText(
                "--"
            )

        # ----------------------------------------------------
        # TRADING VOLUME
        # ----------------------------------------------------

        volume = valid_number(
            clean_history["Volume"].iloc[-1]
        )

        if volume is not None:

            self.volume_value.setText(
                f"{int(volume):,}"
            )

        else:

            self.volume_value.setText(
                "--"
            )

        # ----------------------------------------------------
        # SAVE DATA
        # ----------------------------------------------------

        try:

            self.db.save_stock(
                ticker,
                info
            )

            if period not in (
                "1d",
                "5d"
            ):

                self.db.save_history(
                    ticker,
                    clean_history
                )

        except Exception as error:

            print(
                f"[Explorer] Database save error: {error}"
            )

        # ----------------------------------------------------
        # UPDATE CHART
        # ----------------------------------------------------

        self.update_chart(
            ticker,
            clean_history
        )

        # ----------------------------------------------------
        # UPDATE WATCHLIST BUTTON
        # ----------------------------------------------------

        self.update_watchlist_button()

        self.statusBar().showMessage(
            f"{ticker} loaded successfully"
        )

# Immediately request the latest available market quote.
        self.refresh_explorer_quote()

    # ========================================================
    # STOCK ERROR
    # ========================================================

    def stock_error(
        self,
        error,
        worker,
        request_id=None
    ):

        self.active_workers.discard(
            worker
        )

        # Ignore errors from requests that are no
        # longer the currently selected search.
        if (
            request_id is not None
            and request_id != self.explorer_request_id
        ):
            return

        self.company_label.setText(
            "Unable to retrieve stock data"
        )
        self.explorer_company_meta.setText("Data unavailable")
        self.explorer_description.setText("Please try another ticker or retry the search.")

        self.price_value.setText("--")
        self.price_change.setText("--")
        self.marketcap_value.setText("--")
        self.pe_value.setText("--")
        self.volume_value.setText("--")

        self.statusBar().showMessage(
            str(error)
        )

        QMessageBox.warning(
            self,
            "Market Data Error",
            str(error)
        )

    # ========================================================
    # UPDATE CHART
    # ========================================================

    def update_chart(
        self,
        ticker,
        history
    ):

        self.chart.set_data(
            ticker,
            history
        )

    # ========================================================
    # FETCH COMPANY NEWS
    # ========================================================

    def load_company_news(
        self,
        ticker
    ):

        if not ticker:
            return

        self.news_request_id += 1

        request_id = (
            self.news_request_id
        )

        self.clear_news()

        self.news_status.setText(
            f"Searching recent news for {ticker}..."
        )

        self.news_refresh_button.setEnabled(
            False
        )

        worker = NewsWorker(
            ticker,
            self.news_company_name,
            request_id
        )

        self.news_workers.add(
            worker
        )

        worker.signals.finished.connect(
            lambda symbol, articles, source, rid, w=worker:
            self.company_news_loaded(
                symbol,
                articles,
                source,
                w,
                rid
            )
        )

        worker.signals.error.connect(
            lambda symbol, error, rid, w=worker:
            self.company_news_error(
                symbol,
                error,
                w,
                rid
            )
        )

        self.threadpool.start(
            worker
        )

    # ========================================================
    # REFRESH COMPANY NEWS
    # ========================================================

    def refresh_company_news(self):

        ticker = (
            self.explorer_requested_ticker
        )

        if ticker:

            self.load_company_news(
                ticker
            )

    # ========================================================
    # NEWS LOADED
    # ========================================================

    def company_news_loaded(
        self,
        ticker,
        articles,
        source,
        worker,
        request_id=None
    ):

        self.news_workers.discard(
            worker
        )

        if ticker != self.explorer_requested_ticker:
            return

        if (
            request_id is not None
            and request_id != self.news_request_id
        ):
            return

        self.news_refresh_button.setEnabled(
            True
        )

        self.clear_news()

        self.news_status.setText(
            f"{len(articles)} articles for {ticker} "
            f"— Source: {source}"
        )

        for article in articles:

            self.add_news_card(
                article
            )

    # ========================================================
    # NEWS ERROR
    # ========================================================

    def company_news_error(
        self,
        ticker,
        error,
        worker,
        request_id=None
    ):

        self.news_workers.discard(
            worker
        )

        if ticker != self.explorer_requested_ticker:
            return

        if (
            request_id is not None
            and request_id != self.news_request_id
        ):
            return

        self.news_refresh_button.setEnabled(
            True
        )

        self.news_status.setText(
            "News services are currently unavailable. "
            f"Details: {error}"
        )

    # ========================================================
    # CLEAR NEWS CARDS
    # ========================================================

    def clear_news(self):

        while self.news_layout.count():

            item = (
                self.news_layout.takeAt(0)
            )

            widget = (
                item.widget()
            )

            if widget is not None:

                widget.deleteLater()

    # ========================================================
    # ADD NEWS CARD
    # ========================================================

    def add_news_card(
        self,
        article
    ):

        card = QFrame()

        card.setObjectName(
            "CompanyNewsCard"
        )

        card.setStyleSheet("""
            QFrame#CompanyNewsCard {
                background: #182235;
                border: 1px solid #2a3951;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(
            card
        )

        layout.setContentsMargins(
            16, 14, 16, 14
        )

        layout.setSpacing(
            10
        )

        # ----------------------------------------------------
        # HEADLINE
        # ----------------------------------------------------

        title = QLabel(
            article["title"]
        )

        title.setWordWrap(
            True
        )

        title.setStyleSheet("""
            color: #e7edf7;
            font-size: 14px;
            font-weight: bold;
            border: none;
        """)

        layout.addWidget(
            title
        )

        # ----------------------------------------------------
        # PUBLISHER AND DATE
        # ----------------------------------------------------

        publisher = article.get(
            "publisher",
            "Unknown"
        )

        date = format_news_date(
            article.get("published")
        )

        metadata = QLabel(
            f"{publisher}  •  {date}"
        )

        metadata.setStyleSheet("""
            color: #8d9bb2;
            font-size: 11px;
            border: none;
        """)

        layout.addWidget(
            metadata
        )

        # ----------------------------------------------------
        # READ ARTICLE BUTTON
        # ----------------------------------------------------

        button_row = QHBoxLayout()

        button_row.addStretch()

        read_button = QPushButton(
            "Read Article"
        )

        url = article["url"]

        read_button.clicked.connect(
            lambda checked=False, link=url:
            self.open_news_article(
                link
            )
        )

        button_row.addWidget(
            read_button
        )

        layout.addLayout(
            button_row
        )

        self.news_layout.addWidget(
            card
        )

    # ========================================================
    # OPEN NEWS ARTICLE IN STOCKTERMINAL BROWSER
    # ========================================================

    def open_news_article(self, url):
        self.browser_launcher.open_url(url)
