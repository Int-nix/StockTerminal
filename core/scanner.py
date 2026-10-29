"""
StockTerminal v0.7
Concurrent Stock Scanner

Features:
- Concurrent stock scanning
- Analyst consensus screening
- Configurable worker count
- Analyst data caching
- Cancellation support
- Progress reporting
- Existing scanner compatibility
"""

import math
import time
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
    FIRST_COMPLETED
)

import yfinance as yf

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal
)

from core.analysis import (
    calculate_metrics,
    matches
)


# ==========================================
# CONFIGURATION
# ==========================================

MAX_WORKERS = 8

ANALYST_CACHE_SECONDS = 60 * 60 * 6

ANALYST_CACHE = {}
ANALYST_CACHE_LOCK = threading.Lock()


# ==========================================
# SIGNALS
# ==========================================

class ScannerSignals(QObject):

    progress = Signal(int, int, str)

    result = Signal(object)

    finished = Signal(int, int, bool)


# ==========================================
# HELPERS
# ==========================================

def safe_float(value):

    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return None


def get_number(info, *keys):

    for key in keys:

        value = safe_float(
            info.get(key)
        )

        if value is not None:
            return value

    return None


# ==========================================
# ANALYST CACHE
# ==========================================

def get_cached_analyst(ticker):

    with ANALYST_CACHE_LOCK:

        cached = ANALYST_CACHE.get(
            ticker
        )

        if cached is None:
            return None

        timestamp, data = cached

        age = time.time() - timestamp

        if age > ANALYST_CACHE_SECONDS:

            del ANALYST_CACHE[ticker]

            return None

        return data


def cache_analyst(ticker, data):

    with ANALYST_CACHE_LOCK:

        ANALYST_CACHE[ticker] = (
            time.time(),
            data
        )


# ==========================================
# ANALYST RECOMMENDATIONS
# ==========================================

def get_recommendations(stock):

    recommendations = {
        "strongBuy": 0,
        "buy": 0,
        "hold": 0,
        "sell": 0,
        "strongSell": 0
    }

    try:

        history = stock.recommendations

        if history is None or history.empty:
            return recommendations

        latest = history.iloc[0]

        if "period" in history.columns:

            current = history[
                history["period"].astype(str) == "0m"
            ]

            if not current.empty:
                latest = current.iloc[0]

        for key in recommendations:

            value = safe_float(
                latest.get(key, 0)
            )

            if value is not None:

                recommendations[key] = max(
                    0,
                    int(value)
                )

    except Exception:
        pass

    return recommendations


# ==========================================
# CONSENSUS CALCULATION
# ==========================================

def calculate_consensus(recommendations):

    weights = {
        "strongBuy": 1,
        "buy": 2,
        "hold": 3,
        "sell": 4,
        "strongSell": 5
    }

    total = sum(
        recommendations.values()
    )

    if total == 0:
        return None, None, 0

    score = sum(
        recommendations[key] * weights[key]
        for key in weights
    ) / total

    if score < 1.5:
        rating = "Strong Buy"

    elif score < 2.5:
        rating = "Buy"

    elif score < 3.5:
        rating = "Hold"

    elif score < 4.5:
        rating = "Sell"

    else:
        rating = "Strong Sell"

    return rating, score, total


# ==========================================
# FETCH ANALYST DATA
# ==========================================

def fetch_analyst_data(ticker):

    cached = get_cached_analyst(
        ticker
    )

    if cached is not None:
        return cached

    stock = yf.Ticker(ticker)

    info = stock.info or {}

    recommendations = get_recommendations(
        stock
    )

    data = {
        "info": info,
        "recommendations": recommendations
    }

    cache_analyst(
        ticker,
        data
    )

    return data


# ==========================================
# CONSENSUS BUY SCANNER
# ==========================================

def scan_consensus_buy(
    ticker,
    exchange,
    min_cap_b,
    min_analysts,
    min_upside
):

    data = fetch_analyst_data(
        ticker
    )

    info = data["info"]

    recommendations = data[
        "recommendations"
    ]

    current_price = get_number(
        info,
        "currentPrice",
        "regularMarketPrice"
    )

    target_mean = get_number(
        info,
        "targetMeanPrice"
    )

    target_low = get_number(
        info,
        "targetLowPrice"
    )

    target_high = get_number(
        info,
        "targetHighPrice"
    )

    if (
        current_price is None
        or current_price <= 0
        or target_mean is None
        or target_mean <= 0
    ):
        return None

    market_cap = get_number(
        info,
        "marketCap"
    )

    cap_b = (
        market_cap / 1_000_000_000
        if market_cap is not None
        else None
    )

    if min_cap_b > 0:

        if (
            cap_b is None
            or cap_b < min_cap_b
        ):
            return None

    rating, score, total = (
        calculate_consensus(
            recommendations
        )
    )

    if total < min_analysts:
        return None

    if rating not in (
        "Strong Buy",
        "Buy"
    ):
        return None

    upside = (
        (target_mean / current_price) - 1
    ) * 100

    if upside < min_upside:
        return None

    return {
        "ticker": ticker,
        "exchange": exchange,
        "price": current_price,
        "consensus": rating,
        "target": target_mean,
        "target_low": target_low,
        "target_high": target_high,
        "upside": upside,
        "analysts": total,
        "cap_b": cap_b,
        "score": upside,
        "consensus_score": score,
        "strong_buy": recommendations["strongBuy"],
        "buy": recommendations["buy"],
        "hold": recommendations["hold"],
        "sell": recommendations["sell"],
        "strong_sell": recommendations["strongSell"]
    }


