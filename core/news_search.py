"""Search Google News RSS without blocking StockTerminal's interface."""
from PySide6.QtCore import QObject, QRunnable, Signal
from core.news import fetch_feed


class SearchSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class NewsSearchWorker(QRunnable):
    def __init__(self, query, limit=40):
        super().__init__()
        self.query = query.strip()
        self.limit = limit
        self.signals = SearchSignals()

    def run(self):
        try:
            if not self.query:
                self.signals.finished.emit([])
                return
            articles = fetch_feed(self.query, limit=self.limit)
            unique = {article['url']: article for article in articles}
            results = sorted(unique.values(), key=lambda a: a.get('timestamp', 0), reverse=True)
            self.signals.finished.emit(results)
        except Exception as exc:
            self.signals.error.emit(str(exc))
