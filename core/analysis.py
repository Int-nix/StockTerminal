"""Reusable research indicators, adapted from PyTerm scanning concepts."""

import math
import pandas as pd


def safe_number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def rsi(close, period=14):
    """PyTerm-style simple moving average RSI (not Wilder RSI)."""

    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()

    gain = delta.clip(lower=0).rolling(
        period, min_periods=period
    ).mean()

    loss = (-delta.clip(upper=0)).rolling(
        period, min_periods=period
    ).mean()

    rs = gain / loss.replace(0, float("nan"))
    result = 100 - 100 / (1 + rs)

    result = result.mask(
        (loss == 0) & (gain > 0), 100.0
    )

    result = result.mask(
        (loss == 0) & (gain == 0), 50.0
    )

    return result


def calculate_metrics(history, lookback=20):
    """Return metrics when sufficient daily price history exists."""

    if history is None or len(history) < max(20, lookback + 1):
        return None

    close = pd.to_numeric(
        history["Close"], errors="coerce"
    )

    volume = pd.to_numeric(
        history["Volume"], errors="coerce"
    )

    if close.isna().any() or close.iloc[-1] <= 0:
        return None

    price = float(close.iloc[-1])
    earlier = float(close.iloc[-lookback - 1])
    five_earlier = float(close.iloc[-6])

    if earlier <= 0 or five_earlier <= 0:
        return None

    current_rsi = safe_number(rsi(close).iloc[-1])

    if current_rsi is None:
        return None

    # Compare the latest volume against preceding sessions.
    reference = volume.iloc[-61:-1]

    if len(reference) < 20:
        reference = volume.iloc[:-1]

    mean = safe_number(reference.mean())
    std = safe_number(reference.std())
    today_volume = safe_number(volume.iloc[-1])

    if (
        today_volume is not None
        and mean is not None
        and std
        and std > 0
    ):
        z = (today_volume - mean) / std
    else:
        z = None

    return {
        "price": price,
        "rsi": current_rsi,
        "change": (price / earlier - 1) * 100,
        "five_day": (price / five_earlier - 1) * 100,
        "volume": today_volume,
        "volume_z": z,
        "date": str(history.index[-1].date()),
    }


def matches(mode, metrics, info, minimum_cap_b):
    cap = (
        safe_number(info.get("marketCap"))
        if info else None
    )

    if minimum_cap_b > 0:
        if cap is None or cap < minimum_cap_b * 1e9:
            return None

    output = dict(metrics)

    output["cap_b"] = (
        cap / 1e9 if cap is not None else None
    )

    output["pe"] = (
        safe_number(info.get("trailingPE"))
        if info else None
    )

    output["pb"] = (
        safe_number(info.get("priceToBook"))
        if info else None
    )

    output["peg"] = (
        safe_number(
            info.get("trailingPegRatio")
            or info.get("pegRatio")
        )
        if info else None
    )

    if mode == "Reversal":
        if (
            output["rsi"] >= 45
            or output["five_day"] <= -0.5
        ):
            return None

        output["score"] = (
            45 - output["rsi"] + output["five_day"]
        )

    elif mode == "Volume":
        if (
            output["volume_z"] is None
            or output["volume_z"] < 5
        ):
            return None

        output["score"] = output["volume_z"]

    elif mode == "Value":
        ratios = [
            output["pe"],
            output["pb"],
            output["peg"]
        ]

        if not any(
            x is not None and x > 0
            for x in ratios
        ):
            return None

        if not (
            (
                output["pe"] is not None
                and 0 < output["pe"] < 20
            )
            or (
                output["pb"] is not None
                and 0 < output["pb"] < 2
            )
            or (
                output["peg"] is not None
                and 0 < output["peg"] < 1
            )
        ):
            return None

        output["score"] = sum((
            1 if output["pe"] and 0 < output["pe"] < 20 else 0,
            1 if output["pb"] and 0 < output["pb"] < 2 else 0,
            1 if output["peg"] and 0 < output["peg"] < 1 else 0,
        ))

    else:
        return None

    return output