# ==========================================
# INDIVIDUAL STOCK SCANNER
# ==========================================

def scan_stock(
    ticker,
    exchange,
    mode,
    min_cap_b,
    lookback,
    min_analysts,
    min_upside
):

    try:

        # ==================================
        # CONSENSUS BUY
        # ==================================

        if mode == "Consensus Buy":

            result = scan_consensus_buy(
                ticker=ticker,
                exchange=exchange,
                min_cap_b=min_cap_b,
                min_analysts=min_analysts,
                min_upside=min_upside
            )

            return result, False

        # ==================================
        # EXISTING SCANNERS
        # ==================================

        stock = yf.Ticker(ticker)

        history = stock.history(
            period="6mo",
            interval="1d",
            auto_adjust=True
        )

        metrics = calculate_metrics(
            history,
            lookback
        )

        if not metrics:
            return None, True

        if (
            mode == "Value"
            or min_cap_b > 0
        ):

            info = stock.info or {}

        else:
            info = {}

        match = matches(
            mode,
            metrics,
            info,
            min_cap_b
        )

        if match is not None:

            match.update(
                ticker=ticker,
                exchange=exchange
            )

        return match, False

    except Exception:

        return None, True


# ==========================================
# CONCURRENT SCANNER WORKER
# ==========================================

class ScannerWorker(QRunnable):

    def __init__(
        self,
        universe,
        mode,
        min_cap_b=0,
        lookback=20,
        min_analysts=5,
        min_upside=10,
        max_workers=MAX_WORKERS
    ):

        super().__init__()

        self.universe = list(
            universe
        )

        self.mode = mode

        self.min_cap_b = min_cap_b

        self.lookback = lookback

        self.min_analysts = min_analysts

        self.min_upside = min_upside

        self.max_workers = max(
            1,
            min(int(max_workers), 16)
        )

        self.signals = ScannerSignals()

        self.cancel_event = (
            threading.Event()
        )

    # ======================================
    # CANCEL
    # ======================================

    def cancel(self):

        self.cancel_event.set()

    # ======================================
    # SCAN ONE STOCK
    # ======================================

    def process_stock(
        self,
        ticker,
        exchange
    ):

        if self.cancel_event.is_set():
            return None, False

        return scan_stock(
            ticker=ticker,
            exchange=exchange,
            mode=self.mode,
            min_cap_b=self.min_cap_b,
            lookback=self.lookback,
            min_analysts=self.min_analysts,
            min_upside=self.min_upside
        )

    # ======================================
    # MAIN SCANNER
    # ======================================

    def run(self):

        processed = 0
        errors = 0

        total = len(
            self.universe
        )

        if total == 0:

            self.signals.finished.emit(
                0,
                0,
                False
            )

            return

        # Limit outstanding futures so that
        # cancellation doesn't leave hundreds
        # of queued requests waiting.

        executor = ThreadPoolExecutor(
            max_workers=self.max_workers
        )

        pending = {}

        universe_iterator = iter(
            self.universe
        )

        def submit_next():

            if self.cancel_event.is_set():
                return False

            try:
                ticker, exchange = next(
                    universe_iterator
                )

            except StopIteration:
                return False

            future = executor.submit(
                self.process_stock,
                ticker,
                exchange
            )

            pending[future] = ticker

            return True

        try:

            # ==================================
            # INITIAL CONCURRENT REQUESTS
            # ==================================

            for _ in range(
                min(
                    self.max_workers,
                    total
                )
            ):

                if not submit_next():
                    break

            # ==================================
            # PROCESS COMPLETED REQUESTS
            # ==================================

            while pending:

                if self.cancel_event.is_set():
                    break

                completed, _ = wait(
                    pending,
                    timeout=0.2,
                    return_when=FIRST_COMPLETED
                )

                if not completed:
                    continue

                for future in completed:

                    ticker = pending.pop(
                        future
                    )

                    try:

                        match, failed = (
                            future.result()
                        )

                        if failed:
                            errors += 1

                        if (
                            match is not None
                            and not self.cancel_event.is_set()
                        ):

                            self.signals.result.emit(
                                match
                            )

                    except Exception:
                        errors += 1

                    processed += 1

                    self.signals.progress.emit(
                        processed,
                        total,
                        ticker
                    )

                    # Replace the completed request
                    # with the next available ticker.

                    if not self.cancel_event.is_set():
                        submit_next()

        finally:

            if self.cancel_event.is_set():

                for future in pending:
                    future.cancel()

            # Running requests cannot be forcibly
            # interrupted. Wait for them to finish
            # before reporting the scan as complete.

            executor.shutdown(
                wait=True,
                cancel_futures=True
            )

            self.signals.finished.emit(
                processed,
                errors,
                self.cancel_event.is_set()
            )
