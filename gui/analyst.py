"""Analyst consensus panel for StockTerminal."""

import math

import pandas as pd
import yfinance as yf

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QProgressBar
)


class AnalystSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def money(value):
    value = number(value)
    return f"${value:,.2f}" if value is not None else "—"


def read_target(info, *keys):
    for key in keys:
        value = number(info.get(key))
        if value is not None:
            return value
    return None


class AnalystWorker(QRunnable):
    def __init__(self, ticker):
        super().__init__()
        self.ticker = ticker.strip().upper()
        self.signals = AnalystSignals()

    def run(self):
        try:
            stock = yf.Ticker(self.ticker)
            info = stock.info or {}

            current = read_target(
                info, "currentPrice", "regularMarketPrice"
            )

            average = read_target(
                info, "targetMeanPrice"
            )

            low = read_target(info, "targetLowPrice")
            high = read_target(info, "targetHighPrice")

            recommendations = {
                "strongBuy": 0,
                "buy": 0,
                "hold": 0,
                "sell": 0,
                "strongSell": 0
            }

            history = stock.recommendations

            if (
                isinstance(history, pd.DataFrame)
                and not history.empty
            ):
                latest = history.iloc[0]

                # Prefer the most recent reporting period
                # when yfinance supplies a period column.
                if "period" in history.columns:
                    matching = history[
                        history["period"].astype(str) == "0m"
                    ]
                    if not matching.empty:
                        latest = matching.iloc[0]

                for key in recommendations:
                    value = number(latest.get(key, 0))
                    recommendations[key] = (
                        max(0, int(value))
                        if value is not None else 0
                    )

            total = sum(recommendations.values())

            upside = None
            if current and average:
                upside = (average / current - 1) * 100

            # Calculate a weighted recommendation score.
            weights = {
                "strongBuy": 1,
                "buy": 2,
                "hold": 3,
                "sell": 4,
                "strongSell": 5
            }

            consensus = "Unavailable"
            score = None

            if total > 0:
                score = sum(
                    recommendations[key] * weights[key]
                    for key in recommendations
                ) / total

                if score < 1.5:
                    consensus = "Strong Buy"
                elif score < 2.5:
                    consensus = "Buy"
                elif score < 3.5:
                    consensus = "Hold"
                elif score < 4.5:
                    consensus = "Sell"
                else:
                    consensus = "Strong Sell"

            self.signals.finished.emit({
                "ticker": self.ticker,
                "current": current,
                "average": average,
                "low": low,
                "high": high,
                "upside": upside,
                "recommendations": recommendations,
                "total": total,
                "consensus": consensus,
                "score": score,
                "target_analysts": info.get(
                    "numberOfAnalystOpinions"
                )
            })

        except Exception as exc:
            self.signals.error.emit(str(exc))


