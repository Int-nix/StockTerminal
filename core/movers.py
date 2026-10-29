"""
Background Yahoo Finance market-movers retrieval for StockTerminal.
"""

import math

from PySide6.QtCore import QObject, QRunnable, Signal

import yfinance as yf


class MoversSignals(QObject):

    finished = Signal(object)
    error = Signal(str)


def number(value):
    try:
        result = float(value)

        return result if math.isfinite(result) else None

    except (TypeError, ValueError, OverflowError):
        return None


class MoversWorker(QRunnable):
    """
    Fetch Yahoo's precomputed US gainers and losers,
    not an exchange-wide scan.
    """

    def __init__(self):
        super().__init__()

        self.signals = MoversSignals()

    def run(self):

        results = []
        failures = []

        for screen_name, direction in (
            ("day_gainers", "Gainers"),
            ("day_losers", "Losers")
        ):

            try:
                response = yf.screen(
                    screen_name,
                    count=100
                )

                quotes = (
                    response.get("quotes", [])
                    if isinstance(response, dict)
                    else []
                )

                for quote in quotes:

                    symbol = quote.get("symbol")

                    change = number(
                        quote.get("regularMarketChangePercent")
                    )

                    if not symbol or change is None:
                        continue

                    results.append({
                        "symbol": str(symbol),

                        "name": str(
                            quote.get("shortName")
                            or quote.get("longName")
                            or symbol
                        ),

                        "change": change,

                        "price": number(
                            quote.get("regularMarketPrice")
                        ),

                        "volume": number(
                            quote.get("regularMarketVolume")
                        ),

                        "market_cap": number(
                            quote.get("marketCap")
                        ),

                        "exchange": str(
                            quote.get("exchange") or ""
                        ),

                        "direction": direction,
                    })

            except Exception as exc:

                failures.append(
                    f"{screen_name}: {exc}"
                )

        if results:

            self.signals.finished.emit(
                results
            )

        else:

            self.signals.error.emit(
                "; ".join(failures)
                or "No movers returned by Yahoo Finance"
            )
