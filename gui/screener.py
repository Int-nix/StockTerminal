"""StockTerminal stock screener with analyst consensus scanning."""

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QProgressBar,
    QTabWidget,
)

from core.universe import get_universe
from core.scanner import ScannerWorker
from core.scan_history import save_scan
from gui.scan_history import ScanHistory
from datetime import datetime, timezone


class ScreenerMixin:

    # ==========================================
    # BUILD SCREENER
    # ==========================================

    def build_screener(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        self.screener_tabs = QTabWidget()
        outer.addWidget(self.screener_tabs)
        scan_page = QWidget()
        layout = QVBoxLayout(scan_page)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        title = QLabel("Stock Screener")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Research signals from Yahoo Finance data. "
            "Analyst estimates are not guaranteed returns."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ==========================================
        # PRIMARY CONTROLS
        # ==========================================

        row = QHBoxLayout()

        self.scan_exchange = QComboBox()
        self.scan_exchange.addItems([
            "All",
            "TSX",
            "NYSE",
            "NAS",
        ])

        self.scan_mode = QComboBox()
        self.scan_mode.addItems([
            "Reversal",
            "Value",
            "Volume",
            "Consensus Buy",
        ])

        self.scan_mode.currentTextChanged.connect(
            self.scan_mode_changed
        )

        self.scan_cap = QDoubleSpinBox()
        self.scan_cap.setRange(0, 10000)
        self.scan_cap.setDecimals(1)
        self.scan_cap.setSuffix("B min cap")
        self.scan_cap.setToolTip(
            "Minimum market capitalization in billions. "
            "0 disables the filter."
        )

        self.scan_days = QSpinBox()
        self.scan_days.setRange(5, 60)
        self.scan_days.setValue(20)
        self.scan_days.setSuffix(" trading days")
        self.scan_days.setToolTip(
            "Historical lookback period for technical "
            "scanner modes."
        )

        self.scan_start = QPushButton("Run Scan")
        self.scan_start.setObjectName("Primary")
        self.scan_start.clicked.connect(self.start_scan)

        self.scan_stop = QPushButton("Stop")
        self.scan_stop.setEnabled(False)
        self.scan_stop.clicked.connect(self.stop_scan)

        controls = [
            ("Exchange", self.scan_exchange),
            ("Scanner", self.scan_mode),
            ("Lookback", self.scan_days),
            ("Market cap", self.scan_cap),
        ]

        for label, widget in controls:
            row.addWidget(QLabel(label))
            row.addWidget(widget)

        row.addWidget(self.scan_start)
        row.addWidget(self.scan_stop)

        layout.addLayout(row)

        # ==========================================
        # ANALYST CONSENSUS FILTERS
        # ==========================================

        self.consensus_controls = QWidget()

        consensus_row = QHBoxLayout(
            self.consensus_controls
        )
        consensus_row.setContentsMargins(0, 0, 0, 0)

        self.scan_min_analysts = QSpinBox()
        self.scan_min_analysts.setRange(1, 100)
        self.scan_min_analysts.setValue(5)
        self.scan_min_analysts.setToolTip(
            "Minimum number of recent analyst "
            "recommendations required."
        )

        self.scan_min_upside = QDoubleSpinBox()
        self.scan_min_upside.setRange(0, 1000)
        self.scan_min_upside.setDecimals(1)
        self.scan_min_upside.setValue(10)
        self.scan_min_upside.setSuffix("%")
        self.scan_min_upside.setToolTip(
            "Minimum implied upside calculated from "
            "the average analyst price target."
        )

        consensus_row.addWidget(
            QLabel("Minimum analysts:")
        )
        consensus_row.addWidget(
            self.scan_min_analysts
        )

        consensus_row.addSpacing(20)

        consensus_row.addWidget(
            QLabel("Minimum upside:")
        )
        consensus_row.addWidget(
            self.scan_min_upside
        )

        consensus_row.addStretch()

        layout.addWidget(self.consensus_controls)

        # ==========================================
        # STATUS AND PROGRESS
        # ==========================================

        self.scan_status = QLabel(
            "Choose a scan and click Run Scan. "
            "Double-click a result to explore it."
        )
        self.scan_status.setObjectName("Muted")
        self.scan_status.setWordWrap(True)

        layout.addWidget(self.scan_status)

        self.scan_progress = QProgressBar()
        self.scan_progress.setValue(0)

        layout.addWidget(self.scan_progress)

        # ==========================================
        # RESULTS TABLE
        # ==========================================

        self.scan_table = QTableWidget()

        self.scan_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.scan_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.scan_table.setSortingEnabled(True)

        header = self.scan_table.horizontalHeader()
        header.setMouseTracking(True)
        header.setSectionResizeMode(
            QHeaderView.Interactive
        )
        header.setStretchLastSection(True)

        self.scan_table.cellDoubleClicked.connect(
            self.open_scanned_stock
        )

        layout.addWidget(self.scan_table)

        self.screener_tabs.addTab(scan_page, "Screener")
        self.scan_history_widget = ScanHistory(self.threadpool, self._open_history_stock)
        self.screener_tabs.addTab(self.scan_history_widget, "Scan History")
        self.screener_tabs.currentChanged.connect(self._screener_tab_changed)
        self.pages.addWidget(page)

        # ==========================================
        # WORKER STATE
        # ==========================================

        self.scan_worker = None
        self.scan_matches = 0
        self.scan_active_mode = None

        self.configure_scan_columns()

        self.scan_mode_changed(
            self.scan_mode.currentText()
        )

    # ==========================================
    # CONFIGURE TABLE COLUMNS
    # ==========================================

    def configure_scan_columns(self):
        mode = self.scan_mode.currentText()

        if mode == "Consensus Buy":

            self.scan_columns = [
                "Ticker",
                "Exchange",
                "Consensus",
                "Price",
                "Avg Target",
                "Upside %",
                "Low Target",
                "High Target",
                "Analysts",
                "MCap B",
            ]

            self.scan_keys = [
                "ticker",
                "exchange",
                "consensus",
                "price",
                "target",
                "upside",
                "target_low",
                "target_high",
                "analysts",
                "cap_b",
            ]

        else:

            self.scan_columns = [
                "Ticker",
                "Exchange",
                "Price",
                "RSI",
                "P/E",
                "P/B",
                "PEG",
                "5D %",
                "Lookback %",
                "Volume Z",
                "MCap B",
                "Score",
            ]

            self.scan_keys = [
                "ticker",
                "exchange",
                "price",
                "rsi",
                "pe",
                "pb",
                "peg",
                "five_day",
                "change",
                "volume_z",
                "cap_b",
                "score",
            ]

        # ==========================================
        # COLUMN TOOLTIPS
        # ==========================================

        self.scan_tooltips = {

            "Ticker": (
                "STOCK TICKER\n\n"
                "The unique symbol identifying a "
                "publicly traded security."
            ),

            "Exchange": (
                "EXCHANGE / STOCK GROUP\n\n"
                "The stock group from which the scanner "
                "selected this security.\n\n"
                "Initial ticker lists may not represent "
                "verified current exchange listings."
            ),

            "Consensus": (
                "ANALYST CONSENSUS\n\n"
                "Weighted analyst recommendation rating.\n\n"
                "Strong Buy: score below 1.5\n"
                "Buy: 1.5 to below 2.5\n"
                "Hold: 2.5 to below 3.5\n"
                "Sell: 3.5 to below 4.5\n"
                "Strong Sell: 4.5 or higher.\n\n"
                "Based on available recommendation counts."
            ),

            "Price": (
                "STOCK PRICE\n\n"
                "Latest reported stock price.\n\n"
                "Prices are displayed in each security's "
                "trading currency."
            ),

            "Avg Target": (
                "AVERAGE ANALYST PRICE TARGET\n\n"
                "Average target price reported by analysts.\n\n"
                "This is an estimate, not a guaranteed "
                "future price."
            ),

            "Upside %": (
                "ANALYST-IMPLIED UPSIDE\n\n"
                "Calculated as:\n\n"
                "(Average Target / Current Price - 1) × 100\n\n"
                "Higher values indicate a larger gap "
                "between the current price and the "
                "average analyst target.\n\n"
                "This does not represent a guaranteed return."
            ),

            "Low Target": (
                "LOW ANALYST PRICE TARGET\n\n"
                "Lowest reported analyst price target."
            ),

            "High Target": (
                "HIGH ANALYST PRICE TARGET\n\n"
                "Highest reported analyst price target."
            ),

            "Analysts": (
                "ANALYST RECOMMENDATIONS\n\n"
                "Total recent analyst recommendation counts.\n\n"
                "This may differ from the number of analysts "
                "contributing to price targets."
            ),

            "RSI": (
                "RELATIVE STRENGTH INDEX\n\n"
                "A momentum indicator ranging from 0 to 100.\n\n"
                "Below 30: Traditionally oversold.\n"
                "Above 70: Traditionally overbought.\n\n"
                "Extreme readings do not guarantee reversals."
            ),

            "P/E": (
                "PRICE-TO-EARNINGS RATIO\n\n"
                "Share price divided by earnings per share.\n\n"
                "A low P/E does not automatically mean "
                "a stock is undervalued."
            ),

            "P/B": (
                "PRICE-TO-BOOK RATIO\n\n"
                "Compares market valuation with "
                "shareholders' book equity."
            ),

            "PEG": (
                "PRICE/EARNINGS-TO-GROWTH RATIO\n\n"
                "Compares valuation with earnings growth.\n\n"
                "Depends on the reliability of growth estimates."
            ),

            "5D %": (
                "FIVE-DAY PRICE CHANGE\n\n"
                "Percentage price change over the "
                "last five trading sessions."
            ),

            "Lookback %": (
                "LOOKBACK PRICE CHANGE\n\n"
                "Percentage price change over the "
                "selected lookback period."
            ),

            "Volume Z": (
                "VOLUME Z-SCORE\n\n"
                "Measures how unusual the latest trading "
                "volume is relative to recent history.\n\n"
                "High volume does not indicate whether "
                "a stock will rise or fall."
            ),

            "MCap B": (
                "MARKET CAPITALIZATION\n\n"
                "Total market value of outstanding shares, "
                "expressed in billions."
            ),

            "Score": (
                "STOCKTERMINAL SCANNER SCORE\n\n"
                "Reversal: RSI and recent momentum.\n"
                "Value: qualifying valuation ratios.\n"
                "Volume: volume Z-score.\n\n"
                "Scores are not comparable across modes "
                "and do not predict future returns."
            ),
        }

        # ==========================================
        # REBUILD TABLE
        # ==========================================

        self.scan_table.setSortingEnabled(False)

        self.scan_table.setRowCount(0)

        self.scan_table.setColumnCount(
            len(self.scan_columns)
        )

        self.scan_table.setHorizontalHeaderLabels(
            self.scan_columns
        )

        for index, name in enumerate(
            self.scan_columns
        ):
            header_item = (
                self.scan_table.horizontalHeaderItem(index)
            )

            if header_item is not None:
                header_item.setToolTip(
                    self.scan_tooltips.get(name, "")
                )

        self.scan_table.setSortingEnabled(True)

        # ==========================================
        # DEFAULT SORT
        # ==========================================

        if mode == "Consensus Buy":
            column = self.scan_columns.index("Upside %")
        else:
            column = self.scan_columns.index("Score")

        self.scan_table.sortItems(
            column,
            Qt.DescendingOrder
        )

    # ==========================================
    # SCANNER MODE CHANGED
    # ==========================================

    def scan_mode_changed(self, mode):
        is_consensus = (
            mode == "Consensus Buy"
        )

        self.consensus_controls.setVisible(
            is_consensus
        )

        self.scan_days.setEnabled(
            not is_consensus
        )

        # Rebuild the table only when the user
        # changes the scanner mode.
        #
        # Never call this method when a scan
        # finishes, because rebuilding the table
        # clears all results.

        if self.scan_worker is None:
            self.configure_scan_columns()

        if is_consensus:
            self.scan_status.setText(
                "Consensus Buy finds stocks with Buy or "
                "Strong Buy analyst ratings, then ranks "
                "them by analyst-implied upside."
            )
        else:
            self.scan_status.setText(
                "Choose a scan and click Run Scan. "
                "Double-click a result to explore it."
            )

    # ==========================================
    # START SCAN
    # ==========================================

    def start_scan(self):
        if self.scan_worker is not None:
            return

        universe = get_universe(
            self.scan_exchange.currentText()
        )

        if not universe:
            self.scan_status.setText(
                "No symbols available for this exchange."
            )
            return

        self.scan_matches = 0
        self.scan_snapshot_results = []
        self.scan_started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.scan_snapshot_filters = {
            "exchange": self.scan_exchange.currentText(),
            "mode": self.scan_mode.currentText(),
            "lookback_days": self.scan_days.value(),
            "minimum_market_cap_billions": self.scan_cap.value(),
            "minimum_analysts": self.scan_min_analysts.value(),
            "minimum_analyst_upside_percent": self.scan_min_upside.value(),
        }
        self.scan_universe_count = len(universe)

        self.scan_active_mode = (
            self.scan_mode.currentText()
        )

        # Clearing old results here is intentional:
        # a new scan is starting.
        self.configure_scan_columns()

        self.scan_progress.setRange(
            0,
            len(universe)
        )

        self.scan_progress.setValue(0)

        self.scan_start.setEnabled(False)
        self.scan_stop.setEnabled(True)

        # Prevent mode changes during the scan.
        self.scan_mode.setEnabled(False)
        self.scan_exchange.setEnabled(False)

        self.scan_worker = ScannerWorker(
            universe=universe,
            mode=self.scan_active_mode,
            min_cap_b=self.scan_cap.value(),
            lookback=self.scan_days.value(),
            min_analysts=self.scan_min_analysts.value(),
            min_upside=self.scan_min_upside.value(),
        )

        worker = self.scan_worker

        worker.signals.progress.connect(
            self.scan_progress_update
        )

        worker.signals.result.connect(
            self.scan_result_received
        )

        worker.signals.finished.connect(
            self.scan_finished
        )

        self.threadpool.start(worker)

    # ==========================================
    # STOP SCAN
    # ==========================================

    def stop_scan(self):
        if self.scan_worker is not None:
            self.scan_worker.cancel()

            self.scan_status.setText(
                "Stopping after the current "
                "request finishes..."
            )

            self.scan_stop.setEnabled(False)

    # ==========================================
    # SCAN PROGRESS
    # ==========================================

    def scan_progress_update(
        self,
        done,
        total,
        ticker
    ):
        self.scan_progress.setValue(done)

        self.scan_status.setText(
            f"Scanned {done}/{total} · "
            f"{self.scan_matches} matches · "
            f"last: {ticker}"
        )

    # ==========================================
    # RECEIVE SCAN RESULTS
    # ==========================================

    def scan_result_received(self, data):
        self.scan_snapshot_results.append(dict(data))
        self.scan_matches += 1

        self.scan_table.setSortingEnabled(False)

        row = self.scan_table.rowCount()
        self.scan_table.insertRow(row)

        for col, key in enumerate(self.scan_keys):
            value = data.get(key)

            item = QTableWidgetItem()

            if value is None:
                item.setText("—")

            elif isinstance(value, (float, int)):
                item.setData(
                    Qt.DisplayRole,
                    round(float(value), 2)
                )

            else:
                item.setText(str(value))

            # ======================================
            # ANALYST RECOMMENDATION TOOLTIPS
            # ======================================

            if self.scan_active_mode == "Consensus Buy":

                if key == "consensus":
                    score = data.get("consensus_score")

                    if score is not None:
                        item.setToolTip(
                            f"Weighted rating score: "
                            f"{score:.2f}\n\n"
                            f"Strong Buy: "
                            f"{data.get('strong_buy', 0)}\n"
                            f"Buy: {data.get('buy', 0)}\n"
                            f"Hold: {data.get('hold', 0)}\n"
                            f"Sell: {data.get('sell', 0)}\n"
                            f"Strong Sell: "
                            f"{data.get('strong_sell', 0)}"
                        )

                elif key == "upside":
                    item.setToolTip(
                        "Analyst-implied upside based on "
                        "the average price target.\n\n"
                        "Not a predicted or guaranteed return."
                    )

            self.scan_table.setItem(
                row,
                col,
                item
            )

        self.scan_table.setSortingEnabled(True)

        # ======================================
        # SORT RESULTS
        # ======================================

        if self.scan_active_mode == "Consensus Buy":
            sort_column = self.scan_columns.index(
                "Upside %"
            )
        else:
            sort_column = self.scan_columns.index(
                "Score"
            )

        self.scan_table.sortItems(
            sort_column,
            Qt.DescendingOrder
        )

    # ==========================================
    # FINISH SCAN
    # ==========================================

    def scan_finished(
        self,
        done,
        errors,
        cancelled
    ):
        state = (
            "Stopped"
            if cancelled
            else "Completed"
        )

        if self.scan_active_mode == "Consensus Buy":
            self.scan_status.setText(
                f"{state}: {done} scanned, "
                f"{self.scan_matches} consensus-buy matches, "
                f"{errors} failed requests. "
                "Ranked by analyst-implied upside."
            )
        else:
            self.scan_status.setText(
                f"{state}: {done} scanned, "
                f"{self.scan_matches} matches, "
                f"{errors} missing/failed price histories. "
                "Metadata may also be unavailable."
            )

        # Persist the exact worker results, not the rounded/sorted table cells.
        try:
            saved_id = save_scan(
                started_at=self.scan_started_at,
                mode=self.scan_active_mode,
                exchange=self.scan_snapshot_filters["exchange"],
                filters=self.scan_snapshot_filters,
                universe_count=self.scan_universe_count,
                processed=done,
                errors=errors,
                cancelled=cancelled,
                results=self.scan_snapshot_results,
            )
            self.scan_status.setText(self.scan_status.text() + f"  · Saved to history #{saved_id}.")
        except Exception as exc:
            self.scan_status.setText(self.scan_status.text() + f"  · HISTORY SAVE FAILED: {exc}")

        # ======================================
        # RESET WORKER STATE
        # ======================================

        self.scan_worker = None
        self.scan_active_mode = None

        self.scan_start.setEnabled(True)
        self.scan_stop.setEnabled(False)

        self.scan_mode.setEnabled(True)
        self.scan_exchange.setEnabled(True)

        # ======================================
        # IMPORTANT BUG FIX
        # ======================================
        #
        # Previously, scan_finished() called:
        #
        # self.scan_mode_changed(
        #     self.scan_mode.currentText()
        # )
        #
        # That method calls configure_scan_columns(),
        # which clears the results table.
        #
        # Instead, restore the filter visibility
        # directly without rebuilding the table.
        #
        # This preserves every scanned stock
        # after the progress bar reaches 100%.
        # ======================================

        is_consensus = (
            self.scan_mode.currentText()
            == "Consensus Buy"
        )

        self.consensus_controls.setVisible(
            is_consensus
        )

        self.scan_days.setEnabled(
            not is_consensus
        )

        # Do not call scan_mode_changed() here.
        # Do not call configure_scan_columns() here.
        # Do not clear the table.

    # ==========================================
    # OPEN SCANNED STOCK
    # ==========================================

    def open_scanned_stock(
        self,
        row,
        column
    ):
        item = self.scan_table.item(row, 0)

        if item is not None:
            self.change_page(1)
            self.load_stock(item.text())

    def _screener_tab_changed(self, index):
        if index == 1:
            self.scan_history_widget.refresh()

    def _open_history_stock(self, ticker):
        if ticker:
            self.change_page(1)
            self.load_stock(ticker)
