"""RSS news retrieval for the StockTerminal dashboard (no API key required)."""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from PySide6.QtCore import QObject, QRunnable, Signal


# ============================================================
# NEWS CATEGORIES
# ============================================================

CATEGORIES = (
    "Trending",
    "Politics",
    "Business",
    "Your Watchlist",
    "Science",
    "Technology",
    "Sports"
)


# ============================================================
# NEWS SEARCHES
# ============================================================

SEARCHES = {
    "Trending": [
        "breaking news when:1d",
        "top news headlines when:1d",
        "world news latest when:1d",
    ],

    "Politics": [
        "politics government elections when:2d",
        "Canada politics parliament government when:2d",
        "US politics congress white house when:2d",
        "world politics international relations when:2d",
    ],

    "Business": [
        "business finance earnings companies markets when:2d",
        "stock market economy financial news when:2d",
    ],

    "Science": [
        "science research discoveries when:7d",
        "scientific breakthroughs research when:7d",
    ],

    "Technology": [
        "technology AI semiconductors innovation when:3d",
        "technology companies software hardware when:3d",
    ],

    "Sports": [
        "sports news when:2d",
        "major sports headlines when:2d",
    ],
}


# Maximum preferred age of articles, in hours.
MAX_AGE_HOURS = {
    "Trending": 24,
    "Politics": 48,
    "Business": 48,
    "Science": 168,
    "Technology": 72,
    "Sports": 48,
    "Your Watchlist": 168,
}


# ============================================================
# SIGNALS
# ============================================================

class NewsSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def feed_url(query):
    return (
        "https://news.google.com/rss/search?q="
        + quote(query, safe="")
        + "&hl=en-CA&gl=CA&ceid=CA:en"
    )


def fetch_feed(query, limit=40):
    request = Request(
        feed_url(query),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; StockTerminal/0.6)"
            ),
            "Cache-Control": "no-cache",
        },
    )

    with urlopen(request, timeout=12) as response:
        content = response.read(2_000_000)

    root = ElementTree.fromstring(content)

    articles = []

    for item in root.findall("./channel/item"):
        title = (
            item.findtext("title") or ""
        ).strip()

        link = (
            item.findtext("link") or ""
        ).strip()

        source = (
            item.findtext("source") or "Unknown source"
        ).strip()

        date_text = (
            item.findtext("pubDate") or ""
        ).strip()

        if not title or not link.startswith("https://"):
            continue

        try:
            published = parsedate_to_datetime(date_text)

            if published.tzinfo is None:
                published = published.replace(
                    tzinfo=timezone.utc
                )

            timestamp = published.timestamp()

            date_label = published.astimezone().strftime(
                "%b %d, %Y · %I:%M %p"
            )

        except (TypeError, ValueError, OverflowError):
            timestamp = 0.0
            date_label = date_text or "Date unavailable"

        articles.append({
            "title": title,
            "source": source,
            "url": link,
            "published": date_label,
            "timestamp": timestamp,
        })

        if len(articles) >= limit:
            break

    return articles


# ============================================================
# ARTICLE PROCESSING
# ============================================================

def process_articles(articles, category, limit=20):
    """
    Deduplicate, filter by age, and sort newest first.

    Older articles are excluded when recent coverage exists.
    """

    unique = {}

    for article in articles:
        url = article.get("url", "")

        if not url:
            continue

        unique.setdefault(url, article)

    articles = list(unique.values())

    articles.sort(
        key=lambda item: item.get("timestamp", 0),
        reverse=True
    )

    max_age = MAX_AGE_HOURS.get(category, 72)

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=max_age)
    ).timestamp()

    recent = [
        article
        for article in articles
        if article.get("timestamp", 0) >= cutoff
    ]

    # Prefer recent articles. If no recent articles are
    # available, show older results instead of a blank page.
    if recent:
        return recent[:limit]

    return articles[:limit]


# ============================================================
# NEWS WORKER
# ============================================================

class NewsWorker(QRunnable):

    def __init__(self, category, watchlist=()):
        super().__init__()

        self.category = category
        self.watchlist = list(watchlist)
        self.signals = NewsSignals()

    def run(self):
        try:

            # ------------------------------------------------
            # WATCHLIST NEWS
            # ------------------------------------------------

            if self.category == "Your Watchlist":

                if not self.watchlist:
                    self.signals.finished.emit([])
                    return

                articles = []
                failures = 0

                for ticker in self.watchlist[:20]:
                    try:
                        query = (
                            f'"{ticker}" stock company earnings when:7d'
                        )

                        articles.extend(
                            fetch_feed(query, limit=8)
                        )

                    except Exception:
                        failures += 1

                if failures == min(len(self.watchlist), 20):
                    raise RuntimeError(
                        "Unable to retrieve watchlist news feeds."
                    )

            # ------------------------------------------------
            # GENERAL NEWS
            # ------------------------------------------------

            else:
                articles = []
                failures = 0

                queries = SEARCHES.get(self.category, [])

                for query in queries:
                    try:
                        articles.extend(
                            fetch_feed(query, limit=40)
                        )

                    except Exception:
                        failures += 1

                if failures == len(queries):
                    raise RuntimeError(
                        f"Unable to retrieve {self.category} news feeds."
                    )

            # ------------------------------------------------
            # SORT / FILTER
            # ------------------------------------------------

            results = process_articles(
                articles,
                self.category,
                limit=20
            )

            self.signals.finished.emit(results)

        except Exception as exc:
            self.signals.error.emit(str(exc))
