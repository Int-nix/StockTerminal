from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath


class StockChart(QWidget):

    def __init__(self):
        super().__init__()

        self.chart_type = "Candlestick"
        self.history = None
        self.ticker = ""

        # Number of candles currently visible.
        self.visible_count = 90

        # Number of candles hidden to the right.
        self.offset = 0

        self.hover = None
        self.intraday = False

        # Mouse dragging state.
        self.drag_x = None
        self.drag_offset = 0

        self.setMinimumHeight(400)
        self.setMouseTracking(True)

    def set_chart_type(self, chart_type):
        if chart_type in ("Candlestick", "Line"):
            self.chart_type = chart_type
            self.update()

    # ========================================================
    # LOAD CHART DATA
    # ========================================================

    def set_data(self, ticker, history):

        self.ticker = ticker
        self.history = history.copy()

        self.intraday = bool(
            len(history)
            and (
                history.index[0].hour != 0
                or history.index[0].minute != 0
            )
        )

        # IMPORTANT:
        # Automatically display the ENTIRE selected period.
        #
        # 1d  -> all intraday candles
        # 5d  -> all five days
        # 1y  -> all yearly candles
        # 5y  -> all five years
        # max -> all available candles

        self.visible_count = len(self.history)

        # Reset horizontal position to the latest candle.
        self.offset = 0

        # Clear previous hover/drag state.
        self.hover = None
        self.drag_x = None
        self.drag_offset = 0

        self.update()

    # ========================================================
    # MOUSE WHEEL ZOOM
    # ========================================================

    def wheelEvent(self, event):

        if self.history is None or self.history.empty:
            return

        total = len(self.history)

        if total <= 1:
            return

        old_count = min(
            self.visible_count,
            total
        )

        # Mouse wheel direction.
        delta = event.angleDelta().y()

        if delta == 0:
            return

        # Zoom by approximately 20% per wheel step.
        steps = abs(delta) / 120

        factor = 1.2 ** steps

        if delta > 0:
            # Zoom in.
            new_count = int(
                old_count / factor
            )

        else:
            # Zoom out.
            new_count = int(
                old_count * factor
            )

        minimum = min(15, total)

        new_count = max(
            minimum,
            min(total, new_count)
        )

        if new_count == old_count:
            return

        # ----------------------------------------------------
        # KEEP MOUSE POSITION AS ZOOM ANCHOR
        # ----------------------------------------------------

        left_margin = 75
        right_margin = 24

        plot_width = max(
            1,
            self.width()
            - left_margin
            - right_margin
        )

        mouse_x = event.position().x()

        relative_x = (
            mouse_x - left_margin
        ) / plot_width

        relative_x = max(
            0.0,
            min(1.0, relative_x)
        )

        # Current visible range.
        old_end = total - self.offset

        old_start = max(
            0,
            old_end - old_count
        )

        # Candle index under the mouse.
        anchor_index = (
            old_start
            + relative_x * old_count
        )

        # Calculate new range around anchor.
        new_start = round(
            anchor_index
            - relative_x * new_count
        )

        new_start = max(
            0,
            min(
                total - new_count,
                new_start
            )
        )

        new_end = (
            new_start + new_count
        )

        self.visible_count = new_count

        self.offset = (
            total - new_end
        )

        self.update()

    # ========================================================
    # MOUSE LEAVES CHART
    # ========================================================

    def leaveEvent(self, event):

        self.hover = None

        self.update()

    # ========================================================
    # START DRAGGING
    # ========================================================

    def mousePressEvent(self, event):

        if event.button() == Qt.LeftButton:

            self.drag_x = (
                event.position().x()
            )

            self.drag_offset = (
                self.offset
            )

    # ========================================================
    # STOP DRAGGING
    # ========================================================

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.LeftButton:
            self.drag_x = None

    # ========================================================
    # MOUSE MOVEMENT
    # ========================================================

    def mouseMoveEvent(self, event):

        if (
            self.drag_x is not None
            and self.history is not None
            and not self.history.empty
        ):

            total = len(self.history)

            plot_width = max(
                1,
                self.width() - 99
            )

            visible = max(
                1,
                min(
                    self.visible_count,
                    total
                )
            )

            spacing = (
                plot_width / visible
            )

            shift = round(
                (
                    event.position().x()
                    - self.drag_x
                ) / spacing
            )

            self.offset = max(
                0,
                min(
                    total - visible,
                    self.drag_offset + shift
                )
            )

        self.hover = (
            event.position()
        )

        self.update()

    # ========================================================
    # PAINT CHART
    # ========================================================

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(
            QPainter.Antialiasing
        )

        p.fillRect(
            self.rect(),
            QColor("#0B1220")
        )

        # ----------------------------------------------------
        # NO DATA
        # ----------------------------------------------------

        if self.history is None or self.history.empty:

            p.setPen(
                QColor("#94A3B8")
            )

            p.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Waiting for historical prices..."
            )

            p.end()
            return

        # ----------------------------------------------------
        # VISIBLE DATA RANGE
        # ----------------------------------------------------

        total = len(self.history)

        count = min(
            self.visible_count,
            total
        )

        end = max(
            count,
            total - self.offset
        )

        start = max(
            0,
            end - count
        )

        data = self.history.iloc[
            start:end
        ]

        if data.empty:
            p.end()
            return

        # ----------------------------------------------------
        # CHART DIMENSIONS
        # ----------------------------------------------------

        left = 75
        right = 24
        top = 48
        bottom = 42

        width = max(
            1,
            self.width() - left - right
        )

        height = max(
            1,
            self.height() - top - bottom
        )

        price_height = (
            height * 0.76
        )

        volume_top = (
            top + price_height + 12
        )

        volume_height = max(
            1,
            height - price_height - 12
        )

        # ----------------------------------------------------
        # PRICE RANGE
        # ----------------------------------------------------

        high = float(
            data["High"].max()
        )

        low = float(
            data["Low"].min()
        )

        pad = max(
            (high - low) * 0.06,
            abs(high) * 0.001,
            0.01
        )

        high += pad
        low -= pad

        span = high - low

        spacing = (
            width / len(data)
        )

        candle_width = max(
            1.0,
            min(
                16.0,
                spacing * 0.68
            )
        )

        def y_price(value):

            return (
                top
                + (
                    high - float(value)
                ) / span
                * price_height
            )

        # ----------------------------------------------------
        # HORIZONTAL PRICE GRID
        # ----------------------------------------------------

        p.setPen(
            QPen(
                QColor("#293548"),
                1
            )
        )

        for i in range(6):

            y = (
                top
                + i * price_height / 5
            )

            p.drawLine(
                QPointF(left, y),
                QPointF(left + width, y)
            )

            p.setPen(
                QColor("#94A3B8")
            )

            p.drawText(
                6,
                int(y + 4),
                f"{high - i * span / 5:,.2f}"
            )

            p.setPen(
                QPen(
                    QColor("#293548"),
                    1
                )
            )

        # ----------------------------------------------------
        # CANDLESTICKS AND VOLUME
        # ----------------------------------------------------

        max_volume = max(
            float(
                data["Volume"].max()
            ),
            1
        )

        if self.chart_type == "Line":
            # Draw close-price line and retain the original volume bars.
            path = QPainterPath()
            closes = data["Close"].tolist()
            for i, closing in enumerate(closes):
                x = left + (i + 0.5) * spacing
                y = y_price(closing)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.setPen(QPen(QColor("#22C55E"), 2.2))
            p.drawPath(path)

        for i, (date, row) in enumerate(data.iterrows()):
            x = left + (i + 0.5) * spacing
            opening = float(row["Open"])
            closing = float(row["Close"])
            color = QColor("#22C55E" if closing >= opening else "#EF4444")
            if self.chart_type != "Line":
                p.setPen(QPen(color, 1))
                p.drawLine(QPointF(x, y_price(row["High"])),
                           QPointF(x, y_price(row["Low"])))
                body_top = min(y_price(opening), y_price(closing))
                body_height = max(1.2, abs(y_price(opening) - y_price(closing)))
                p.fillRect(QRectF(x - candle_width / 2, body_top,
                                  candle_width, body_height), color)
            volume_height_bar = float(row["Volume"]) / max_volume * volume_height
            p.fillRect(QRectF(x - candle_width / 2,
                              volume_top + volume_height - volume_height_bar,
                              candle_width, volume_height_bar), color)

        # ----------------------------------------------------
        # DATE LABELS
        # ----------------------------------------------------

        p.setPen(
            QColor("#94A3B8")
        )

        for i in range(5):

            idx = round(
                i * (len(data) - 1) / 4
            )

            date = (
                data.index[idx]
            )

            x = (
                left
                + (idx + 0.5) * spacing
            )

            label = (
                date.strftime(
                    "%b %d %H:%M"
                )
                if self.intraday
                else date.strftime(
                    "%b %d, %Y"
                )
            )

            p.drawText(
                int(x - 40),
                self.height() - 12,
                label
            )

        # ----------------------------------------------------
        # CHART TITLE
        # ----------------------------------------------------

        p.setPen(
            QColor("#F8FAFC")
        )

        p.drawText(
            20,
            26,
            f"{self.ticker}  |  "
            f"Historical {self.chart_type} + Volume"
        )

        p.setPen(
            QColor("#94A3B8")
        )

        p.drawText(
            self.width() - 190,
            26,
            "Wheel: zoom  |  Drag: pan"
        )

        # ----------------------------------------------------
        # HOVER INFORMATION
        # ----------------------------------------------------

        if (
            self.hover is not None
            and left <= self.hover.x()
            <= left + width
        ):

            idx = min(
                len(data) - 1,
                max(
                    0,
                    int(
                        (
                            self.hover.x()
                            - left
                        ) / spacing
                    )
                )
            )

            row = data.iloc[idx]

            date = (
                data.index[idx]
            )

            x = (
                left
                + (idx + 0.5) * spacing
            )

            p.setPen(
                QPen(
                    QColor("#64748B"),
                    1,
                    Qt.DashLine
                )
            )

            p.drawLine(
                QPointF(x, top),
                QPointF(
                    x,
                    volume_top + volume_height
                )
            )

            timestamp = (
                date.strftime(
                    "%Y-%m-%d %H:%M"
                )
                if self.intraday
                else date.strftime(
                    "%Y-%m-%d"
                )
            )

            tooltip = (
                f"{timestamp}   "
                f"O {row['Open']:.2f}   "
                f"H {row['High']:.2f}   "
                f"L {row['Low']:.2f}   "
                f"C {row['Close']:.2f}   "
                f"Vol {int(row['Volume']):,}"
            )

            p.setPen(
                QColor("#E2E8F0")
            )

            p.drawText(
                left + 5,
                43,
                tooltip
            )

        p.end()
