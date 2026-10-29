from pathlib import Path

APP_NAME = "StockTerminal"
APP_VERSION = "0.5.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "stocks.db"

COLORS = {
    "background": "#0B1220",
    "sidebar": "#111827",
    "panel": "#172235",
    "panel_light": "#1E293B",
    "border": "#293548",
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "green": "#22C55E",
    "red": "#EF4444",
    "blue": "#3B82F6"
}