
"""RSS news retrieval for StockTerminal, with article thumbnail support."""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse
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
    "Sports",
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
# CONFIGURATION
# ============================================================

RSS_TIMEOUT = 12
IMAGE_TIMEOUT = 5

# Avoid delaying news loading for too long when publishers
# block image metadata requests.
MAX_IMAGE_LOOKUPS = 12

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
)

MEDIA_NS = "http://search.yahoo.com/mrss/"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


# ============================================================
# SIGNALS
# ============================================================

class NewsSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


# ============================================================
# URL HELPERS
# ============================================================

def valid_http_url(url):
    """Return True for ordinary HTTP or HTTPS URLs."""
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )

    except ValueError:
        return False


def normalize_image_url(url, base_url=""):
    """Resolve an image URL relative to its source page."""
    if not url:
        return None

    url = str(url).strip()

    if base_url:
        url = urljoin(base_url, url)

    if valid_http_url(url):
        return url

    return None


# ============================================================
# HTML IMAGE METADATA PARSER
# ============================================================

class ImageMetadataParser(HTMLParser):
    """Extract Open Graph, Twitter, and HTML image metadata."""

    def __init__(self):
        super().__init__()

        self.og_image = None
        self.twitter_image = None
        self.first_image = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag.lower() == "meta":
            property_name = (
                attributes.get("property")
                or attributes.get("name")
                or ""
            ).lower()

            content = attributes.get("content", "")

            if property_name in (
                "og:image",
                "og:image:url",
                "og:image:secure_url",
            ):
                if content and not self.og_image:
                    self.og_image = content

            elif property_name in (
                "twitter:image",
                "twitter:image:src",
            ):
                if content and not self.twitter_image:
                    self.twitter_image = content

        elif tag.lower() == "img":
            source = (
                attributes.get("src")
                or attributes.get("data-src")
                or ""
            )

            if source and not self.first_image:
                self.first_image = source

    def best_image(self):
        return (
            self.og_image
            or self.twitter_image
            or self.first_image
        )


def extract_image_from_html(html, base_url=""):
    """Find a thumbnail URL inside an HTML document."""
    if not html:
        return None

    parser = ImageMetadataParser()

    try:
        parser.feed(html)

    except Exception:
        return None

    return normalize_image_url(
        parser.best_image(),
        base_url,
    )


# ============================================================
# GOOGLE NEWS RSS
# ============================================================

def feed_url(query):
    return (
        "https://news.google.com/rss/search?q="
        + quote(query, safe="")
        + "&hl=en-CA&gl=CA&ceid=CA:en"
    )


def extract_rss_image(item):
    """
    Find an image supplied directly in an RSS entry.

    Supports Media RSS, RSS enclosures, and embedded HTML.
    """

    # Media RSS thumbnail
    for tag in (
        f"{{{MEDIA_NS}}}thumbnail",
        f"{{{MEDIA_NS}}}content",
    ):
        for element in item.findall(tag):
            url = element.attrib.get("url", "")

            media_type = element.attrib.get("type", "")

            if (
                tag.endswith("content")
                and media_type
                and not media_type.startswith("image/")
            ):
                continue

            image = normalize_image_url(url)

            if image:
                return image

    # RSS enclosure
    for enclosure in item.findall("enclosure"):
        url = enclosure.attrib.get("url", "")
        media_type = enclosure.attrib.get("type", "")

        if media_type.startswith("image/"):
            image = normalize_image_url(url)

            if image:
                return image

    # Embedded HTML in the description
    description = item.findtext("description") or ""

    image = extract_image_from_html(description)

    if image:
        return image

    # RSS content:encoded
    encoded = item.findtext(
        f"{{{CONTENT_NS}}}encoded"
    ) or ""

    image = extract_image_from_html(encoded)

    if image:
        return image

    return None


