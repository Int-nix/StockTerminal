import sqlite3
from datetime import datetime
from config import DB_PATH


class Database:

    def __init__(self):
        self.path = DB_PATH
        self.initialize()

    def connect(self):
        return sqlite3.connect(self.path)

    def initialize(self):
        with self.connect() as conn:

            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    ticker TEXT PRIMARY KEY,
                    company_name TEXT,
                    sector TEXT,
                    exchange TEXT,
                    currency TEXT,
                    updated_at TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT UNIQUE NOT NULL,
                    date_added TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_prices (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    PRIMARY KEY (ticker, date)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS screening_results (
                    ticker TEXT PRIMARY KEY,
                    score REAL,
                    valuation_score REAL,
                    technical_score REAL,
                    fundamental_score REAL,
                    updated_at TEXT
                )
            """)

    def add_watchlist(self, ticker):
        ticker = ticker.upper().strip()

        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)",
                (ticker,)
            )

    def remove_watchlist(self, ticker):
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM watchlist WHERE ticker = ?",
                (ticker,)
            )

    def get_watchlist(self):
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT ticker FROM watchlist ORDER BY ticker"
            ).fetchall()

        return [row[0] for row in rows]

    def save_stock(self, ticker, info):
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO stocks (
                    ticker, company_name, sector, exchange,
                    currency, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    company_name=excluded.company_name,
                    sector=excluded.sector,
                    exchange=excluded.exchange,
                    currency=excluded.currency,
                    updated_at=excluded.updated_at
            """, (
                ticker,
                info.get("longName") or info.get("shortName", ticker),
                info.get("sector", ""),
                info.get("exchange", ""),
                info.get("currency", ""),
                datetime.now().isoformat()
            ))

    def save_history(self, ticker, history):
        if history.empty:
            return

        records = []

        for date, row in history.iterrows():
            records.append((
                ticker,
                str(date.date()),
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                int(row["Volume"])
            ))

        with self.connect() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO historical_prices
                (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, records)

    def get_latest_price(self, ticker):
        with self.connect() as conn:
            row = conn.execute("""
                SELECT close, date
                FROM historical_prices
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            """, (ticker,)).fetchone()

        return row