"""
StockTerminal — Paper Trading Interface
Version 0.2.2

Features:
- Virtual portfolio dashboard
- $100,000 starting account
- Simulated stock buying and selling
- Holdings and profit/loss tracking
- Portfolio equity chart
- Transaction history
- Trade journal
- Background Yahoo Finance price retrieval

All trading is simulated.

IMPORTANT:
The metric-card method is named create_metric_card(),
not metric(), because QWidget.metric() is an internal
Qt method. Overriding it causes application crashes.
"""

import math
from datetime import datetime

import yfinance as yf

from PySide6.QtCore import (
    Qt,
    QObject,
    QRunnable,
    Signal,
    QThreadPool,
    QRectF,
    QPointF
)

from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QFont
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QDoubleSpinBox,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QTabWidget,
    QGroupBox,
    QMessageBox,
    QFrame,
    QTextEdit,
    QApplication
)

from core.paper import PaperTradingEngine


# ============================================================
# FORMATTING
# ============================================================

def money(value):
    return f"${float(value):,.2f}"


def signed_money(value):
    value = float(value)

    sign = "+" if value >= 0 else "-"

    return f"{sign}${abs(value):,.2f}"


def format_time(value):
    if not value:
        return "Unknown"

    try:
        return datetime.fromisoformat(
            str(value)
        ).strftime("%Y-%m-%d %H:%M")

    except (ValueError, TypeError):
        return str(value)


def format_shares(value):
    return (
        f"{float(value):,.6f}"
        .rstrip("0")
        .rstrip(".")
    )


# ============================================================
# MARKET QUOTE SIGNALS
# ============================================================

class QuoteSignals(QObject):

    completed = Signal(object)


# ============================================================
# MARKET QUOTE WORKER
# ============================================================

class QuoteWorker(QRunnable):

    def __init__(self, tickers):
        super().__init__()

        # Keep worker lifetime under our control.
        self.setAutoDelete(False)

        self.tickers = list(dict.fromkeys(
            str(ticker).strip().upper()
            for ticker in tickers
            if str(ticker).strip()
        ))

        self.signals = QuoteSignals()

    def run(self):
        results = {}
        errors = []

        for ticker in self.tickers:

            try:
                stock = yf.Ticker(ticker)

                history = stock.history(
                    period="5d",
                    interval="1d",
                    auto_adjust=True
                )

                if history is None or history.empty:
                    errors.append(ticker)
                    continue

                closes = history["Close"].dropna()

                if closes.empty:
                    errors.append(ticker)
                    continue

                price = float(
                    closes.iloc[-1]
                )

                if (
                    not math.isfinite(price)
                    or price <= 0
                ):
                    errors.append(ticker)
                    continue

                quote_time = (
                    closes.index[-1].isoformat()
                )

                results[ticker] = {
                    "price": price,
                    "quote_time": quote_time
                }

            except Exception:
                errors.append(ticker)

        try:
            self.signals.completed.emit({
                "prices": results,
                "errors": errors
            })

        except RuntimeError:
            # The application may already be closing.
            pass


# ============================================================
# PORTFOLIO CHART
# ============================================================

