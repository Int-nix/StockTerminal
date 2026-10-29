"""Technical indicators and background market-data retrieval."""

import math

import pandas as pd
import yfinance as yf

from PySide6.QtCore import QObject, QRunnable, Signal


PERIODS = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
    "2Y": "2y",
    "5Y": "5y",
}


class TechnicalSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


def safe_float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def calculate_indicators(history):
    """
    Calculate technical indicators from daily OHLCV data.

    Indicators:
        SMA 20, 50, 200
        Wilder RSI 14
        MACD 12/26/9
        Volume average 20
        Volume Z-score 20
    """

    df = history.copy()

    if df.empty:
        return df

    for column in (
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ):
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    close = df["Close"]
    volume = df["Volume"]

    # ==========================================
    # SIMPLE MOVING AVERAGES
    # ==========================================

    df["SMA20"] = close.rolling(
        window=20,
        min_periods=20
    ).mean()

    df["SMA50"] = close.rolling(
        window=50,
        min_periods=50
    ).mean()

    df["SMA200"] = close.rolling(
        window=200,
        min_periods=200
    ).mean()

    # ==========================================
    # RSI 14 - WILDER SMOOTHING
    # ==========================================

    delta = close.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    period = 14

    # Seed Wilder averages with the first
    # 14 price changes.
    avg_gain = pd.Series(
        float("nan"),
        index=df.index,
        dtype=float
    )

    avg_loss = pd.Series(
        float("nan"),
        index=df.index,
        dtype=float
    )

    if len(df) > period:
        initial_gain = gains.iloc[1:period + 1].mean()
        initial_loss = losses.iloc[1:period + 1].mean()

        avg_gain.iloc[period] = initial_gain
        avg_loss.iloc[period] = initial_loss

        for i in range(period + 1, len(df)):
            avg_gain.iloc[i] = (
                avg_gain.iloc[i - 1] * (period - 1)
                + gains.iloc[i]
            ) / period

            avg_loss.iloc[i] = (
                avg_loss.iloc[i - 1] * (period - 1)
                + losses.iloc[i]
            ) / period

    rs = avg_gain / avg_loss.replace(
        0,
        float("nan")
    )

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100.0
    )

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50.0
    )

    df["RSI"] = rsi

    # ==========================================
    # MACD
    # ==========================================

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["MACD_HIST"] = (
        df["MACD"] - df["MACD_SIGNAL"]
    )

    # ==========================================
    # VOLUME
    # ==========================================

    df["VOLUME_AVG20"] = volume.rolling(
        window=20,
        min_periods=20
    ).mean()

    volume_std = volume.rolling(
        window=20,
        min_periods=20
    ).std()

    df["VOLUME_Z"] = (
        (volume - df["VOLUME_AVG20"])
        / volume_std.replace(0, float("nan"))
    )

    return df


def latest_value(df, column):
    if df.empty or column not in df:
        return None

    return safe_float(df[column].iloc[-1])


def technical_summary(df):
    """Create a rule-based summary of current conditions."""

    if df.empty:
        return {
            "trend": "Unavailable",
            "momentum": "Unavailable",
            "volume": "Unavailable",
            "details": ["No historical data available."],
            "values": {}
        }

    close = latest_value(df, "Close")
    sma20 = latest_value(df, "SMA20")
    sma50 = latest_value(df, "SMA50")
    sma200 = latest_value(df, "SMA200")

    rsi = latest_value(df, "RSI")
    macd = latest_value(df, "MACD")
    signal = latest_value(df, "MACD_SIGNAL")

    volume_z = latest_value(df, "VOLUME_Z")

    details = []

    # ==========================================
    # TREND
    # ==========================================

    if (
        close is not None
        and sma20 is not None
        and sma50 is not None
    ):
        if close > sma20 > sma50:
            trend = "Bullish"

            details.append(
                "Price is above the 20-day and 50-day "
                "moving averages, with the shorter "
                "average above the longer one."
            )

        elif close < sma20 < sma50:
            trend = "Bearish"

            details.append(
                "Price is below the 20-day and 50-day "
                "moving averages, with the shorter "
                "average below the longer one."
            )

        else:
            trend = "Mixed"

            details.append(
                "Moving-average conditions are mixed. "
                "The short- and medium-term trends "
                "do not currently agree."
            )
    else:
        trend = "Insufficient data"

    # ==========================================
    # RSI MOMENTUM
    # ==========================================

    if rsi is None:
        momentum = "Unavailable"

    elif rsi >= 70:
        momentum = "High RSI"

        details.append(
            f"RSI is {rsi:.1f}, above the conventional "
            "70 overbought threshold."
        )

    elif rsi <= 30:
        momentum = "Low RSI"

        details.append(
            f"RSI is {rsi:.1f}, below the conventional "
            "30 oversold threshold."
        )

    elif rsi > 50:
        momentum = "Positive"

        details.append(
            f"RSI is {rsi:.1f}, indicating stronger "
            "recent gains than losses."
        )

    else:
        momentum = "Negative"

        details.append(
            f"RSI is {rsi:.1f}, indicating stronger "
            "recent losses than gains."
        )

    # ==========================================
    # MACD
    # ==========================================

    if macd is not None and signal is not None:
        if macd > signal:
            details.append(
                "MACD is above its signal line, "
                "indicating positive MACD momentum."
            )
        else:
            details.append(
                "MACD is below its signal line, "
                "indicating negative MACD momentum."
            )

    # ==========================================
    # VOLUME
    # ==========================================

    if volume_z is None:
        volume_condition = "Unavailable"

    elif volume_z >= 2:
        volume_condition = "Unusually high"

        details.append(
            f"Trading volume is {volume_z:.2f} "
            "standard deviations above its "
            "20-session average."
        )

    elif volume_z <= -2:
        volume_condition = "Unusually low"

    else:
        volume_condition = "Typical"

    return {
        "trend": trend,
        "momentum": momentum,
        "volume": volume_condition,
        "details": details,
        "values": {
            "price": close,
            "sma20": sma20,
            "sma50": sma50,
            "sma200": sma200,
            "rsi": rsi,
            "macd": macd,
            "signal": signal,
            "volume_z": volume_z,
        }
    }


class TechnicalWorker(QRunnable):
    """Fetch daily history without blocking the GUI."""

    def __init__(self, ticker, period="1y"):
        super().__init__()

        self.ticker = ticker.strip().upper()
        self.period = period

        self.signals = TechnicalSignals()

    def run(self):
        try:
            if not self.ticker:
                raise ValueError("No ticker provided.")

            stock = yf.Ticker(self.ticker)

            # Fetch extra history so long moving
            # averages have enough observations,
            # even when displaying a short period.
            history = stock.history(
                period="5y",
                interval="1d",
                auto_adjust=True
            )

            if history is None or history.empty:
                raise ValueError(
                    "No historical price data available."
                )

            history = history.sort_index()

            history = history.dropna(
                subset=[
                    "Open",
                    "High",
                    "Low",
                    "Close"
                ]
            )

            if history.empty:
                raise ValueError(
                    "No valid OHLC price data available."
                )

            history = calculate_indicators(history)

            summary = technical_summary(history)

            self.signals.finished.emit({
                "ticker": self.ticker,
                "period": self.period,
                "history": history,
                "summary": summary
            })

        except Exception as exc:
            self.signals.error.emit(
                f"{self.ticker}: {exc}"
            )