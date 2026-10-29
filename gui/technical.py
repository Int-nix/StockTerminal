"""Technical Analysis page and interactive technical chart."""

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox,
    QFrame, QGridLayout, QScrollArea
)

from core.technical import TechnicalWorker, PERIODS
from gui.analyst import AnalystConsensus


GREEN = QColor("#22C55E")
RED = QColor("#EF4444")
BLUE = QColor("#3B82F6")
YELLOW = QColor("#FACC15")
PURPLE = QColor("#A78BFA")
CYAN = QColor("#22D3EE")
MUTED = QColor("#94A3B8")
BORDER = QColor("#293548")
BACKGROUND = QColor("#172235")


def display_number(value, decimals=2):
    try:
        value = float(value)
        if math.isfinite(value):
            return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        pass
    return "—"


class TechnicalChart(QWidget):
    """
    Interactive technical chart.

    Displays:
        - Candlesticks
        - SMA 20, 50 and 200
        - RSI
        - MACD and signal
        - MACD histogram
        - Trading volume
        - Average trading volume

    Controls:
        Mouse wheel = zoom
        Left drag = pan
        Mouse hover = inspect candle
    """

    def __init__(self):
        super().__init__()

        self.data = None
        self.visible_count = 100
        self.end_index = 0

        self.show_sma20 = True
        self.show_sma50 = True
        self.show_sma200 = False

        self.hover_index = None
        self.drag_position = None
        self.drag_remainder = 0

        self.setMinimumHeight(700)
        self.setMouseTracking(True)

        self.setStyleSheet(
            "background-color: #172235;"
        )

    def set_data(self, data, period="1Y"):
        self.data = data

        if data is None or data.empty:
            self.end_index = 0
            self.hover_index = None
            self.update()
            return

        counts = {
            "1M": 22,
            "3M": 65,
            "6M": 130,
            "1Y": 252,
            "2Y": 504,
            "5Y": 1260
        }

        self.visible_count = min(
            counts.get(period, 252),
            len(data)
        )

        self.end_index = len(data)
        self.hover_index = None
        self.update()

    def set_period(self, period):
        if self.data is not None:
            self.set_data(self.data, period)

    def set_overlays(self, sma20, sma50, sma200):
        self.show_sma20 = sma20
        self.show_sma50 = sma50
        self.show_sma200 = sma200
        self.update()

    def visible_data(self):
        if self.data is None or self.data.empty:
            return None, 0

        end = max(
            1,
            min(self.end_index, len(self.data))
        )

        start = max(
            0,
            end - self.visible_count
        )

        return self.data.iloc[start:end], start

    def panel_rectangles(self):
        left = 62
        right = 75

        width = max(
            50,
            self.width() - left - right
        )

        top = 32

        available = max(
            400,
            self.height() - 75
        )

        heights = [
            available * 0.47,
            available * 0.16,
            available * 0.19,
            available * 0.18
        ]

        rectangles = []
        y = top

        for height in heights:
            rectangles.append(
                QRectF(
                    left,
                    y,
                    width,
                    height - 12
                )
            )
            y += height

        return rectangles

    def series_value(self, value):
        try:
            value = float(value)
            if math.isfinite(value):
                return value
        except (TypeError, ValueError):
            pass

        return None

    def draw_text(
        self,
        painter,
        x,
        y,
        text,
        color=MUTED
    ):
        painter.setPen(color)
        painter.drawText(
            int(x),
            int(y),
            str(text)
        )

    def draw_panel(self, painter, rect, title):
        painter.setPen(QPen(BORDER, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        self.draw_text(
            painter,
            rect.left() + 8,
            rect.top() + 16,
            title
        )

    def draw_line_series(
        self,
        painter,
        df,
        column,
        rect,
        minimum,
        maximum,
        color,
        width=1.5
    ):
        if column not in df or len(df) < 2:
            return

        step = rect.width() / len(df)
        painter.setPen(QPen(color, width))

        previous = None

        for i, value in enumerate(df[column]):
            value = self.series_value(value)

            if value is None:
                previous = None
                continue

            x = rect.left() + (i + 0.5) * step

            y = rect.bottom() - (
                (value - minimum)
                / max(maximum - minimum, 0.000001)
            ) * rect.height()

            point = QPointF(x, y)

            if previous is not None:
                painter.drawLine(previous, point)

            previous = point

    def draw_price(self, painter, df, rect):
        columns = ["Low", "High"]

        if self.show_sma20:
            columns.append("SMA20")

        if self.show_sma50:
            columns.append("SMA50")

        if self.show_sma200:
            columns.append("SMA200")

        values = []

        for column in columns:
            if column not in df:
                continue

            for raw in df[column]:
                value = self.series_value(raw)

                if value is not None:
                    values.append(value)

        if not values:
            return

        minimum = min(values)
        maximum = max(values)

        padding = max(
            (maximum - minimum) * 0.08,
            abs(maximum) * 0.002,
            0.001
        )

        minimum -= padding
        maximum += padding

        def y_price(value):
            return rect.bottom() - (
                (value - minimum)
                / max(maximum - minimum, 0.000001)
            ) * rect.height()

        step = rect.width() / len(df)

        candle_width = max(
            1.0,
            min(12.0, step * 0.65)
        )

        for i, (_, candle) in enumerate(df.iterrows()):
            opening = self.series_value(candle["Open"])
            closing = self.series_value(candle["Close"])
            high = self.series_value(candle["High"])
            low = self.series_value(candle["Low"])

            if None in (opening, closing, high, low):
                continue

            color = GREEN if closing >= opening else RED

            x = rect.left() + (i + 0.5) * step

            painter.setPen(QPen(color, 1))

            painter.drawLine(
                QPointF(x, y_price(high)),
                QPointF(x, y_price(low))
            )

            top = min(
                y_price(opening),
                y_price(closing)
            )

            bottom = max(
                y_price(opening),
                y_price(closing)
            )

            painter.fillRect(
                QRectF(
                    x - candle_width / 2,
                    top,
                    candle_width,
                    max(1.0, bottom - top)
                ),
                color
            )

        overlays = [
            ("SMA20", self.show_sma20, YELLOW),
            ("SMA50", self.show_sma50, BLUE),
            ("SMA200", self.show_sma200, PURPLE)
        ]

        for column, enabled, color in overlays:
            if enabled:
                self.draw_line_series(
                    painter,
                    df,
                    column,
                    rect,
                    minimum,
                    maximum,
                    color,
                    1.7
                )

        self.draw_text(
            painter,
            rect.right() + 5,
            rect.top() + 12,
            display_number(maximum)
        )

        self.draw_text(
            painter,
            rect.right() + 5,
            rect.bottom(),
            display_number(minimum)
        )

    def draw_rsi(self, painter, df, rect):
        for level in (30, 50, 70):
            y = rect.bottom() - (
                level / 100
            ) * rect.height()

            painter.setPen(
                QPen(BORDER, 1, Qt.DashLine)
            )

            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )

            self.draw_text(
                painter,
                rect.right() + 5,
                y + 4,
                str(level)
            )

        self.draw_line_series(
            painter,
            df,
            "RSI",
            rect,
            0,
            100,
            PURPLE,
            1.8
        )

    def draw_macd(self, painter, df, rect):
        values = []

        for column in (
            "MACD",
            "MACD_SIGNAL",
            "MACD_HIST"
        ):
            if column not in df:
                continue

            for raw in df[column]:
                value = self.series_value(raw)

                if value is not None:
                    values.append(value)

        if not values:
            return

        minimum = min(min(values), 0)
        maximum = max(max(values), 0)

        padding = max(
            (maximum - minimum) * 0.1,
            0.001
        )

        minimum -= padding
        maximum += padding

        def y_value(value):
            return rect.bottom() - (
                (value - minimum)
                / (maximum - minimum)
            ) * rect.height()

        zero_y = y_value(0)

        painter.setPen(
            QPen(BORDER, 1, Qt.DashLine)
        )

        painter.drawLine(
            QPointF(rect.left(), zero_y),
            QPointF(rect.right(), zero_y)
        )

        step = rect.width() / len(df)

        for i, raw in enumerate(df["MACD_HIST"]):
            value = self.series_value(raw)

            if value is None:
                continue

            x = rect.left() + (i + 0.5) * step
            y = y_value(value)

            painter.fillRect(
                QRectF(
                    x - step * 0.3,
                    min(y, zero_y),
                    max(1.0, step * 0.6),
                    max(1.0, abs(y - zero_y))
                ),
                GREEN if value >= 0 else RED
            )

        self.draw_line_series(
            painter,
            df,
            "MACD",
            rect,
            minimum,
            maximum,
            CYAN
        )

        self.draw_line_series(
            painter,
            df,
            "MACD_SIGNAL",
            rect,
            minimum,
            maximum,
            YELLOW
        )

    def draw_volume(self, painter, df, rect):
        maximum = max(
            float(df["Volume"].max()),
            1
        )

        step = rect.width() / len(df)

        for i, (_, candle) in enumerate(df.iterrows()):
            volume = self.series_value(candle["Volume"])

            if volume is None:
                continue

            height = (
                volume / maximum
            ) * rect.height()

            x = rect.left() + (i + 0.5) * step

            color = (
                GREEN
                if candle["Close"] >= candle["Open"]
                else RED
            )

            painter.fillRect(
                QRectF(
                    x - step * 0.3,
                    rect.bottom() - height,
                    max(1.0, step * 0.6),
                    height
                ),
                color
            )

        self.draw_line_series(
            painter,
            df,
            "VOLUME_AVG20",
            rect,
            0,
            maximum,
            YELLOW
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.Antialiasing
        )

        painter.fillRect(
            self.rect(),
            BACKGROUND
        )

        df, start_index = self.visible_data()

        if df is None or df.empty:
            self.draw_text(
                painter,
                30,
                50,
                "Load a stock to display technical charts."
            )

            painter.end()
            return

        (
            price_rect,
            rsi_rect,
            macd_rect,
            volume_rect
        ) = self.panel_rectangles()

        panels = [
            (price_rect, "PRICE / MOVING AVERAGES"),
            (rsi_rect, "RSI (14)"),
            (macd_rect, "MACD (12, 26, 9)"),
            (volume_rect, "TRADING VOLUME")
        ]

        for rect, title in panels:
            self.draw_panel(
                painter,
                rect,
                title
            )

        for rect, method in [
            (price_rect, self.draw_price),
            (rsi_rect, self.draw_rsi),
            (macd_rect, self.draw_macd),
            (volume_rect, self.draw_volume)
        ]:
            painter.save()
            painter.setClipRect(rect)
            method(painter, df, rect)
            painter.restore()

        # ======================================
        # DATE LABELS
        # ======================================

        count = len(df)
        step = price_rect.width() / count

        for i in range(
            0,
            count,
            max(1, count // 7)
        ):
            date = df.index[i]

            x = price_rect.left() + (
                i + 0.5
            ) * step

            label = (
                date.strftime("%b %d '%y")
                if hasattr(date, "strftime")
                else str(date)[:10]
            )

            self.draw_text(
                painter,
                x - 25,
                volume_rect.bottom() + 20,
                label
            )

        # ======================================
        # HOVER CROSSHAIR
        # ======================================

        if self.hover_index is not None:
            local_index = (
                self.hover_index - start_index
            )

            if 0 <= local_index < count:
                x = price_rect.left() + (
                    local_index + 0.5
                ) * step

                painter.setPen(
                    QPen(
                        MUTED,
                        1,
                        Qt.DashLine
                    )
                )

                painter.drawLine(
                    QPointF(x, price_rect.top()),
                    QPointF(x, volume_rect.bottom())
                )

                candle = self.data.iloc[
                    self.hover_index
                ]

                date = self.data.index[
                    self.hover_index
                ]

                label = (
                    f"{str(date)[:10]}  "
                    f"O {candle['Open']:.2f}  "
                    f"H {candle['High']:.2f}  "
                    f"L {candle['Low']:.2f}  "
                    f"C {candle['Close']:.2f}"
                )

                self.draw_text(
                    painter,
                    price_rect.left(),
                    20,
                    label,
                    QColor("#F8FAFC")
                )

        painter.end()

    def mouseMoveEvent(self, event):
        if self.data is None or self.data.empty:
            return

        x = event.position().x()
        price_rect = self.panel_rectangles()[0]

        if self.drag_position is not None:
            delta = x - self.drag_position
            self.drag_position = x

            df, _ = self.visible_data()

            if df is not None and not df.empty:
                step = price_rect.width() / len(df)

                self.drag_remainder += (
                    delta / max(step, 0.001)
                )

                shift = int(self.drag_remainder)

                if shift:
                    self.end_index = max(
                        self.visible_count,
                        min(
                            len(self.data),
                            self.end_index - shift
                        )
                    )

                    self.drag_remainder -= shift
                    self.update()

            return

        df, start = self.visible_data()

        if df is None or df.empty:
            return

        if (
            price_rect.left()
            <= x
            <= price_rect.right()
        ):
            fraction = (
                (x - price_rect.left())
                / price_rect.width()
            )

            local_index = min(
                len(df) - 1,
                max(
                    0,
                    int(fraction * len(df))
                )
            )

            self.hover_index = (
                start + local_index
            )
        else:
            self.hover_index = None

        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = (
                event.position().x()
            )

            self.drag_remainder = 0

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        self.drag_remainder = 0

    def leaveEvent(self, event):
        self.hover_index = None
        self.update()

    def wheelEvent(self, event):
        if self.data is None or self.data.empty:
            return

        direction = event.angleDelta().y()

        if direction > 0:
            self.visible_count = max(
                15,
                int(self.visible_count * 0.85)
            )

        elif direction < 0:
            self.visible_count = min(
                len(self.data),
                max(
                    15,
                    int(self.visible_count * 1.15)
                )
            )

        self.end_index = max(
            self.visible_count,
            self.end_index
        )

        self.update()


class TechnicalMixin:

    def build_technical(self):
        page = QWidget()

        root = QVBoxLayout(page)
        root.setContentsMargins(25, 20, 25, 20)
        root.setSpacing(12)

        # ======================================
        # HEADER AND SEARCH
        # ======================================

        header = QHBoxLayout()

        title = QLabel("Technical Analysis")
        title.setObjectName("Title")

        header.addWidget(title)
        header.addStretch()

        self.technical_input = QLineEdit()

        self.technical_input.setPlaceholderText(
            "Enter ticker..."
        )

        self.technical_input.setFixedWidth(200)

        self.technical_input.returnPressed.connect(
            self.search_technical
        )

        header.addWidget(
            self.technical_input
        )

        self.technical_analyze = QPushButton(
            "Analyze"
        )

        self.technical_analyze.setObjectName(
            "Primary"
        )

        self.technical_analyze.clicked.connect(
            self.search_technical
        )

        header.addWidget(
            self.technical_analyze
        )

        root.addLayout(header)

        # ======================================
        # STOCK NAME / STATUS
        # ======================================

        self.technical_company = QLabel(
            "Select a stock to begin."
        )

        self.technical_company.setObjectName(
            "SectionTitle"
        )

        root.addWidget(
            self.technical_company
        )

        self.technical_status = QLabel(
            "Technical indicators use historical "
            "daily closing prices."
        )

        self.technical_status.setObjectName(
            "Muted"
        )

        root.addWidget(
            self.technical_status
        )

        # ======================================
        # PERIOD SELECTION
        # ======================================

        controls = QHBoxLayout()

        controls.addWidget(
            QLabel("Timeframe:")
        )

        self.technical_period = QComboBox()

        self.technical_period.addItems(
            list(PERIODS.keys())
        )

        self.technical_period.setCurrentText(
            "1Y"
        )

        self.technical_period.currentTextChanged.connect(
            self.technical_period_changed
        )

        controls.addWidget(
            self.technical_period
        )

        controls.addSpacing(20)

        # ======================================
        # INDICATOR TOGGLES
        # ======================================

        self.technical_sma20 = QCheckBox(
            "SMA 20"
        )

        self.technical_sma20.setChecked(True)

        self.technical_sma50 = QCheckBox(
            "SMA 50"
        )

        self.technical_sma50.setChecked(True)

        self.technical_sma200 = QCheckBox(
            "SMA 200"
        )

        self.technical_sma200.setChecked(False)

        for checkbox in (
            self.technical_sma20,
            self.technical_sma50,
            self.technical_sma200
        ):
            checkbox.stateChanged.connect(
                self.update_technical_overlays
            )

            controls.addWidget(checkbox)

        controls.addStretch()
        root.addLayout(controls)

        # ======================================
        # MAIN SCROLL AREA
        # ======================================

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(
            QFrame.NoFrame
        )

        content = QWidget()

        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(14)

        # ======================================
        # TECHNICAL CHART
        # ======================================

        self.technical_chart = TechnicalChart()

        content_layout.addWidget(
            self.technical_chart
        )

        # ======================================
        # TECHNICAL SUMMARY
        # ======================================

        summary_title = QLabel(
            "Technical Summary"
        )

        summary_title.setObjectName(
            "SectionTitle"
        )

        content_layout.addWidget(
            summary_title
        )

        summary_grid = QGridLayout()

        self.technical_values = {}

        metrics = [
            "Trend",
            "Momentum",
            "Volume",
            "Price",
            "SMA 20",
            "SMA 50",
            "SMA 200",
            "RSI",
            "MACD",
            "MACD Signal",
            "Volume Z"
        ]

        for i, name in enumerate(metrics):
            card = QFrame()
            card.setObjectName("Card")

            layout = QVBoxLayout(card)

            label = QLabel(name)
            label.setObjectName("Muted")

            value = QLabel("—")

            value.setStyleSheet(
                "font-size: 18px;"
                "font-weight: bold;"
            )

            layout.addWidget(label)
            layout.addWidget(value)

            summary_grid.addWidget(
                card,
                i // 4,
                i % 4
            )

            self.technical_values[name] = value

        content_layout.addLayout(
            summary_grid
        )

        # ======================================
        # INDICATOR INTERPRETATION
        # ======================================

        analysis_title = QLabel(
            "Indicator Interpretation"
        )

        analysis_title.setObjectName(
            "SectionTitle"
        )

        content_layout.addWidget(
            analysis_title
        )

        self.technical_explanation = QLabel(
            "Run an analysis to view the "
            "current technical conditions."
        )

        self.technical_explanation.setWordWrap(
            True
        )

        self.technical_explanation.setAlignment(
            Qt.AlignTop
        )

        self.technical_explanation.setStyleSheet(
            "background-color: #172235;"
            "border: 1px solid #293548;"
            "border-radius: 8px;"
            "padding: 16px;"
            "font-size: 13px;"
        )

        content_layout.addWidget(
            self.technical_explanation
        )

        # ======================================
        # NEW: WALL STREET ANALYST CONSENSUS
        # ======================================

        self.analyst_consensus = AnalystConsensus(
            self.threadpool
        )

        content_layout.addWidget(
            self.analyst_consensus
        )

        content_layout.addStretch()

        scroll.setWidget(content)

        root.addWidget(scroll, 1)

        self.pages.addWidget(page)

        # ======================================
        # WORKER STATE
        # ======================================

        self.technical_worker = None
        self.technical_data = None

        self.technical_requested_ticker = None
        self.technical_pending_ticker = None

    def search_technical(self):
        self.load_technical(
            self.technical_input.text()
        )

    def load_technical(self, ticker):
        ticker = ticker.strip().upper()

        if not ticker:
            return

        self.technical_input.setText(
            ticker
        )

        self.technical_requested_ticker = ticker

        if self.technical_worker is not None:
            self.technical_pending_ticker = ticker

            self.technical_status.setText(
                f"Waiting to load {ticker}..."
            )

            return

        self.start_technical_worker(
            ticker
        )

    def start_technical_worker(self, ticker):
        self.technical_status.setText(
            f"Loading technical data for {ticker}..."
        )

        self.technical_company.setText(
            f"Loading {ticker}..."
        )

        self.technical_analyze.setEnabled(
            False
        )

        worker = TechnicalWorker(
            ticker,
            self.technical_period.currentText()
        )

        self.technical_worker = worker

        worker.signals.finished.connect(
            lambda data, w=worker:
            self.technical_loaded(data, w)
        )

        worker.signals.error.connect(
            lambda error, w=worker:
            self.technical_failed(error, w)
        )

        self.threadpool.start(worker)

    def technical_loaded(self, data, worker):
        if (
            data["ticker"]
            != self.technical_requested_ticker
        ):
            self.finish_technical_request(worker)
            return

        self.technical_data = data

        ticker = data["ticker"]

        self.technical_company.setText(
            f"{ticker} — Technical Analysis"
        )

        history = data["history"]

        self.technical_chart.set_data(
            history,
            self.technical_period.currentText()
        )

        self.update_technical_overlays()

        summary = data["summary"]
        values = summary["values"]

        self.technical_values["Trend"].setText(
            summary["trend"]
        )

        self.technical_values["Momentum"].setText(
            summary["momentum"]
        )

        self.technical_values["Volume"].setText(
            summary["volume"]
        )

        mapping = {
            "Price": "price",
            "SMA 20": "sma20",
            "SMA 50": "sma50",
            "SMA 200": "sma200",
            "RSI": "rsi",
            "MACD": "macd",
            "MACD Signal": "signal",
            "Volume Z": "volume_z"
        }

        for label, key in mapping.items():
            self.technical_values[label].setText(
                display_number(
                    values.get(key)
                )
            )

        self.technical_explanation.setText(
            "\n\n".join(
                summary["details"]
            )
        )

        # ======================================
        # NEW: LOAD ANALYST CONSENSUS
        # ======================================

        self.analyst_consensus.load_ticker(
            ticker
        )

        self.technical_status.setText(
            f"{ticker} loaded · "
            f"{len(history)} trading sessions available · "
            "mouse wheel to zoom · drag to pan"
        )

        self.finish_technical_request(worker)

    def technical_failed(self, error, worker):
        if (
            worker.ticker
            == self.technical_requested_ticker
        ):
            self.technical_company.setText(
                "Unable to load technical analysis"
            )

            self.technical_status.setText(
                error
            )

        self.finish_technical_request(worker)

    def finish_technical_request(self, worker):
        if self.technical_worker is worker:
            self.technical_worker = None

        self.technical_analyze.setEnabled(
            True
        )

        pending = self.technical_pending_ticker
        self.technical_pending_ticker = None

        if pending and pending != worker.ticker:
            self.start_technical_worker(
                pending
            )

    def technical_period_changed(self, period):
        if self.technical_data is not None:
            self.technical_chart.set_period(
                period
            )

    def update_technical_overlays(self):
        self.technical_chart.set_overlays(
            self.technical_sma20.isChecked(),
            self.technical_sma50.isChecked(),
            self.technical_sma200.isChecked()
        )
