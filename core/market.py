import math
import yfinance as yf

from PySide6.QtCore import QObject, Signal, QRunnable


# ============================================================
# VALIDATION
# ============================================================

def valid_price(value):
    try:
        value = float(value)

        if not math.isfinite(value) or value <= 0:
            return None

        return value

    except (TypeError, ValueError, OverflowError):
        return None


# ============================================================
# WORKER SIGNALS
# ============================================================

class WorkerSignals(QObject):

    finished = Signal(object)
    error = Signal(str)


# ============================================================
# MARKET WORKER
# ============================================================

class MarketWorker(QRunnable):

    def __init__(self, ticker, period="1y"):
        super().__init__()

        self.ticker = ticker
        self.period = period

        self.signals = WorkerSignals()

    def run(self):

        try:

            stock = yf.Ticker(self.ticker)

            interval = {
                "1d": "5m",
                "5d": "15m"
            }.get(self.period, "1d")

            history = stock.history(
                period=self.period,
                interval=interval,
                auto_adjust=False,
                prepost=self.period in ("1d", "5d")
            )

            if history.empty:
                raise ValueError(
                    f"No market data available for {self.ticker}"
                )

            try:
                info = stock.info or {}

            except Exception:
                info = {}

            self.signals.finished.emit({

                "ticker": self.ticker,

                "period": self.period,

                "history": history,

                "info": info

            })

        except Exception as error:

            self.signals.error.emit(str(error))


# ============================================================
# QUOTE WORKER
# ============================================================

class QuoteWorker(QRunnable):

    """
    Retrieve recent intraday prices.

    Includes:
    - Regular trading hours
    - Premarket trading
    - After-hours trading

    Uses unadjusted prices.
    """

    def __init__(self, ticker):

        super().__init__()

        self.ticker = ticker

        self.signals = WorkerSignals()

    def run(self):

        try:

            stock = yf.Ticker(self.ticker)

            # ------------------------------------------------
            # FETCH INTRADAY DATA
            # ------------------------------------------------

            minute = stock.history(
                period="2d",
                interval="1m",
                prepost=True,
                auto_adjust=False
            )

            if minute.empty:
                raise ValueError(
                    "No recent intraday quotes available"
                )

            closes = minute["Close"].dropna()

            if closes.empty:
                raise ValueError(
                    "No valid intraday closing prices"
                )

            latest = valid_price(
                closes.iloc[-1]
            )

            if latest is None:
                raise ValueError(
                    "Latest quote is invalid"
                )

            # ------------------------------------------------
            # PREVIOUS REGULAR CLOSE
            # ------------------------------------------------

            daily = stock.history(
                period="5d",
                interval="1d",
                auto_adjust=False
            )

            daily_closes = daily["Close"].dropna()

            previous = None

            if len(daily_closes) >= 2:

                previous = valid_price(
                    daily_closes.iloc[-2]
                )

            # ------------------------------------------------
            # TIMESTAMP
            # ------------------------------------------------

            last_bar = closes.index[-1].to_pydatetime()

            # ------------------------------------------------
            # RETURN DATA
            # ------------------------------------------------

            self.signals.finished.emit({

                "ticker": self.ticker,

                "price": latest,

                "previous_close": previous,

                "bar_time": last_bar

            })

        except Exception as error:

            self.signals.error.emit(str(error))


# ============================================================
# INDEX WORKER
# ============================================================

class IndexWorker(QRunnable):

    def __init__(self, ticker):

        super().__init__()

        self.ticker = ticker

        self.signals = WorkerSignals()

    def run(self):

        try:

            history = yf.Ticker(
                self.ticker
            ).history(
                period="10d",
                interval="1d",
                auto_adjust=False
            )

            closes = history["Close"].dropna()

            if len(closes) < 2:

                raise ValueError(
                    "Not enough recent trading sessions"
                )

            current = float(closes.iloc[-1])

            previous = float(closes.iloc[-2])

            difference = current - previous

            percent = (
                difference / previous * 100
                if previous
                else 0.0
            )

            self.signals.finished.emit({

                "ticker": self.ticker,

                "level": current,

                "change": difference,

                "percent": percent,

                "date": closes.index[-1].strftime(
                    "%Y-%m-%d"
                )

            })

        except Exception as error:

            self.signals.error.emit(str(error))
