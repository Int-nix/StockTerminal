"""Background retrieval and normalization of Yahoo Finance financial statements."""

import math
import yfinance as yf
import pandas as pd

from PySide6.QtCore import QObject, QRunnable, Signal


class FundamentalSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


# Yahoo Finance occasionally changes its statement row names.
STATEMENT_ROWS = {
    "Income Statement": [
        ("Total Revenue", ("Total Revenue", "Operating Revenue")),
        ("Cost of Revenue", ("Cost Of Revenue",)),
        ("Gross Profit", ("Gross Profit",)),
        ("Operating Income", ("Operating Income",)),
        ("Pretax Income", ("Pretax Income",)),
        ("Net Income", ("Net Income", "Net Income Common Stockholders")),
        ("Diluted EPS", ("Diluted EPS",)),
    ],
    "Balance Sheet": [
        ("Total Assets", ("Total Assets",)),
        ("Current Assets", ("Current Assets",)),
        (
            "Cash & Equivalents",
            (
                "Cash And Cash Equivalents",
                "Cash Cash Equivalents And Short Term Investments"
            )
        ),
        (
            "Total Liabilities",
            (
                "Total Liabilities Net Minority Interest",
                "Total Liab"
            )
        ),
        ("Current Liabilities", ("Current Liabilities",)),
        ("Total Debt", ("Total Debt",)),
        (
            "Stockholders Equity",
            ("Stockholders Equity", "Common Stock Equity")
        ),
    ],
    "Cash Flow": [
        ("Operating Cash Flow", ("Operating Cash Flow",)),
        ("Capital Expenditure", ("Capital Expenditure",)),
        ("Free Cash Flow", ("Free Cash Flow",)),
        ("Investing Cash Flow", ("Investing Cash Flow",)),
        ("Financing Cash Flow", ("Financing Cash Flow",)),
        ("End Cash Position", ("End Cash Position",)),
    ],
}


def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def first(info, *names):
    for name in names:
        v = number(info.get(name))
        if v is not None:
            return v
    return None


def normalize_statement(df, statement_name):
    if df is None or df.empty:
        return {
            "dates": [],
            "rows": []
        }

    dates = sorted(df.columns, reverse=True)
    output = []

    for label, aliases in STATEMENT_ROWS[statement_name]:
        found = next(
            (a for a in aliases if a in df.index),
            None
        )

        values = [
            number(df.at[found, d]) if found else None
            for d in dates
        ]

        output.append((label, values))

    return {
        "dates": [
            d.strftime("%Y-%m-%d")
            if hasattr(d, "strftime")
            else str(d)[:10]
            for d in dates
        ],
        "rows": output,
    }


def percentage_change(current, previous):
    if current is None or previous in (None, 0):
        return None

    return (current / previous - 1) * 100


def overview_metrics(info, income, cash):
    metrics = [
        ("Market Cap", first(info, "marketCap"), "money"),
        (
            "Enterprise Value",
            first(info, "enterpriseValue"),
            "money"
        ),
        (
            "Revenue (TTM)",
            first(info, "totalRevenue"),
            "money"
        ),
        (
            "Net Income (TTM)",
            first(info, "netIncomeToCommon"),
            "money"
        ),
        (
            "Profit Margin",
            first(info, "profitMargins"),
            "percent"
        ),
        (
            "Return on Equity",
            first(info, "returnOnEquity"),
            "percent"
        ),
        (
            "Free Cash Flow (TTM)",
            first(info, "freeCashflow"),
            "money"
        ),
        (
            "Debt / Equity",
            first(info, "debtToEquity"),
            "de_ratio"
        ),
    ]

    # Some Yahoo tickers have statement data
    # but incomplete company information.
    if metrics[2][1] is None:
        value = next(
            (
                vals[0]
                for label, vals in income["rows"]
                if label == "Total Revenue" and vals
            ),
            None
        )

        metrics[2] = (
            "Revenue (latest FY)",
            value,
            "money"
        )

    if metrics[3][1] is None:
        value = next(
            (
                vals[0]
                for label, vals in income["rows"]
                if label == "Net Income" and vals
            ),
            None
        )

        metrics[3] = (
            "Net Income (latest FY)",
            value,
            "money"
        )

    if metrics[6][1] is None:
        value = next(
            (
                vals[0]
                for label, vals in cash["rows"]
                if label == "Free Cash Flow" and vals
            ),
            None
        )

        metrics[6] = (
            "Free Cash Flow (latest FY)",
            value,
            "money"
        )

    return metrics


class FundamentalWorker(QRunnable):

    def __init__(self, ticker):
        super().__init__()

        self.ticker = ticker.upper().strip()
        self.signals = FundamentalSignals()

    def run(self):
        try:
            stock = yf.Ticker(self.ticker)

            try:
                info = stock.info or {}
            except Exception:
                info = {}

            statements = {}

            for label, annual_attr, quarterly_attr in [
                (
                    "Income Statement",
                    "income_stmt",
                    "quarterly_income_stmt"
                ),
                (
                    "Balance Sheet",
                    "balance_sheet",
                    "quarterly_balance_sheet"
                ),
                (
                    "Cash Flow",
                    "cashflow",
                    "quarterly_cashflow"
                ),
            ]:
                statements[label] = {}

                for period, attr in [
                    ("Annual", annual_attr),
                    ("Quarterly", quarterly_attr)
                ]:
                    try:
                        df = getattr(stock, attr)
                    except Exception:
                        df = pd.DataFrame()

                    statements[label][period] = (
                        normalize_statement(df, label)
                    )

            if not info and all(
                not statements[k]["Annual"]["dates"]
                for k in statements
            ):
                raise ValueError(
                    f"No company financial data available "
                    f"for {self.ticker}."
                )

            self.signals.finished.emit({
                "ticker": self.ticker,
                "info": info,
                "statements": statements,
                "metrics": overview_metrics(
                    info,
                    statements["Income Statement"]["Annual"],
                    statements["Cash Flow"]["Annual"]
                ),
            })

        except Exception as exc:
            self.signals.error.emit(
                f"{self.ticker}: {exc}"
            )