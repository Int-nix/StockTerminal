"""History browser and on-demand price comparison for StockTerminal."""
import math
from datetime import datetime

import yfinance as yf
from PySide6.QtCore import QObject, QRunnable, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QAbstractItemView, QMessageBox
)
from core.scan_history import list_scans, get_results


class PriceSignals(QObject):
    finished = Signal(object)


class PriceWorker(QRunnable):
    def __init__(self, results):
        super().__init__()
        self.results = list(results)
        self.signals = PriceSignals()

    def run(self):
        prices = {}
        for ticker in dict.fromkeys(str(r.get("ticker", "")).strip() for r in self.results):
            if not ticker:
                continue
            try:
                history = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
                if not history.empty:
                    close = float(history["Close"].dropna().iloc[-1])
                    if math.isfinite(close) and close > 0:
                        prices[ticker] = close
            except Exception:
                pass
        self.signals.finished.emit(prices)


class ScanHistory(QWidget):
    def __init__(self, threadpool, open_stock=None, parent=None, account_session=None):
        super().__init__(parent)
        self.threadpool = threadpool
        self.cloud = None
        if account_session:
            from core.account_cloud import Cloud
            self.cloud = Cloud(account_session)
        self.open_stock = open_stock
        self.scans = []
        self.results = []
        self.prices = {}
        self.price_worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        title = QLabel("Scan History")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch()
        self.refresh_button = QPushButton("Refresh History")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)
        self.info = QLabel("Saved scans are permanent snapshots. Current prices are fetched only when requested.")
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        splitter = QSplitter(Qt.Vertical)
        self.sessions = QTableWidget(0, 6)
        self.sessions.setHorizontalHeaderLabels(["Date (local)", "Mode", "Exchange", "Matches", "Scanned", "Status"])
        self.sessions.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sessions.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sessions.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sessions.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.sessions.horizontalHeader().setStretchLastSection(True)
        self.sessions.itemSelectionChanged.connect(self.select_scan)
        splitter.addWidget(self.sessions)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        actions = QHBoxLayout()
        self.details = QLabel("Select a saved scan to view its original results.")
        self.details.setObjectName("Muted")
        actions.addWidget(self.details, 1)
        self.compare_button = QPushButton("Compare Latest Prices")
        self.compare_button.clicked.connect(self.compare)
        self.compare_button.setEnabled(False)
        actions.addWidget(self.compare_button)
        bottom_layout.addLayout(actions)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Ticker", "Exchange", "Original Price", "Latest Close", "Change %",
            "Consensus", "Upside %", "Score"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.open_selected)
        bottom_layout.addWidget(self.table)
        splitter.addWidget(bottom)
        splitter.setSizes([190, 460])
        layout.addWidget(splitter, 1)
        self.refresh()

    def refresh(self):
        try:
            if self.cloud:
                snapshots = self.cloud.request('GET', '/account/scans')['scans']
                self._cloud_snapshots = {s['server_id']: s for s in snapshots}
                self.scans = [dict(id=s['server_id'], started_at=s['started_at'],
                    mode=s['mode'], exchange=s['exchange'], match_count=len(s['results']),
                    processed_count=s['processed_count'], universe_count=s['universe_count'],
                    cancelled=s['cancelled'], error_count=s['error_count']) for s in snapshots]
            else:
                self.scans = list_scans()
        except Exception as exc:
            self.info.setText(f"Unable to read scan history: {exc}")
            return
        self.sessions.blockSignals(True)
        self.sessions.setRowCount(0)
        for scan in self.scans:
            row = self.sessions.rowCount()
            self.sessions.insertRow(row)
            try:
                date = datetime.fromisoformat(scan["started_at"]).astimezone().strftime("%b %d, %Y  %I:%M %p")
            except Exception:
                date = scan["started_at"]
            status = "Cancelled" if scan["cancelled"] else ("Partial / errors" if scan["error_count"] else "Complete")
            values = [date, scan["mode"], scan["exchange"], scan["match_count"],
                      f'{scan["processed_count"]}/{scan["universe_count"]}', status]
            for col, value in enumerate(values):
                item = QTableWidgetItem()
                if isinstance(value, int):
                    item.setData(Qt.DisplayRole, value)
                else:
                    item.setText(str(value))
                self.sessions.setItem(row, col, item)
        self.sessions.blockSignals(False)
        if self.scans:
            self.sessions.selectRow(0)
        else:
            self.results = []
            self.table.setRowCount(0)
            self.compare_button.setEnabled(False)
            self.details.setText("No saved scans yet. Run the screener to create your first snapshot.")

    def select_scan(self):
        row = self.sessions.currentRow()
        if not (0 <= row < len(self.scans)):
            return
        scan = self.scans[row]
        try:
            self.results = (self._cloud_snapshots[scan['id']]['results']
                            if self.cloud else get_results(scan['id']))
        except Exception as exc:
            self.details.setText(f"Could not load scan: {exc}")
            return
        self.prices = {}
        self.compare_button.setEnabled(bool(self.results) and self.price_worker is None)
        self.details.setText(f'{scan["mode"]} · {len(self.results)} matches · {scan["error_count"]} failed requests · Double-click a ticker to explore')
        self.populate()

    def populate(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for result in self.results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            ticker = str(result.get("ticker", ""))
            original = result.get("price")
            latest = self.prices.get(ticker)
            change = ((latest / original - 1) * 100 if isinstance(original, (int, float)) and original > 0 and latest is not None else None)
            values = [ticker, result.get("exchange"), original, latest, change,
                      result.get("consensus"), result.get("upside"), result.get("score")]
            for col, value in enumerate(values):
                item = QTableWidgetItem()
                if isinstance(value, (int, float)) and math.isfinite(value):
                    item.setData(Qt.DisplayRole, round(value, 2))
                else:
                    item.setText(str(value) if value is not None else "—")
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    def compare(self):
        if self.price_worker is not None or not self.results:
            return
        self.compare_button.setEnabled(False)
        self.details.setText("Retrieving latest daily closing prices…")
        worker = PriceWorker(self.results)
        self.price_worker = worker
        worker.signals.finished.connect(self.comparison_ready)
        self.threadpool.start(worker)

    def comparison_ready(self, prices):
        self.price_worker = None
        self.prices = prices
        self.populate()
        self.compare_button.setEnabled(bool(self.results))
        self.details.setText(
            f'Latest daily closes available for {len(prices)}/{len(set(str(r.get("ticker", "")) for r in self.results))} tickers. '
            'Changes compare saved scanner quotes with latest closes; not executable returns.'
        )

    def open_selected(self, row, column):
        item = self.table.item(row, 0)
        if item and self.open_stock:
            self.open_stock(item.text())
