"""
StockTerminal — Paper Trading Engine
Version 0.2.1

Virtual portfolio management and simulated trading.

Features:
- SQLite database
- $100,000 starting virtual balance
- Simulated BUY and SELL transactions
- Weighted-average cost basis
- Realized and unrealized profit/loss
- Portfolio performance tracking
- Market price caching
- Transaction history
- Equity history

IMPORTANT:
This module defines PaperTradingEngine.
It must NOT import PaperTradingEngine from itself.
"""

import math
import sqlite3

from datetime import datetime, timezone
import os
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

STARTING_CASH = 100_000.00

DATA_DIR = Path(
    os.environ.get(
        "STOCKTERMINAL_DATA_DIR",
        str(Path.home() / ".stockterminal")
    )
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DATABASE = DATA_DIR / "paper_trading.db"


# ============================================================
# UTILITIES
# ============================================================

def now():
    """
    Return the current UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )


# ============================================================
# PAPER TRADING ENGINE
# ============================================================

class PaperTradingEngine:

    def __init__(self):

        self.db = sqlite3.connect(
            str(DATABASE)
        )

        self.db.row_factory = sqlite3.Row

        self.initialize()

    # ========================================================
    # DATABASE INITIALIZATION
    # ========================================================

    def initialize(self):

        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                starting_cash REAL NOT NULL,
                cash REAL NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                average_cost REAL NOT NULL,
                PRIMARY KEY (account_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                total REAL NOT NULL,
                realized_pl REAL NOT NULL DEFAULT 0,
                executed_at TEXT NOT NULL,
                quote_time TEXT,
                note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                equity REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT PRIMARY KEY,
                price REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        account = self.db.execute("""
            SELECT id
            FROM accounts
            WHERE id = 1
        """).fetchone()

        if account is None:

            with self.db:

                self.db.execute("""
                    INSERT INTO accounts (
                        id,
                        name,
                        starting_cash,
                        cash,
                        created_at
                    )
                    VALUES (1, ?, ?, ?, ?)
                """, (
                    "Main Portfolio",
                    STARTING_CASH,
                    STARTING_CASH,
                    now()
                ))

                self.db.execute("""
                    INSERT INTO equity_history (
                        account_id,
                        timestamp,
                        equity
                    )
                    VALUES (1, ?, ?)
                """, (
                    now(),
                    STARTING_CASH
                ))

    # ========================================================
    # ACCOUNT INFORMATION
    # ========================================================

    def account(self):

        row = self.db.execute("""
            SELECT *
            FROM accounts
            WHERE id = 1
        """).fetchone()

        if row is None:
            raise RuntimeError(
                "Paper trading account was not found."
            )

        return dict(row)

    # ========================================================
    # POSITIONS
    # ========================================================

    def positions(self):

        rows = self.db.execute("""
            SELECT
                ticker,
                shares,
                average_cost
            FROM positions
            WHERE account_id = 1
              AND shares > 0
            ORDER BY ticker
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def get_position(self, ticker):

        ticker = str(ticker).strip().upper()

        return self.db.execute("""
            SELECT *
            FROM positions
            WHERE account_id = 1
              AND ticker = ?
        """, (
            ticker,
        )).fetchone()

    # ========================================================
    # TRANSACTION HISTORY
    # ========================================================

    def trades(self, limit=500):

        rows = self.db.execute("""
            SELECT *
            FROM trades
            WHERE account_id = 1
            ORDER BY id DESC
            LIMIT ?
        """, (
            int(limit),
        )).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # MARKET PRICE CACHE
    # ========================================================

    def update_price(self, ticker, price):

        ticker = str(ticker).strip().upper()

        price = float(price)

        if not ticker:
            raise ValueError(
                "Ticker symbol is required."
            )

        if (
            not math.isfinite(price)
            or price <= 0
        ):
            raise ValueError(
                "Market price must be positive and finite."
            )

        with self.db:

            self.db.execute("""
                INSERT INTO price_cache (
                    ticker,
                    price,
                    updated_at
                )
                VALUES (?, ?, ?)

                ON CONFLICT(ticker)
                DO UPDATE SET
                    price = excluded.price,
                    updated_at = excluded.updated_at
            """, (
                ticker,
                price,
                now()
            ))

    def cached_prices(self):

        rows = self.db.execute("""
            SELECT
                ticker,
                price,
                updated_at
            FROM price_cache
        """).fetchall()

        return {
            row["ticker"]: {
                "price": row["price"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        }

    # ========================================================
    # EXECUTE SIMULATED TRADE
    # ========================================================

    def execute_trade(
        self,
        ticker,
        side,
        shares,
        price,
        quote_time=None,
        note=""
    ):

        ticker = str(ticker).strip().upper()

        side = str(side).strip().upper()

        shares = float(shares)

        price = float(price)

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not ticker:
            raise ValueError(
                "Ticker symbol is required."
            )

        if side not in (
            "BUY",
            "SELL"
        ):
            raise ValueError(
                "Trade action must be BUY or SELL."
            )

        if (
            not math.isfinite(shares)
            or not math.isfinite(price)
        ):
            raise ValueError(
                "Shares and price must be finite numbers."
            )

        if shares <= 0:
            raise ValueError(
                "Share quantity must be greater than zero."
            )

        if price <= 0:
            raise ValueError(
                "Trade price must be greater than zero."
            )

        shares = round(
            shares,
            6
        )

        price = round(
            price,
            4
        )

        if shares <= 0 or price <= 0:
            raise ValueError(
                "Trade quantity or price is too small."
            )

        total = round(
            shares * price,
            2
        )

        if total <= 0:
            raise ValueError(
                "Trade value is too small."
            )

        # ----------------------------------------------------
        # ACCOUNT STATE
        # ----------------------------------------------------

        account = self.account()

        position = self.get_position(
            ticker
        )

        old_shares = (
            float(position["shares"])
            if position
            else 0.0
        )

        old_cost = (
            float(position["average_cost"])
            if position
            else 0.0
        )

        realized = 0.0

        # ----------------------------------------------------
        # BUY ORDER
        # ----------------------------------------------------

        if side == "BUY":

            if total > account["cash"] + 0.000001:
                raise ValueError(
                    "Insufficient virtual cash."
                )

            new_shares = round(
                old_shares + shares,
                6
            )

            new_cost = (
                (
                    old_shares * old_cost
                    + total
                )
                / new_shares
            )

            new_cash = round(
                account["cash"] - total,
                2
            )

        # ----------------------------------------------------
        # SELL ORDER
        # ----------------------------------------------------

        else:

            if shares > old_shares + 0.000001:
                raise ValueError(
                    "Insufficient shares for this sell order."
                )

            realized = round(
                (price - old_cost) * shares,
                2
            )

            new_shares = round(
                old_shares - shares,
                6
            )

            new_cost = old_cost

            new_cash = round(
                account["cash"] + total,
                2
            )

        # ----------------------------------------------------
        # SAVE TRANSACTION
        # ----------------------------------------------------

        with self.db:

            self.db.execute("""
                UPDATE accounts
                SET cash = ?
                WHERE id = 1
            """, (
                new_cash,
            ))

            # Remove fully closed positions.

            if new_shares <= 0.0000001:

                self.db.execute("""
                    DELETE FROM positions
                    WHERE account_id = 1
                      AND ticker = ?
                """, (
                    ticker,
                ))

            # Insert or update active positions.

            else:

                self.db.execute("""
                    INSERT INTO positions (
                        account_id,
                        ticker,
                        shares,
                        average_cost
                    )
                    VALUES (1, ?, ?, ?)

                    ON CONFLICT(account_id, ticker)
                    DO UPDATE SET
                        shares = excluded.shares,
                        average_cost = excluded.average_cost
                """, (
                    ticker,
                    new_shares,
                    new_cost
                ))

            # Save transaction history.

            self.db.execute("""
                INSERT INTO trades (
                    account_id,
                    ticker,
                    side,
                    shares,
                    price,
                    total,
                    realized_pl,
                    executed_at,
                    quote_time,
                    note
                )
                VALUES (
                    1, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                ticker,
                side,
                shares,
                price,
                total,
                realized,
                now(),
                quote_time,
                str(note)
            ))

        return {
            "ticker": ticker,
            "side": side,
            "shares": shares,
            "price": price,
            "total": total,
            "realized_pl": realized
        }

    # ========================================================
    # PORTFOLIO SUMMARY
    # ========================================================

    def summary(self):

        account = self.account()

        positions = self.positions()

        prices = self.cached_prices()

        market_value = 0.0

        cost_basis = 0.0

        # ----------------------------------------------------
        # CALCULATE HOLDINGS
        # ----------------------------------------------------

        for position in positions:

            ticker = position["ticker"]

            shares = float(
                position["shares"]
            )

            average_cost = float(
                position["average_cost"]
            )

            cached = prices.get(
                ticker,
                {}
            )

            market_price = cached.get(
                "price",
                average_cost
            )

            market_value += (
                shares * market_price
            )

            cost_basis += (
                shares * average_cost
            )

        # ----------------------------------------------------
        # REALIZED PROFIT / LOSS
        # ----------------------------------------------------

        realized_row = self.db.execute("""
            SELECT
                COALESCE(SUM(realized_pl), 0)
            FROM trades
            WHERE account_id = 1
        """).fetchone()

        realized = float(
            realized_row[0]
        )

        # ----------------------------------------------------
        # EQUITY
        # ----------------------------------------------------

        equity = (
            account["cash"]
            + market_value
        )

        unrealized = (
            market_value
            - cost_basis
        )

        # ----------------------------------------------------
        # TOTAL RETURN
        # ----------------------------------------------------

        starting_cash = float(
            account["starting_cash"]
        )

        if starting_cash > 0:

            total_return = (
                (
                    equity / starting_cash
                ) - 1
            ) * 100

        else:

            total_return = 0.0

        return {
            "cash": account["cash"],
            "starting_cash": starting_cash,
            "market_value": market_value,
            "cost_basis": cost_basis,
            "equity": equity,
            "unrealized_pl": unrealized,
            "realized_pl": realized,
            "total_return": total_return
        }

    # ========================================================
    # RECORD PORTFOLIO EQUITY
    # ========================================================

    def record_equity(self):

        summary = self.summary()

        equity = float(
            summary["equity"]
        )

        with self.db:

            self.db.execute("""
                INSERT INTO equity_history (
                    account_id,
                    timestamp,
                    equity
                )
                VALUES (1, ?, ?)
            """, (
                now(),
                equity
            ))

    # ========================================================
    # EQUITY HISTORY
    # ========================================================

    def equity_history(self):

        rows = self.db.execute("""
            SELECT
                timestamp,
                equity
            FROM equity_history
            WHERE account_id = 1
            ORDER BY id
        """).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # DATABASE CLEANUP
    # ========================================================

    def close(self):

        if self.db is not None:

            self.db.close()

            self.db = None
