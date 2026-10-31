"""Searchable news research page with automatic trending articles."""

from PySide6.QtCore import Qt, QTimer, QSize, QUrl

from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from shiboken6 import isValid

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QFrame, QScrollArea, QSizePolicy, QGridLayout,
)

from core.news_search import NewsSearchWorker
from core.news import NewsWorker


TOPICS = {
    "Trending": "",
    "All News": "stock market business economy",
    "Markets": "stocks markets investing",
    "Politics": "politics economy government policy",
    "Business": "business earnings companies",
    "Technology": "technology AI semiconductors",
    "Science": "science research discoveries",
    "Sports": "sports news",
    "Economy": "inflation central banks economy",
    "Energy": "energy oil gas markets",
    "Healthcare": "healthcare pharmaceuticals stocks",
    "Crypto": "cryptocurrency bitcoin markets",
}


class NewsPageMixin:

    # ========================================================
    # BUILD NEWS PAGE
    # ========================================================

    def build_news_page(self):
        page = QWidget()
        page.setObjectName("NewsResearchPage")
        page.setStyleSheet("""
            QWidget#NewsResearchPage { background: #0b1423; color: #eaf1ff; }
            QFrame#NewsPanel { background: #101f33; border: 1px solid #263b55;
                               border-radius: 9px; }
            QFrame#NewsArticle { background: #14243a; border: 1px solid #2b405a;
                                 border-radius: 8px; }
            QFrame#NewsArticle:hover { border: 1px solid #3b82f6; background: #182b45; }
            QLabel#NewsMuted { color: #9db0c9; font-size: 11px; }
            QLabel#NewsSection { color: #f2f6ff; font-size: 15px; font-weight: 700; }
            QLabel#NewsHeadline { color: #f2f6ff; font-size: 15px; font-weight: 700; }
            QLabel#NewsImage { background: #1c304b; border: 1px solid #314b69;
                               border-radius: 8px; color: #8da8c9; }
            QPushButton#NewsRead { background: transparent; border: none;
                                   color: #70adff; font-weight: 700; text-align: left; }
            QPushButton#NewsRead:hover { color: #b5d7ff; }
            QLabel#NewsBadge { background: #183a62; color: #91c5ff;
                               border-radius: 5px; padding: 4px 8px;
                               font-size: 10px; font-weight: 700; }
            QPushButton#NewsTopic { background: #162942; color: #bcd0ed;
                                    border: 1px solid #2a405e; border-radius: 7px;
                                    padding: 10px 12px; font-weight: 600; }
            QPushButton#NewsTopic:checked { background: #1956b6; color: white;
                                            border: 1px solid #448aff; }
            QPushButton#NewsTopic:hover { background: #254369; }
            QScrollArea { border: none; background: transparent; }
        """)
        root = QVBoxLayout(page)
        root.setContentsMargins(18, 15, 18, 12)
        root.setSpacing(12)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("News Research")
        title.setObjectName("Title")
        subtitle = QLabel("Explore market headlines, search companies, and research current events")
        subtitle.setObjectName("NewsMuted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()
        root.addLayout(header)

        search_panel = QFrame()
        search_panel.setObjectName("NewsPanel")
        search_layout = QHBoxLayout(search_panel)
        search_layout.setContentsMargins(12, 10, 12, 10)
        self.news_search_input = QLineEdit()
        self.news_search_input.setPlaceholderText("Search a company, ticker, topic, or event...")
        self.news_search_input.returnPressed.connect(self.search_news_articles)
        search_layout.addWidget(self.news_search_input, 1)
        self.news_search_button = QPushButton("Search")
        self.news_search_button.setObjectName("Primary")
        self.news_search_button.clicked.connect(self.search_news_articles)
        search_layout.addWidget(self.news_search_button)
        search_layout.addSpacing(10)
        search_layout.addWidget(QLabel("Topic"))
        self.news_topic = QComboBox()
        self.news_topic.addItems(TOPICS.keys())
        self.news_topic.currentTextChanged.connect(self.news_topic_selected)
        search_layout.addWidget(self.news_topic)
        search_layout.addWidget(QLabel("Sort"))
        self.news_sort = QComboBox()
        self.news_sort.addItems(["Newest first", "Oldest first"])
        self.news_sort.currentIndexChanged.connect(self.show_news_search_results)
        search_layout.addWidget(self.news_sort)
        self.news_refresh_button = QPushButton("↻ Refresh")
        self.news_refresh_button.clicked.connect(self.refresh_news_research)
        search_layout.addWidget(self.news_refresh_button)
        root.addWidget(search_panel)

        # Clickable category ribbon; buttons use the existing search workers.
        ribbon_scroll = QScrollArea()
        ribbon_scroll.setWidgetResizable(True)
        ribbon_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ribbon_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ribbon_scroll.setFixedHeight(67)
        ribbon = QWidget()
        ribbon_layout = QHBoxLayout(ribbon)
        ribbon_layout.setContentsMargins(0, 2, 0, 4)
        ribbon_layout.setSpacing(8)
        self.news_topic_buttons = {}
        for topic in ("Trending", "All News", "Markets", "Business", "Technology",
                      "Politics", "Economy", "Energy", "Healthcare", "Crypto", "Science", "Sports"):
            button = QPushButton(topic)
            button.setObjectName("NewsTopic")
            button.setCheckable(True)
            button.setChecked(topic == "Trending")
            button.clicked.connect(lambda checked=False, t=topic: self.select_news_category(t))
            ribbon_layout.addWidget(button)
            self.news_topic_buttons[topic] = button
        ribbon_layout.addStretch()
        ribbon_scroll.setWidget(ribbon)
        root.addWidget(ribbon_scroll)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        main_panel = QFrame()
        main_panel.setObjectName("NewsPanel")
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(14, 13, 14, 12)
        main_layout.setSpacing(10)
        result_header = QHBoxLayout()
        self.news_results_heading = QLabel("Trending News")
        self.news_results_heading.setObjectName("NewsSection")
        result_header.addWidget(self.news_results_heading)
        result_header.addStretch()
        self.news_research_status = QLabel("Loading trending articles...")
        self.news_research_status.setObjectName("NewsMuted")
        result_header.addWidget(self.news_research_status)
        main_layout.addLayout(result_header)

        self.news_results = QListWidget()
        self.news_results.setObjectName("NewsResults")
        self.news_results.setStyleSheet("""
            QListWidget#NewsResults { background: transparent; border: none; outline: none; }
            QListWidget#NewsResults::item { background: transparent; border: none; }
            QListWidget#NewsResults::item:selected { background: transparent; }
        """)
        self.news_results.setSpacing(12)
        self.news_results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.news_results.itemDoubleClicked.connect(self.open_research_article)
        main_layout.addWidget(self.news_results, 1)
        open_button = QPushButton("Read Selected Article")
        open_button.clicked.connect(self.open_selected_research_article)
        main_layout.addWidget(open_button)
        columns.addWidget(main_panel, 1)

        sidebar = QWidget()
        sidebar.setFixedWidth(275)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)

        topics_panel = QFrame()
        topics_panel.setObjectName("NewsPanel")
        topics_layout = QVBoxLayout(topics_panel)
        topics_title = QLabel("POPULAR RESEARCH TOPICS")
        topics_title.setObjectName("NewsSection")
        topics_layout.addWidget(topics_title)
        for text, query in (("Earnings", "company earnings reports"),
                            ("Artificial intelligence", "AI artificial intelligence stocks"),
                            ("Federal Reserve", "Federal Reserve interest rates"),
                            ("Inflation", "inflation economy markets"),
                            ("Semiconductors", "semiconductor industry stocks"),
                            ("Electric vehicles", "electric vehicles automotive stocks")):
            btn = QPushButton(text)
            btn.setObjectName("NewsTopic")
            btn.clicked.connect(lambda checked=False, q=query: self.search_news_topic(q))
            topics_layout.addWidget(btn)
        side_layout.addWidget(topics_panel)

        feature_panel = QFrame()
        feature_panel.setObjectName("NewsPanel")
        feature_layout = QVBoxLayout(feature_panel)
        feature_heading = QLabel("FEATURED ARTICLE")
        feature_heading.setObjectName("NewsSection")
        feature_layout.addWidget(feature_heading)
        self.news_feature_image = QLabel("STOCKTERMINAL  /  NEWS")
        self.news_feature_image.setObjectName("NewsImage")
        self.news_feature_image.setAlignment(Qt.AlignCenter)
        self.news_feature_image.setFixedHeight(142)
        feature_layout.addWidget(self.news_feature_image)
        self.news_feature_title = QLabel("Waiting for headlines...")
        self.news_feature_title.setObjectName("NewsHeadline")
        self.news_feature_title.setWordWrap(True)
        feature_layout.addWidget(self.news_feature_title)
        self.news_feature_meta = QLabel("Latest article from your news results")
        self.news_feature_meta.setObjectName("NewsMuted")
        self.news_feature_meta.setWordWrap(True)
        feature_layout.addWidget(self.news_feature_meta)
        feature_button = QPushButton("Read Featured Article")
        feature_button.setObjectName("Primary")
        feature_button.clicked.connect(self.open_featured_news_article)
        feature_layout.addWidget(feature_button)
        side_layout.addWidget(feature_panel)

        tip_panel = QFrame()
        tip_panel.setObjectName("NewsPanel")
        tip_layout = QVBoxLayout(tip_panel)
        tip_title = QLabel("RESEARCH WORKSPACE")
        tip_title.setObjectName("NewsSection")
        tip_layout.addWidget(tip_title)
        tip = QLabel("Search a ticker such as AAPL or NVDA to find related news. "
                     "Double-click any headline to open it in the StockTerminal browser.")
        tip.setObjectName("NewsMuted")
        tip.setWordWrap(True)
        tip_layout.addWidget(tip)
        side_layout.addWidget(tip_panel)
        side_layout.addStretch()
        columns.addWidget(sidebar)
        root.addLayout(columns, 1)

        self.news_feature_url = None
        self.news_image_manager = QNetworkAccessManager(page)
        self.news_image_cache = {}
        self.news_image_waiters = {}
        self.news_image_active = {}
        self.news_image_queue = []
        self.news_image_max_concurrent = 5
        self.news_search_worker = None
        self.news_search_pending = None
        self.news_search_query = ""
        self.news_search_articles = []
        self.news_research_mode = "Trending"
        self.pages.addWidget(page)
        QTimer.singleShot(0, self.load_trending_news)

    def select_news_category(self, topic):
        self.news_topic.setCurrentText(topic)
        # setCurrentText does not emit when choosing the already-selected topic.
        if topic == "Trending" and self.news_research_mode != "Trending":
            self.load_trending_news()

    def search_news_topic(self, query):
        self.news_search_input.setText(query)
        self.search_news_articles()

    def open_featured_news_article(self):
        if self.news_feature_url:
            self.browser_launcher.open_url(self.news_feature_url)

    def _sync_news_topic_buttons(self, selected):
        for topic, button in self.news_topic_buttons.items():
            button.setChecked(topic == selected)

    def _news_image_placeholder(self, width, height, title="MARKET NEWS"):
        """Attractive fallback when a publisher doesn't expose a thumbnail."""
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#172b45"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#294a70"))
        for x in range(0, width, 24):
            painter.drawLine(x, 0, x + 50, height)
        painter.setPen(QColor("#91b7e7"))
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter | Qt.TextWordWrap, title)
        painter.end()
        return pixmap

    def _news_set_image(self, label, pixmap):
        if label is None or not isValid(label):
            return
        if pixmap.isNull():
            return
        label.setPixmap(pixmap.scaled(
            label.width(), label.height(),
            Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        ))

    def _news_request_image(self, article, label):
        """Nonblocking image retrieval; GUI never waits on publisher hosts."""
        url = (article.get("image_url") or article.get("thumbnail")
               or article.get("image") or "")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            return
        if url in self.news_image_cache:
            self._news_set_image(label, self.news_image_cache[url])
            return
        self.news_image_waiters.setdefault(url, []).append(label)
        if url in self.news_image_active or url in self.news_image_queue:
            return
        self.news_image_queue.append(url)
        self._news_pump_images()

    def _news_pump_images(self):
        while (self.news_image_queue and
               len(self.news_image_active) < self.news_image_max_concurrent):
            url = self.news_image_queue.pop(0)
            request = QNetworkRequest(QUrl(url))
            request.setAttribute(
                QNetworkRequest.RedirectPolicyAttribute,
                QNetworkRequest.NoLessSafeRedirectPolicy
            )
            request.setRawHeader(b"User-Agent", b"Mozilla/5.0 StockTerminal/0.6")
            request.setTransferTimeout(8000)
            reply = self.news_image_manager.get(request)
            self.news_image_active[url] = reply
            reply.finished.connect(
                lambda u=url, r=reply: self._news_image_finished(u, r)
            )

    def _news_image_finished(self, url, reply):
        self.news_image_active.pop(url, None)
        pixmap = QPixmap()
        if reply.error() == reply.NetworkError.NoError:
            data = bytes(reply.readAll())
            if len(data) <= 5_000_000:
                pixmap.loadFromData(data)
        reply.deleteLater()
        if not pixmap.isNull():
            if len(self.news_image_cache) >= 100:
                self.news_image_cache.pop(next(iter(self.news_image_cache)))
            self.news_image_cache[url] = pixmap
            for label in self.news_image_waiters.pop(url, []):
                self._news_set_image(label, pixmap)
        else:
            self.news_image_waiters.pop(url, None)
        self._news_pump_images()

    def _make_news_card(self, article):
        """Mockup-inspired horizontal card with real thumbnail and article metadata."""
        card = QFrame()
        card.setObjectName("NewsArticle")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(15)

        picture = QLabel()
        picture.setObjectName("NewsImage")
        picture.setFixedSize(180, 118)
        picture.setAlignment(Qt.AlignCenter)
        self._news_set_image(picture, self._news_image_placeholder(180, 118))
        layout.addWidget(picture)

        content = QVBoxLayout()
        content.setSpacing(7)
        meta_row = QHBoxLayout()
        badge = QLabel(str(article.get("source") or "NEWS").upper()[:28])
        badge.setObjectName("NewsBadge")
        meta_row.addWidget(badge)
        meta_row.addStretch()
        published = QLabel(str(article.get("published") or ""))
        published.setObjectName("NewsMuted")
        meta_row.addWidget(published)
        content.addLayout(meta_row)

        headline = QLabel(str(article.get("title") or "Untitled article"))
        headline.setObjectName("NewsHeadline")
        headline.setWordWrap(True)
        headline.setMaximumHeight(55)
        content.addWidget(headline)
        description = article.get("description") or article.get("summary") or ""
        if description:
            excerpt = QLabel(str(description))
            excerpt.setObjectName("NewsMuted")
            excerpt.setWordWrap(True)
            excerpt.setMaximumHeight(38)
            content.addWidget(excerpt)
        content.addStretch()
        footer = QHBoxLayout()
        read = QPushButton("Read full article  ↗")
        read.setObjectName("NewsRead")
        read.setCursor(Qt.PointingHandCursor)
        read.clicked.connect(
            lambda checked=False, url=article.get("url"):
            self.browser_launcher.open_url(url) if url else None
        )
        footer.addWidget(read)
        footer.addStretch()
        content.addLayout(footer)
        layout.addLayout(content, 1)
        self._news_request_image(article, picture)
        return card

    # ========================================================
    # QUICK TOPIC SELECTION
    # ========================================================

    def news_topic_selected(self, topic):

        self._sync_news_topic_buttons(topic)

        if topic == "Trending":

            self.news_search_input.clear()
            self.load_trending_news()
            return

        query = TOPICS.get(topic, topic)

        self.news_search_input.setText(query)

        self.search_news_articles()

    # ========================================================
    # SEARCH ARTICLES
    # ========================================================

    def search_news_articles(self):

        query = self.news_search_input.text().strip()

        # Empty search returns to Trending.
        if not query:

            self.news_research_mode = "Trending"

            self.news_topic.blockSignals(True)
            self.news_topic.setCurrentText("Trending")
            self.news_topic.blockSignals(False)

            self.load_trending_news()
            return

        self.news_research_mode = "Search"
        self.news_search_query = query

        self.news_results_heading.setText(
            f"Search Results: {query}"
        )

        if self.news_search_worker is not None:

            self.news_search_pending = (
                "Search",
                query
            )

            self.news_research_status.setText(
                "Search queued; waiting for current request..."
            )

            return

        self._start_news_search(query)

    # ========================================================
    # LOAD TRENDING
    # ========================================================

    def load_trending_news(self):

        self.news_research_mode = "Trending"
        self.news_search_query = ""
        self._sync_news_topic_buttons("Trending")

        self.news_results_heading.setText(
            "Trending News"
        )

        if self.news_search_worker is not None:

            self.news_search_pending = (
                "Trending",
                ""
            )

            self.news_research_status.setText(
                "Trending news queued..."
            )

            return

        self._start_trending_news()

    # ========================================================
    # START TRENDING WORKER
    # ========================================================

    def _start_trending_news(self):

        self.news_research_status.setText(
            "Fetching the latest trending headlines..."
        )

        self.news_search_button.setEnabled(False)
        self.news_refresh_button.setEnabled(False)

        worker = NewsWorker("Trending")

        self.news_search_worker = worker

        worker.signals.finished.connect(
            lambda results, w=worker:
            self._trending_news_finished(
                results,
                w
            )
        )

        worker.signals.error.connect(
            lambda error, w=worker:
            self._trending_news_failed(
                error,
                w
            )
        )

        self.threadpool.start(worker)

    # ========================================================
    # TRENDING FINISHED
    # ========================================================

    def _trending_news_finished(
        self,
        results,
        worker
    ):

        if self.news_research_mode == "Trending":

            self.news_search_articles = results

            self.show_news_search_results()

        self._complete_news_search(worker)

    # ========================================================
    # TRENDING FAILED
    # ========================================================

    def _trending_news_failed(
        self,
        error,
        worker
    ):

        if self.news_research_mode == "Trending":

            self.news_research_status.setText(
                f"Unable to load trending news: {error}"
            )

        self._complete_news_search(worker)

    # ========================================================
    # START SEARCH WORKER
    # ========================================================

    def _start_news_search(self, query):

        self.news_research_status.setText(
            f"Searching for: {query}..."
        )

        self.news_search_button.setEnabled(False)
        self.news_refresh_button.setEnabled(False)

        worker = NewsSearchWorker(query)

        self.news_search_worker = worker

        worker.signals.finished.connect(
            lambda results, w=worker, q=query:
            self._news_search_finished(
                results,
                w,
                q
            )
        )

        worker.signals.error.connect(
            lambda error, w=worker, q=query:
            self._news_search_failed(
                error,
                w,
                q
            )
        )

        self.threadpool.start(worker)

    # ========================================================
    # SEARCH FINISHED
    # ========================================================

    def _news_search_finished(
        self,
        results,
        worker,
        query
    ):

        if (
            self.news_research_mode == "Search"
            and query == self.news_search_query
        ):

            self.news_search_articles = results

            self.show_news_search_results()

        self._complete_news_search(worker)

    # ========================================================
    # SEARCH FAILED
    # ========================================================

    def _news_search_failed(
        self,
        error,
        worker,
        query
    ):

        if (
            self.news_research_mode == "Search"
            and query == self.news_search_query
        ):

            self.news_research_status.setText(
                f"Unable to search news: {error}"
            )

        self._complete_news_search(worker)

    # ========================================================
    # COMPLETE WORKER
    # ========================================================

    def _complete_news_search(self, worker):

        if self.news_search_worker is worker:
            self.news_search_worker = None

        self.news_search_button.setEnabled(True)
        self.news_refresh_button.setEnabled(True)

        pending = self.news_search_pending
        self.news_search_pending = None

        if pending:

            mode, query = pending

            if mode == "Trending":

                self._start_trending_news()

            elif mode == "Search":

                self._start_news_search(query)

    # ========================================================
    # REFRESH
    # ========================================================

    def refresh_news_research(self):

        if self.news_research_mode == "Trending":

            self.load_trending_news()

        else:

            self.search_news_articles()

    # ========================================================
    # DISPLAY RESULTS
    # ========================================================

    def show_news_search_results(self):
        if not hasattr(self, "news_results"):
            return
        self.news_results.clear()
        newest_first = self.news_sort.currentIndex() == 0
        articles = sorted(
            self.news_search_articles,
            key=lambda article: article.get("timestamp") or 0,
            reverse=newest_first,
        )
        for article in articles:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, article.get("url"))
            item.setToolTip("Double-click to read in StockTerminal Browser")
            card = self._make_news_card(article)
            item.setSizeHint(QSize(100, max(154, card.sizeHint().height() + 8)))
            self.news_results.addItem(item)
            self.news_results.setItemWidget(item, card)
        if articles:
            featured = articles[0]
            self.news_feature_title.setText(str(featured.get("title") or "Untitled article"))
            self.news_feature_meta.setText("  •  ".join(filter(None, (
                str(featured.get("source") or "Unknown source"),
                str(featured.get("published") or "")))))
            self.news_feature_url = featured.get("url")
            self._news_set_image(self.news_feature_image,
                                 self._news_image_placeholder(275, 142, "FEATURED STORY"))
            self._news_request_image(featured, self.news_feature_image)
        else:
            self.news_feature_title.setText("No articles available")
            self.news_feature_meta.setText("Try another search or refresh the feed")
            self.news_feature_url = None
            self._news_set_image(self.news_feature_image,
                                 self._news_image_placeholder(275, 142, "NO IMAGE"))
        if self.news_research_mode == "Trending":
            self.news_research_status.setText(f"{len(articles)} trending articles")
        else:
            self.news_research_status.setText(
                f"{len(articles)} article(s) for: {self.news_search_query}"
            )

    # ========================================================
    # OPEN ARTICLE
    # ========================================================

    def open_research_article(self, item):

        url = item.data(Qt.UserRole)

        if url:
            self.browser_launcher.open_url(url)

    def open_selected_research_article(self):

        item = self.news_results.currentItem()

        if item is not None:
            self.open_research_article(item)
