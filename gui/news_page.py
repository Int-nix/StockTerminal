"""Searchable news research page with automatic trending articles."""

from PySide6.QtCore import Qt, QTimer

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
}


class NewsPageMixin:

    # ========================================================
    # BUILD NEWS PAGE
    # ========================================================

    def build_news_page(self):

        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        title = QLabel("News Research")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Explore trending headlines, search topics, "
            "and read articles in the StockTerminal browser."
        )
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        # ----------------------------------------------------
        # SEARCH BAR
        # ----------------------------------------------------

        search_row = QHBoxLayout()

        self.news_search_input = QLineEdit()
        self.news_search_input.setPlaceholderText(
            "Search a topic, company, event, or ticker..."
        )

        self.news_search_input.returnPressed.connect(
            self.search_news_articles
        )

        search_row.addWidget(self.news_search_input, 1)

        self.news_search_button = QPushButton("Search")
        self.news_search_button.setObjectName("Primary")

        self.news_search_button.clicked.connect(
            self.search_news_articles
        )

        search_row.addWidget(self.news_search_button)

        layout.addLayout(search_row)

        # ----------------------------------------------------
        # TOPIC FILTERS
        # ----------------------------------------------------

        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Quick topic:"))

        self.news_topic = QComboBox()
        self.news_topic.addItems(TOPICS.keys())

        self.news_topic.currentTextChanged.connect(
            self.news_topic_selected
        )

        filter_row.addWidget(self.news_topic)

        filter_row.addSpacing(12)
        filter_row.addWidget(QLabel("Sort:"))

        self.news_sort = QComboBox()
        self.news_sort.addItems([
            "Newest first",
            "Oldest first"
        ])

        self.news_sort.currentIndexChanged.connect(
            self.show_news_search_results
        )

        filter_row.addWidget(self.news_sort)
        filter_row.addStretch()

        layout.addLayout(filter_row)

        # ----------------------------------------------------
        # NEWS HEADING
        # ----------------------------------------------------

        heading_row = QHBoxLayout()

        self.news_results_heading = QLabel(
            "Trending News"
        )
        self.news_results_heading.setObjectName(
            "SectionTitle"
        )

        heading_row.addWidget(
            self.news_results_heading
        )

        heading_row.addStretch()

        self.news_refresh_button = QPushButton(
            "Refresh Articles"
        )

        self.news_refresh_button.clicked.connect(
            self.refresh_news_research
        )

        heading_row.addWidget(
            self.news_refresh_button
        )

        layout.addLayout(heading_row)

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.news_research_status = QLabel(
            "Loading trending articles..."
        )

        self.news_research_status.setObjectName(
            "Muted"
        )

        layout.addWidget(
            self.news_research_status
        )

        # ----------------------------------------------------
        # ARTICLE LIST
        # ----------------------------------------------------

        self.news_results = QListWidget()

        self.news_results.setWordWrap(True)
        self.news_results.setSpacing(7)

        self.news_results.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.news_results.itemDoubleClicked.connect(
            self.open_research_article
        )

        layout.addWidget(
            self.news_results,
            1
        )

        # ----------------------------------------------------
        # READ ARTICLE BUTTON
        # ----------------------------------------------------

        open_button = QPushButton(
            "Read Selected Article"
        )

        open_button.clicked.connect(
            self.open_selected_research_article
        )

        layout.addWidget(open_button)

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.news_search_worker = None
        self.news_search_pending = None

        self.news_search_query = ""
        self.news_search_articles = []

        self.news_research_mode = "Trending"

        self.pages.addWidget(page)

        # Load Trending automatically after the GUI exists.
        QTimer.singleShot(
            0,
            self.load_trending_news
        )

    # ========================================================
    # QUICK TOPIC SELECTION
    # ========================================================

    def news_topic_selected(self, topic):

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

        newest_first = (
            self.news_sort.currentIndex() == 0
        )

        articles = sorted(
            self.news_search_articles,
            key=lambda article: article.get(
                "timestamp",
                0
            ),
            reverse=newest_first
        )

        for article in articles:

            label = (
                f"{article['title']}\n"
                f"{article['source']}  ·  "
                f"{article['published']}"
            )

            item = QListWidgetItem(label)

            item.setData(
                Qt.UserRole,
                article["url"]
            )

            item.setToolTip(
                "Double-click to read in StockTerminal Browser"
            )

            self.news_results.addItem(item)

        if self.news_research_mode == "Trending":

            self.news_research_status.setText(
                f"{len(articles)} trending articles · "
                "newest first · double-click to read"
            )

        else:

            self.news_research_status.setText(
                f"{len(articles)} article(s) found for: "
                f"{self.news_search_query}"
                if articles
                else
                f"No articles found for: "
                f"{self.news_search_query}"
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
