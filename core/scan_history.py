"""Immutable snapshots of completed StockTerminal screening runs."""
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "scan_history.db"


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        finished_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        exchange TEXT NOT NULL,
        filters_json TEXT NOT NULL,
        universe_count INTEGER NOT NULL,
        processed_count INTEGER NOT NULL,
        error_count INTEGER NOT NULL,
        cancelled INTEGER NOT NULL,
        match_count INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
        ticker TEXT NOT NULL,
        price REAL,
        data_json TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_scan ON scan_results(scan_id)")
    db.commit()
    return db


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def save_scan(started_at, mode, exchange, filters, universe_count, processed, errors, cancelled, results):
    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as db:
        cursor = db.execute("""INSERT INTO scans
            (started_at, finished_at, mode, exchange, filters_json, universe_count,
             processed_count, error_count, cancelled, match_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (started_at, finished_at, mode, exchange, json.dumps(clean(filters)),
             universe_count, processed, errors, int(cancelled), len(results)))
        scan_id = cursor.lastrowid
        db.executemany("""INSERT INTO scan_results(scan_id, ticker, price, data_json)
            VALUES (?, ?, ?, ?)""", [
            (scan_id, str(r.get("ticker", "")), r.get("price") if isinstance(r.get("price"), (int, float)) and math.isfinite(r["price"]) else None,
             json.dumps(clean(r))) for r in results
        ])
    return scan_id


def list_scans():
    with connect() as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM scans ORDER BY id DESC")]


def get_results(scan_id):
    with connect() as db:
        rows = db.execute("SELECT data_json FROM scan_results WHERE scan_id=? ORDER BY id", (scan_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]
