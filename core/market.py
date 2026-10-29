import yfinance as yf
from PySide6.QtCore import QObject, Signal, QRunnable

class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)

class MarketWorker(QRunnable):
    def __init__(self, ticker, period="1y"):
        super().__init__()
        self.ticker = ticker
        self.period = period
        self.signals = WorkerSignals()

    def run(self):
        try:
            stock = yf.Ticker(self.ticker)
            interval = {"1d": "5m", "5d": "15m"}.get(self.period, "1d")
            history = stock.history(period=self.period, interval=interval, auto_adjust=True)
            if history.empty:
                raise ValueError(f"No market data available for {self.ticker}")
            try:
                info = stock.info or {}
            except Exception:
                info = {}
            self.signals.finished.emit({"ticker": self.ticker, "period": self.period,
                                        "history": history, "info": info})
        except Exception as error:
            self.signals.error.emit(str(error))

class QuoteWorker(QRunnable):
    """Lightweight periodic quote update; does not fetch company fundamentals."""
    def __init__(self, ticker):
        super().__init__()
        self.ticker = ticker
        self.signals = WorkerSignals()

    def run(self):
        try:
            stock = yf.Ticker(self.ticker)
            minute = stock.history(period="2d", interval="1m", auto_adjust=True)
            if minute.empty:
                raise ValueError("No recent intraday quotes")
            latest = float(minute["Close"].dropna().iloc[-1])
            # Daily close is used as a fallback reference for the change.
            daily = stock.history(period="5d", interval="1d", auto_adjust=True)
            closes = daily["Close"].dropna()
            previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
            last_bar = minute.index[-1].to_pydatetime()
            self.signals.finished.emit({"ticker": self.ticker, "price": latest,
                                        "previous_close": previous, "bar_time": last_bar})
        except Exception as error:
            self.signals.error.emit(str(error))

class IndexWorker(QRunnable):
    """Fetch recent daily index closes without blocking the interface."""
    def __init__(self, ticker):
        super().__init__()
        self.ticker = ticker
        self.signals = WorkerSignals()

    def run(self):
        try:
            history = yf.Ticker(self.ticker).history(period="10d", interval="1d", auto_adjust=False)
            closes = history["Close"].dropna()
            if len(closes) < 2:
                raise ValueError("Not enough recent trading sessions")
            current = float(closes.iloc[-1])
            previous = float(closes.iloc[-2])
            difference = current - previous
            percent = difference / previous * 100 if previous else 0.0
            self.signals.finished.emit({"ticker": self.ticker, "level": current,
                                        "change": difference, "percent": percent,
                                        "date": closes.index[-1].strftime("%Y-%m-%d")})
        except Exception as exc:
            self.signals.error.emit(str(exc))