class AnalystConsensus(QWidget):
    """Display price targets and analyst recommendations."""

    def __init__(self, threadpool, parent=None):
        super().__init__(parent)

        self.threadpool = threadpool
        self.worker = None
        self.requested_ticker = None
        self.pending_ticker = None

        self.setObjectName("AnalystConsensus")

        self.setStyleSheet("""
            QFrame#AnalystCard {
                background-color: #172235;
                border: 1px solid #293548;
                border-radius: 8px;
            }
            QProgressBar {
                background-color: #293548;
                border: none;
                border-radius: 4px;
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 4px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 10, 0, 10)
        root.setSpacing(14)

        title = QLabel("Wall Street Analyst Consensus")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        self.status = QLabel(
            "Select a stock to load analyst estimates."
        )
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        grid = QGridLayout()
        grid.setSpacing(10)

        self.values = {}

        metrics = [
            "Consensus Rating",
            "Average Price Target",
            "Current Price",
            "Implied Upside / Downside",
            "Low Price Target",
            "High Price Target",
            "Analyst Opinions"
        ]

        for i, name in enumerate(metrics):
            card = QFrame()
            card.setObjectName("AnalystCard")

            layout = QVBoxLayout(card)
            layout.setContentsMargins(15, 12, 15, 12)

            heading = QLabel(name)
            heading.setStyleSheet("color: #94A3B8;")

            value = QLabel("—")
            value.setStyleSheet(
                "color: #F8FAFC;"
                "font-size: 19px;"
                "font-weight: bold;"
            )

            layout.addWidget(heading)
            layout.addWidget(value)

            grid.addWidget(card, i // 4, i % 4)
            self.values[name] = value

        root.addLayout(grid)

        heading = QLabel("Analyst Recommendations")
        heading.setObjectName("SectionTitle")
        root.addWidget(heading)

        self.bars = {}

        categories = [
            ("strongBuy", "Strong Buy"),
            ("buy", "Buy"),
            ("hold", "Hold"),
            ("sell", "Sell"),
            ("strongSell", "Strong Sell")
        ]

        for key, label in categories:
            row = QHBoxLayout()

            name = QLabel(label)
            name.setFixedWidth(100)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)

            count = QLabel("—")
            count.setFixedWidth(35)

            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(count)

            root.addLayout(row)
            self.bars[key] = (bar, count)

        note = QLabel(
            "Analyst ratings and price targets are estimates, "
            "not guarantees. Data availability varies by ticker. "
            "The displayed consensus is calculated from the "
            "latest available recommendation counts."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color: #94A3B8; font-size: 11px;"
        )
        root.addWidget(note)

    def load_ticker(self, ticker):
        ticker = ticker.strip().upper()

        if not ticker:
            return

        if ticker == self.requested_ticker:
            return

        self.requested_ticker = ticker

        if self.worker is not None:
            self.pending_ticker = ticker
            self.status.setText(
                f"Waiting to load {ticker}..."
            )
            return

        self.start_worker(ticker)

    def start_worker(self, ticker):
        self.status.setText(
            f"Fetching analyst estimates for {ticker}..."
        )

        worker = AnalystWorker(ticker)
        self.worker = worker

        worker.signals.finished.connect(
            lambda data, w=worker:
            self.loaded(data, w)
        )

        worker.signals.error.connect(
            lambda error, w=worker:
            self.failed(error, w)
        )

        self.threadpool.start(worker)

    def loaded(self, data, worker):
        if data["ticker"] == self.requested_ticker:
            self.display_data(data)

        self.finish_worker(worker)

    def failed(self, error, worker):
        if worker.ticker == self.requested_ticker:
            self.status.setText(
                f"Analyst estimates unavailable: {error}"
            )

        self.finish_worker(worker)

    def finish_worker(self, worker):
        if self.worker is worker:
            self.worker = None

        pending = self.pending_ticker
        self.pending_ticker = None

        if pending and pending != worker.ticker:
            self.start_worker(pending)

    def display_data(self, data):
        def set_value(key, value):
            self.values[key].setText(value)

        set_value(
            "Consensus Rating",
            data["consensus"]
        )

        set_value(
            "Average Price Target",
            money(data["average"])
        )

        set_value(
            "Current Price",
            money(data["current"])
        )

        set_value(
            "Low Price Target",
            money(data["low"])
        )

        set_value(
            "High Price Target",
            money(data["high"])
        )

        opinions = data["target_analysts"]

        set_value(
            "Analyst Opinions",
            str(opinions) if opinions is not None else "—"
        )

        upside = data["upside"]

        if upside is not None:
            set_value(
                "Implied Upside / Downside",
                f"{upside:+.2f}%"
            )

            color = (
                "#22C55E"
                if upside >= 0
                else "#EF4444"
            )

            self.values[
                "Implied Upside / Downside"
            ].setStyleSheet(
                f"color: {color};"
                "font-size: 19px;"
                "font-weight: bold;"
            )
        else:
            set_value(
                "Implied Upside / Downside",
                "—"
            )

        total = data["total"]

        for key, (bar, label) in self.bars.items():
            count = data["recommendations"][key]

            percentage = (
                round(count / total * 100)
                if total else 0
            )

            bar.setValue(percentage)
            label.setText(str(count) if total else "—")

        if total:
            self.status.setText(
                f"{data['ticker']} · "
                f"{total} recent recommendation ratings"
            )
        else:
            self.status.setText(
                f"{data['ticker']} · "
                "No recent analyst recommendation counts available"
            )