def fetch_feed(query, limit=40):
    request = Request(
        feed_url(query),
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
        },
    )

    with urlopen(
        request,
        timeout=RSS_TIMEOUT,
    ) as response:
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
            item.findtext("source")
            or "Unknown source"
        ).strip()

        date_text = (
            item.findtext("pubDate") or ""
        ).strip()

        if not title or not valid_http_url(link):
            continue

        try:
            published = parsedate_to_datetime(
                date_text
            )

            if published.tzinfo is None:
                published = published.replace(
                    tzinfo=timezone.utc
                )

            timestamp = published.timestamp()

            date_label = (
                published.astimezone().strftime(
                    "%b %d, %Y · %I:%M %p"
                )
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            timestamp = 0.0

            date_label = (
                date_text or "Date unavailable"
            )

        image_url = extract_rss_image(item)

        articles.append({
            "title": title,
            "source": source,
            "url": link,
            "published": date_label,
            "timestamp": timestamp,
            "image_url": image_url,
            "image": image_url,
            "thumbnail": image_url,
        })

        if len(articles) >= limit:
            break

    return articles


# ============================================================
# PUBLISHER IMAGE DISCOVERY
# ============================================================

def fetch_publisher_image(article_url):
    """
    Try to discover an article's Open Graph image.

    Google News may return a redirect or intermediary page,
    so this is best-effort rather than guaranteed.
    """

    if not valid_http_url(article_url):
        return None

    request = Request(
        article_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
        },
    )

    try:
        with urlopen(
            request,
            timeout=IMAGE_TIMEOUT,
        ) as response:

            final_url = response.geturl()

            content_type = (
                response.headers.get(
                    "Content-Type", ""
                ).lower()
            )

            if "text/html" not in content_type:
                return None

            # Read a limited portion of the page.
            content = response.read(500_000)

        html = content.decode(
            "utf-8",
            errors="replace",
        )

        return extract_image_from_html(
            html,
            final_url,
        )

    except Exception:
        return None


def enrich_article_images(
    articles,
    max_lookups=MAX_IMAGE_LOOKUPS,
):
    """
    Add missing thumbnails using article page metadata.

    This function should run inside a background worker,
    never on the GUI thread.
    """

    lookups = 0

    for article in articles:
        image_url = (
            article.get("image_url")
            or article.get("image")
            or article.get("thumbnail")
        )

        if not image_url and lookups < max_lookups:
            lookups += 1

            image_url = fetch_publisher_image(
                article.get("url", "")
            )

        article["image_url"] = image_url
        article["image"] = image_url
        article["thumbnail"] = image_url

    return articles


# ============================================================
# ARTICLE PROCESSING
# ============================================================

def process_articles(
    articles,
    category,
    limit=20,
):
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
        key=lambda item: item.get(
            "timestamp", 0
        ),
        reverse=True,
    )

    max_age = MAX_AGE_HOURS.get(
        category, 72
    )

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=max_age)
    ).timestamp()

    recent = [
        article
        for article in articles
        if article.get("timestamp", 0) >= cutoff
    ]

    if recent:
        return recent[:limit]

    return articles[:limit]


# ============================================================
# NEWS WORKER
# ============================================================

class NewsWorker(QRunnable):

    def __init__(
        self,
        category,
        watchlist=(),
    ):
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
                            f'"{ticker}" stock company '
                            f'earnings when:7d'
                        )

                        articles.extend(
                            fetch_feed(
                                query,
                                limit=8,
                            )
                        )

                    except Exception:
                        failures += 1

                if failures == min(
                    len(self.watchlist), 20
                ):
                    raise RuntimeError(
                        "Unable to retrieve "
                        "watchlist news feeds."
                    )

            # ------------------------------------------------
            # GENERAL NEWS
            # ------------------------------------------------

            else:
                articles = []
                failures = 0

                queries = SEARCHES.get(
                    self.category, []
                )

                for query in queries:
                    try:
                        articles.extend(
                            fetch_feed(
                                query,
                                limit=40,
                            )
                        )

                    except Exception:
                        failures += 1

                if failures == len(queries):
                    raise RuntimeError(
                        f"Unable to retrieve "
                        f"{self.category} news feeds."
                    )

            # ------------------------------------------------
            # SORT / FILTER
            # ------------------------------------------------

            results = process_articles(
                articles,
                self.category,
                limit=20,
            )

            # ------------------------------------------------
            # THUMBNAIL ENRICHMENT
            # ------------------------------------------------

            results = enrich_article_images(
                results
            )

            self.signals.finished.emit(
                results
            )

        except Exception as exc:
            self.signals.error.emit(
                str(exc)
            )