class PortfolioChart(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.values = []

        self.setMinimumHeight(240)

    def set_values(self, values):
        self.values = [
            float(value)
            for value in values
            if math.isfinite(float(value))
        ]

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.fillRect(
            self.rect(),
            QColor("#131c2b")
        )

        chart_rect = QRectF(
            65,
            25,
            max(1, self.width() - 90),
            max(1, self.height() - 70)
        )

        # ----------------------------------------------------
        # GRID
        # ----------------------------------------------------

        painter.setPen(
            QPen(
                QColor("#29384e"),
                1
            )
        )

        for index in range(5):
            y = (
                chart_rect.top()
                + chart_rect.height()
                * index / 4
            )

            painter.drawLine(
                QPointF(chart_rect.left(), y),
                QPointF(chart_rect.right(), y)
            )

        # ----------------------------------------------------
        # EMPTY STATE
        # ----------------------------------------------------

        if not self.values:
            painter.setPen(
                QColor("#8392a9")
            )

            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "No portfolio history yet"
            )

            painter.end()
            return

        # ----------------------------------------------------
        # VALUE RANGE
        # ----------------------------------------------------

        minimum = min(self.values)
        maximum = max(self.values)

        if maximum == minimum:
            padding = max(
                1,
                abs(maximum) * 0.01
            )

        else:
            padding = (
                maximum - minimum
            ) * 0.12

        minimum -= padding
        maximum += padding

        span = maximum - minimum

        # ----------------------------------------------------
        # AXIS LABELS
        # ----------------------------------------------------

        painter.setFont(
            QFont("Arial", 9)
        )

        painter.setPen(
            QColor("#8495ad")
        )

        for index in range(5):
            value = (
                maximum
                - span * index / 4
            )

            y = (
                chart_rect.top()
                + chart_rect.height()
                * index / 4
            )

            painter.drawText(
                QRectF(
                    0,
                    y - 10,
                    60,
                    20
                ),
                Qt.AlignRight | Qt.AlignVCenter,
                f"{value / 1000:,.1f}k"
            )

        # ----------------------------------------------------
        # CHART POINTS
        # ----------------------------------------------------

        points = []

        for index, value in enumerate(self.values):

            if len(self.values) == 1:
                x = (
                    chart_rect.left()
                    + chart_rect.width() / 2
                )

            else:
                x = (
                    chart_rect.left()
                    + index
                    * chart_rect.width()
                    / (len(self.values) - 1)
                )

            y = (
                chart_rect.bottom()
                - (
                    (value - minimum)
                    / span
                ) * chart_rect.height()
            )

            points.append(
                QPointF(x, y)
            )

        # ----------------------------------------------------
        # LINE
        # ----------------------------------------------------

        painter.setPen(
            QPen(
                QColor("#4e9cff"),
                2.5
            )
        )

        for index in range(1, len(points)):
            painter.drawLine(
                points[index - 1],
                points[index]
            )

        # ----------------------------------------------------
        # FINAL POINT
        # ----------------------------------------------------

        if points:
            painter.setBrush(
                QBrush(
                    QColor("#4e9cff")
                )
            )

            painter.drawEllipse(
                points[-1],
                4,
                4
            )

        painter.end()


# ============================================================
# PAPER TRADING PAGE
# ============================================================

class PaperTradingPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.engine = PaperTradingEngine()

        self.pool = QThreadPool.globalInstance()

        self.quote_worker = None

        self.quotes = {}
        self.quote_times = {}

        self.build_ui()

        self.refresh()

    # ========================================================
    # UI HELPERS
    # ========================================================

    def label(self, text, size=12, bold=False):
        widget = QLabel(
            str(text)
        )

        font = widget.font()

        font.setPointSize(
            size
        )

        font.setBold(
            bold
        )

        widget.setFont(
            font
        )

        return widget

    # ========================================================
    # METRIC CARD
    #
    # DO NOT RENAME THIS TO metric().
    # QWidget already defines metric().
    # ========================================================

    def create_metric_card(self, title):
        frame = QFrame()

        frame.setObjectName(
            "MetricCard"
        )

        layout = QVBoxLayout(
            frame
        )

        layout.setContentsMargins(
            16, 12, 16, 12
        )

        layout.setSpacing(
            8
        )

        title_label = self.label(
            title,
            10
        )

        title_label.setObjectName(
            "Muted"
        )

        value_label = self.label(
            "—",
            19,
            True
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            value_label
        )

        return frame, value_label

    # ========================================================
    # TABLE HELPER
    # ========================================================

    def make_table(self, headers):
        table = QTableWidget()

        table.setColumnCount(
            len(headers)
        )

        table.setHorizontalHeaderLabels(
            headers
        )

        table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        table.setAlternatingRowColors(
            True
        )

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        table.verticalHeader().setVisible(
            False
        )

        return table

    def add_row(self, table, values):
        row = table.rowCount()

        table.insertRow(
            row
        )

        for column, value in enumerate(values):
            item = QTableWidgetItem(
                str(value)
            )

            table.setItem(
                row,
                column,
                item
            )

    # ========================================================
    # BUILD MAIN INTERFACE
    # ========================================================

    def build_ui(self):
        root = QVBoxLayout(self)

        root.setContentsMargins(
            24, 20, 24, 20
        )

        root.setSpacing(
            14
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = QHBoxLayout()

        title = self.label(
            "Paper Trading",
            24,
            True
        )

        header.addWidget(
            title
        )

        header.addStretch()

        refresh_button = QPushButton(
            "Refresh Market Prices"
        )

        refresh_button.clicked.connect(
            self.refresh_prices
        )

        header.addWidget(
            refresh_button
        )

        root.addLayout(
            header
        )

        subtitle = self.label(
            "Virtual portfolio simulator — "
            "No real money or brokerage connection"
        )

        subtitle.setObjectName(
            "Muted"
        )

        root.addWidget(
            subtitle
        )

        # ----------------------------------------------------
        # PORTFOLIO METRICS
        # ----------------------------------------------------

        metrics = QGridLayout()

        metrics.setSpacing(
            12
        )

        self.cards = {}

        card_names = [
            ("equity", "Portfolio Value"),
            ("cash", "Available Cash"),
            ("market_value", "Invested Value"),
            ("total_return", "Total Return"),
            ("unrealized_pl", "Unrealized P/L"),
            ("realized_pl", "Realized P/L")
        ]

        for index, (key, name) in enumerate(card_names):

            card, value = self.create_metric_card(
                name
            )

            self.cards[key] = value

            metrics.addWidget(
                card,
                index // 3,
                index % 3
            )

        root.addLayout(
            metrics
        )

        # ----------------------------------------------------
        # TABS
        # ----------------------------------------------------

        self.tabs = QTabWidget()

        root.addWidget(
            self.tabs,
            1
        )

        self.build_portfolio_tab()
        self.build_trade_tab()
        self.build_history_tab()

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status = QLabel(
            "Paper trading ready."
        )

        self.status.setObjectName(
            "Muted"
        )

        root.addWidget(
            self.status
        )

        # ----------------------------------------------------
        # STYLING
        # ----------------------------------------------------

        self.setStyleSheet("""
            QWidget {
                color: #e7edf7;
            }

            QFrame#MetricCard {
                background: #182235;
                border: 1px solid #2a3951;
                border-radius: 8px;
            }

            QLabel#Muted {
                color: #8d9bb2;
            }

            QTableWidget,
            QLineEdit,
            QDoubleSpinBox,
            QComboBox,
            QTextEdit {
                background: #141e2d;
                color: #e7edf7;
                border: 1px solid #304059;
                border-radius: 5px;
                padding: 5px;
            }

            QPushButton {
                background: #254b91;
                color: white;
                border: 1px solid #3864ad;
                border-radius: 5px;
                padding: 8px 14px;
            }

            QPushButton:hover {
                background: #3263b4;
            }

            QPushButton:pressed {
                background: #19396e;
            }

            QGroupBox {
                border: 1px solid #304059;
                border-radius: 7px;
                margin-top: 12px;
                padding: 12px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }

            QTabWidget::pane {
                border: 1px solid #304059;
                background: #101827;
            }

            QTabBar::tab {
                background: #182235;
                color: #9cabc0;
                padding: 9px 18px;
                margin-right: 3px;
            }

            QTabBar::tab:selected {
                background: #254b91;
                color: white;
            }
        """)

    # ========================================================
    # PORTFOLIO TAB
    # ========================================================

    def build_portfolio_tab(self):
        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.setSpacing(
            12
        )

        layout.addWidget(
            self.label(
                "Portfolio Performance",
                15,
                True
            )
        )

        self.chart = PortfolioChart()

        layout.addWidget(
            self.chart,
            2
        )

        layout.addWidget(
            self.label(
                "Current Holdings",
                15,
                True
            )
        )

        self.holdings_table = self.make_table([
            "Ticker",
            "Shares",
            "Avg Cost",
            "Market Price",
            "Market Value",
            "Unrealized P/L",
            "Return %"
        ])

        self.holdings_table.cellDoubleClicked.connect(
            self.holding_selected
        )

        layout.addWidget(
            self.holdings_table,
            3
        )

        self.tabs.addTab(
            page,
            "Portfolio"
        )

    # ========================================================
    # TRADE TAB
    # ========================================================

    def build_trade_tab(self):
        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        group = QGroupBox(
            "Place Simulated Trade"
        )

        form = QGridLayout(
            group
        )

        form.setSpacing(
            12
        )

        # ----------------------------------------------------
        # TICKER
        # ----------------------------------------------------

        self.trade_ticker = QLineEdit()

        self.trade_ticker.setPlaceholderText(
            "AAPL, MSFT, NVDA..."
        )

        self.trade_ticker.textChanged.connect(
            self.update_trade_total
        )

        # ----------------------------------------------------
        # BUY / SELL
        # ----------------------------------------------------

        self.trade_side = QComboBox()

        self.trade_side.addItems([
            "BUY",
            "SELL"
        ])

        # ----------------------------------------------------
        # SHARE QUANTITY
        # ----------------------------------------------------

        self.trade_shares = QDoubleSpinBox()

        self.trade_shares.setRange(
            0.000001,
            1_000_000
        )

        self.trade_shares.setDecimals(
            6
        )

        self.trade_shares.setValue(
            1
        )

        self.trade_shares.valueChanged.connect(
            self.update_trade_total
        )

        # ----------------------------------------------------
        # QUOTE INFORMATION
        # ----------------------------------------------------

        self.trade_price = QLabel(
            "No quote loaded"
        )

        self.quote_date = QLabel(
            "Quote date: —"
        )

        self.quote_date.setObjectName(
            "Muted"
        )

        self.trade_total = QLabel(
            "Estimated total: —"
        )

        # ----------------------------------------------------
        # JOURNAL
        # ----------------------------------------------------

        self.trade_note = QTextEdit()

        self.trade_note.setPlaceholderText(
            "Optional: Why are you making "
            "this simulated trade?"
        )

        self.trade_note.setMaximumHeight(
            90
        )

        # ----------------------------------------------------
        # BUTTONS
        # ----------------------------------------------------

        fetch_button = QPushButton(
            "Get Market Price"
        )

        fetch_button.clicked.connect(
            self.fetch_trade_quote
        )

        execute_button = QPushButton(
            "Execute Paper Trade"
        )

        execute_button.clicked.connect(
            self.execute_trade
        )

        # ----------------------------------------------------
        # FORM
        # ----------------------------------------------------

        form.addWidget(
            QLabel("Ticker"),
            0, 0
        )

        form.addWidget(
            self.trade_ticker,
            0, 1
        )

        form.addWidget(
            QLabel("Action"),
            1, 0
        )

        form.addWidget(
            self.trade_side,
            1, 1
        )

        form.addWidget(
            QLabel("Shares"),
            2, 0
        )

        form.addWidget(
            self.trade_shares,
            2, 1
        )

        form.addWidget(
            fetch_button,
            3, 0
        )

        form.addWidget(
            self.trade_price,
            3, 1
        )

        form.addWidget(
            self.quote_date,
            4, 1
        )

        form.addWidget(
            self.trade_total,
            5, 1
        )

        form.addWidget(
            QLabel("Trade Journal"),
            6, 0
        )

        form.addWidget(
            self.trade_note,
            6, 1
        )

        form.addWidget(
            execute_button,
            7, 1
        )

        layout.addWidget(
            group
        )

        # ----------------------------------------------------
        # NOTICE
        # ----------------------------------------------------

        notice = QLabel(
            "Simulated orders use the latest available "
            "daily closing price. Actual market fills "
            "may differ. No real trades are placed."
        )

        notice.setWordWrap(
            True
        )

        notice.setObjectName(
            "Muted"
        )

        layout.addWidget(
            notice
        )

        layout.addStretch()

        self.tabs.addTab(
            page,
            "Trade"
        )

    # ========================================================
    # TRADE HISTORY TAB
    # ========================================================

    def build_history_tab(self):
        page = QWidget()

        layout = QVBoxLayout(
            page
        )

        layout.addWidget(
            self.label(
                "Transaction History",
                15,
                True
            )
        )

        self.history_table = self.make_table([
            "Date",
            "Ticker",
            "Action",
            "Shares",
            "Price",
            "Total",
            "Realized P/L",
            "Note"
        ])

        layout.addWidget(
            self.history_table
        )

        self.tabs.addTab(
            page,
            "Trade History"
        )

    # ========================================================
    # REFRESH DASHBOARD
    # ========================================================

    def refresh(self):
        summary = self.engine.summary()

        self.cards["equity"].setText(
            money(
                summary["equity"]
            )
        )

        self.cards["cash"].setText(
            money(
                summary["cash"]
            )
        )

        self.cards["market_value"].setText(
            money(
                summary["market_value"]
            )
        )

        self.cards["total_return"].setText(
            f"{summary['total_return']:+.2f}%"
        )

        self.cards["unrealized_pl"].setText(
            signed_money(
                summary["unrealized_pl"]
            )
        )

        self.cards["realized_pl"].setText(
            signed_money(
                summary["realized_pl"]
            )
        )

        self.refresh_holdings()

        self.refresh_history()

        history = self.engine.equity_history()

        self.chart.set_values([
            row["equity"]
            for row in history
        ])

    # ========================================================
    # REFRESH HOLDINGS
    # ========================================================

    def refresh_holdings(self):
        self.holdings_table.setRowCount(
            0
        )

        positions = self.engine.positions()

        prices = self.engine.cached_prices()

        for position in positions:

            ticker = position["ticker"]

            shares = float(
                position["shares"]
            )

            cost = float(
                position["average_cost"]
            )

            cached = prices.get(
                ticker,
                {}
            )

            price = cached.get(
                "price",
                cost
            )

            market_value = (
                shares * price
            )

            unrealized_pl = (
                shares * (price - cost)
            )

            return_percent = (
                (price / cost - 1) * 100
                if cost > 0
                else 0
            )

            self.add_row(
                self.holdings_table,
                [
                    ticker,
                    format_shares(shares),
                    money(cost),
                    money(price),
                    money(market_value),
                    signed_money(unrealized_pl),
                    f"{return_percent:+.2f}%"
                ]
            )

    # ========================================================
    # REFRESH TRADE HISTORY
    # ========================================================

    def refresh_history(self):
        self.history_table.setRowCount(
            0
        )

        trades = self.engine.trades()

        for trade in trades:

            self.add_row(
                self.history_table,
                [
                    format_time(
                        trade["executed_at"]
                    ),
                    trade["ticker"],
                    trade["side"],
                    format_shares(
                        trade["shares"]
                    ),
                    money(
                        trade["price"]
                    ),
                    money(
                        trade["total"]
                    ),
                    signed_money(
                        trade["realized_pl"]
                    ),
                    trade["note"]
                ]
            )

    # ========================================================
    # REQUEST MARKET QUOTES
    # ========================================================

    def request_quotes(self, tickers):

        if self.quote_worker is not None:

            self.status.setText(
                "A market price request is already running."
            )

            return

        tickers = list(dict.fromkeys(
            str(ticker).strip().upper()
            for ticker in tickers
            if str(ticker).strip()
        ))

        if not tickers:
            return

        worker = QuoteWorker(
            tickers
        )

        self.quote_worker = worker

        worker.signals.completed.connect(
            self.quotes_received
        )

        self.status.setText(
            f"Fetching {len(tickers)} market quote(s)..."
        )

        self.pool.start(
            worker
        )

    # ========================================================
    # FETCH SINGLE TRADE QUOTE
    # ========================================================

    def fetch_trade_quote(self):

        ticker = (
            self.trade_ticker.text()
            .strip()
            .upper()
        )

        if not ticker:

            QMessageBox.warning(
                self,
                "Ticker Required",
                "Enter a ticker symbol."
            )

            return

        self.request_quotes([
            ticker
        ])

    # ========================================================
    # REFRESH ALL HELD STOCK PRICES
    # ========================================================

    def refresh_prices(self):

        tickers = [
            position["ticker"]
            for position in self.engine.positions()
        ]

        trade_ticker = (
            self.trade_ticker.text()
            .strip()
            .upper()
        )

        if trade_ticker:
            tickers.append(
                trade_ticker
            )

        if not tickers:

            self.status.setText(
                "No positions to refresh."
            )

            return

        self.request_quotes(
            tickers
        )

    # ========================================================
    # HANDLE MARKET QUOTES
    # ========================================================

    def quotes_received(self, result):

        # The worker has finished.
        self.quote_worker = None

        updated = 0

        for ticker, quote in result["prices"].items():

            price = float(
                quote["price"]
            )

            quote_time = quote[
                "quote_time"
            ]

            self.quotes[ticker] = price

            self.quote_times[ticker] = quote_time

            self.engine.update_price(
                ticker,
                price
            )

            updated += 1

        if updated:
            self.engine.record_equity()

        self.refresh()

        self.update_trade_total()

        failed = len(
            result["errors"]
        )

        self.status.setText(
            f"Updated {updated} market price(s). "
            f"{failed} unavailable."
        )

    # ========================================================
    # UPDATE TRADE ESTIMATE
    # ========================================================

    def update_trade_total(self, *args):

        ticker = (
            self.trade_ticker.text()
            .strip()
            .upper()
        )

        price = self.quotes.get(
            ticker
        )

        if price is None:

            self.trade_price.setText(
                "No quote loaded"
            )

            self.quote_date.setText(
                "Quote date: —"
            )

            self.trade_total.setText(
                "Estimated total: —"
            )

            return

        self.trade_price.setText(
            f"Latest daily close: {money(price)}"
        )

        self.quote_date.setText(
            "Quote date: "
            + format_time(
                self.quote_times.get(ticker)
            )
        )

        shares = self.trade_shares.value()

        total = (
            price * shares
        )

        self.trade_total.setText(
            f"Estimated total: {money(total)}"
        )

    # ========================================================
    # EXECUTE SIMULATED TRADE
    # ========================================================

    def execute_trade(self):

        ticker = (
            self.trade_ticker.text()
            .strip()
            .upper()
        )

        side = (
            self.trade_side.currentText()
        )

        shares = (
            self.trade_shares.value()
        )

        price = self.quotes.get(
            ticker
        )

        if price is None:

            QMessageBox.warning(
                self,
                "Price Required",
                "Fetch a market price before trading."
            )

            return

        total = (
            shares * price
        )

        quote_time = self.quote_times.get(
            ticker
        )

        # ----------------------------------------------------
        # CONFIRM ORDER
        # ----------------------------------------------------

        confirmation = QMessageBox.question(
            self,
            "Confirm Paper Trade",
            f"Execute simulated {side}?\n\n"
            f"Ticker: {ticker}\n"
            f"Shares: {format_shares(shares)}\n"
            f"Estimated price: {money(price)}\n"
            f"Quote date: {format_time(quote_time)}\n"
            f"Estimated total: {money(total)}\n\n"
            "This is a virtual trade using "
            "the latest available daily close.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirmation != QMessageBox.Yes:
            return

        # ----------------------------------------------------
        # EXECUTE
        # ----------------------------------------------------

        try:

            trade = self.engine.execute_trade(
                ticker=ticker,
                side=side,
                shares=shares,
                price=price,
                quote_time=quote_time,
                note=self.trade_note.toPlainText()
            )

            self.engine.record_equity()

        except ValueError as error:

            QMessageBox.warning(
                self,
                "Trade Rejected",
                str(error)
            )

            return

        # ----------------------------------------------------
        # UPDATE INTERFACE
        # ----------------------------------------------------

        self.trade_note.clear()

        self.refresh()

        self.status.setText(
            f"Simulated {trade['side']} completed: "
            f"{format_shares(trade['shares'])} "
            f"{ticker} at {money(trade['price'])}."
        )

        QMessageBox.information(
            self,
            "Paper Trade Executed",
            f"{trade['side']} "
            f"{format_shares(trade['shares'])} "
            f"shares of {ticker}\n\n"
            f"Price: {money(trade['price'])}\n"
            f"Total: {money(trade['total'])}\n\n"
            "No real order was placed."
        )

    # ========================================================
    # SELECT HOLDING
    # ========================================================

    def holding_selected(self, row, column):

        item = self.holdings_table.item(
            row,
            0
        )

        if item is None:
            return

        ticker = item.text()

        self.trade_ticker.setText(
            ticker
        )

        self.tabs.setCurrentIndex(
            1
        )

        self.update_trade_total()


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    import sys

    app = QApplication(
        sys.argv
    )

    window = PaperTradingPage()

    window.setWindowTitle(
        "StockTerminal — Paper Trading"
    )

    window.resize(
        1200,
        850
    )

    window.show()

    sys.exit(
        app.exec()
    )
