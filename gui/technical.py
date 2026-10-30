"""Technical Analysis page and interactive technical chart."""

import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox,
    QFrame, QGridLayout, QScrollArea, QSizePolicy
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
    """Interactive multi-panel chart with axes, legends and a candle inspector."""

    def __init__(self):
        super().__init__()
        self.data = None
        self.visible_count = 100
        self.end_index = 0
        self.show_sma20 = True
        self.show_sma50 = True
        self.show_sma200 = False
        self.hover_index = None
        self.hover_position = None
        self.show_rsi = True
        self.show_macd = True
        self.show_volume = True
        self.show_grid = True
        self.show_crosshair = True
        self.drag_position = None
        self.drag_remainder = 0
        self.setMinimumHeight(780)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #172235;")

    @staticmethod
    def numeric(value):
        try:
            value = float(value)
            return value if math.isfinite(value) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def compact(value):
        value = TechnicalChart.numeric(value)
        if value is None:
            return "—"
        for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(value) >= threshold:
                return f"{value / threshold:,.2f}{suffix}"
        return f"{value:,.0f}"

    @staticmethod
    def fmt(value, decimals=2):
        value = TechnicalChart.numeric(value)
        return f"{value:,.{decimals}f}" if value is not None else "—"

    def set_data(self, data, period="1Y"):
        self.data = data
        if data is None or data.empty:
            self.end_index = 0
            self.hover_index = None
        else:
            counts = {"1M": 22, "3M": 65, "6M": 130, "1Y": 252, "2Y": 504, "5Y": 1260}
            self.visible_count = min(counts.get(period, 252), len(data))
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
        end = max(1, min(self.end_index, len(self.data)))
        start = max(0, end - self.visible_count)
        return self.data.iloc[start:end], start

    def panel_rectangles(self):
        """Allocate deliberate gaps between chart panels and their headings."""
        left, right, top = 24, 104, 42
        width = max(50, self.width() - left - right)
        bottom_margin = 42
        gap = 34  # clear separation for axis labels and next-panel titles
        weights = [("price", 4.6)]
        if self.show_rsi:
            weights.append(("rsi", 1.4))
        if self.show_macd:
            weights.append(("macd", 1.65))
        if self.show_volume:
            weights.append(("volume", 1.5))
        usable = max(360, self.height() - top - bottom_margin - gap * (len(weights) - 1))
        total = sum(weight for _, weight in weights)
        rects = {}
        y = top
        for name, weight in weights:
            h = usable * weight / total
            rects[name] = QRectF(left, y, width, h)
            y += h + gap
        return rects

    @staticmethod
    def map_y(value, minimum, maximum, rect):
        return rect.bottom() - (value - minimum) / max(maximum - minimum, 1e-12) * rect.height()

    def value_range(self, df, columns, include_zero=False, padding=0.08):
        values = []
        for column in columns:
            if column not in df:
                continue
            values.extend(v for raw in df[column] if (v := self.numeric(raw)) is not None)
        if include_zero:
            values.append(0.0)
        if not values:
            return (0.0, 1.0)
        lo, hi = min(values), max(values)
        margin = max((hi - lo) * padding, abs(hi) * 0.002, 0.001)
        return lo - margin, hi + margin

    def label(self, painter, x, y, text, color=MUTED):
        painter.setPen(color)
        painter.drawText(int(x), int(y), str(text))

    def draw_grid(self, painter, rect, minimum, maximum, kind="number", ticks=5):
        painter.save()
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        for i in range(ticks + 1):
            value = minimum + (maximum - minimum) * i / ticks
            y = self.map_y(value, minimum, maximum, rect)
            painter.setPen(QPen(BORDER, 1, Qt.DashLine))
            if self.show_grid:
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            if kind == "volume":
                label = self.compact(value)
            elif kind == "rsi":
                label = f"{value:.0f}"
            elif kind == "macd":
                label = f"{value:+.3f}"
            else:
                label = f"{value:,.2f}"
            self.label(painter, rect.right() + 8, y + 4, label)
        painter.restore()

    def line_series(self, painter, df, column, rect, lo, hi, color, width=1.6):
        if column not in df or len(df) < 2:
            return
        step = rect.width() / len(df)
        painter.setPen(QPen(color, width))
        previous = None
        for i, raw in enumerate(df[column]):
            value = self.numeric(raw)
            if value is None:
                previous = None
                continue
            point = QPointF(rect.left() + (i + .5) * step,
                            self.map_y(value, lo, hi, rect))
            if previous is not None:
                painter.drawLine(previous, point)
            previous = point

    def panel_title(self, painter, rect, title, legend):
        self.label(painter, rect.left() + 5, rect.top() - 6, title, QColor("#F8FAFC"))
        # Put the legend on the same line, but keep it inside the plot's width.
        x = rect.left() + 170
        for text, color in legend:
            width = painter.fontMetrics().horizontalAdvance(text) + 17
            if x + width > rect.right():
                break
            painter.setPen(QPen(color, 3))
            painter.drawLine(QPointF(x, rect.top() - 10), QPointF(x + 10, rect.top() - 10))
            self.label(painter, x + 14, rect.top() - 6, text, color)
            x += width + 10

    def latest(self, df, column):
        if column not in df:
            return None
        for raw in reversed(df[column].tolist()):
            value = self.numeric(raw)
            if value is not None:
                return value
        return None

    def draw_price(self, painter, df, rect):
        overlays = [("SMA20", self.show_sma20, YELLOW),
                    ("SMA50", self.show_sma50, BLUE),
                    ("SMA200", self.show_sma200, PURPLE)]
        columns = ["Low", "High"] + [name for name, enabled, _ in overlays if enabled]
        lo, hi = self.value_range(df, columns)
        self.draw_grid(painter, rect, lo, hi)
        painter.save()
        painter.setClipRect(rect)
        step = rect.width() / len(df)
        candle_width = max(1.0, min(12.0, step * .65))
        for i, (_, candle) in enumerate(df.iterrows()):
            values = [self.numeric(candle.get(k)) for k in ("Open", "Close", "High", "Low")]
            if any(v is None for v in values):
                continue
            opening, closing, high, low = values
            color = GREEN if closing >= opening else RED
            x = rect.left() + (i + .5) * step
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPointF(x, self.map_y(high, lo, hi, rect)),
                             QPointF(x, self.map_y(low, lo, hi, rect)))
            a, b = self.map_y(opening, lo, hi, rect), self.map_y(closing, lo, hi, rect)
            painter.fillRect(QRectF(x - candle_width / 2, min(a, b),
                                    candle_width, max(1.0, abs(a - b))), color)
        for column, enabled, color in overlays:
            if enabled:
                self.line_series(painter, df, column, rect, lo, hi, color, 1.7)
        painter.restore()
        last = self.latest(df, "Close")
        legend = [("Close " + self.fmt(last), QColor("#F8FAFC"))]
        legend += [(name + " " + self.fmt(self.latest(df, name)), color)
                   for name, enabled, color in overlays if enabled]
        self.panel_title(painter, rect, "PRICE / SMA", legend)
        if last is not None and lo <= last <= hi:
            y = self.map_y(last, lo, hi, rect)
            painter.fillRect(QRectF(rect.right() + 4, y - 10, 86, 19), BLUE)
            self.label(painter, rect.right() + 8, y + 4, self.fmt(last), QColor("#FFFFFF"))

    def draw_rsi(self, painter, df, rect):
        self.draw_grid(painter, rect, 0, 100, "rsi", 5)
        painter.save()
        painter.setClipRect(rect)
        for level in (30, 70):
            y = self.map_y(level, 0, 100, rect)
            painter.setPen(QPen(YELLOW, 1, Qt.DashLine))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        self.line_series(painter, df, "RSI", rect, 0, 100, PURPLE, 1.8)
        painter.restore()
        self.panel_title(painter, rect, "RSI (14)",
                         [("RSI " + self.fmt(self.latest(df, "RSI")), PURPLE)])

    def draw_macd(self, painter, df, rect):
        lo, hi = self.value_range(df, ("MACD", "MACD_SIGNAL", "MACD_HIST"), True, .1)
        self.draw_grid(painter, rect, lo, hi, "macd")
        painter.save()
        painter.setClipRect(rect)
        step = rect.width() / len(df)
        zero = self.map_y(0, lo, hi, rect)
        if "MACD_HIST" in df:
            for i, raw in enumerate(df["MACD_HIST"]):
                value = self.numeric(raw)
                if value is None:
                    continue
                y = self.map_y(value, lo, hi, rect)
                x = rect.left() + (i + .5) * step
                painter.fillRect(QRectF(x - step * .3, min(y, zero),
                                        max(1., step * .6), max(1., abs(y - zero))),
                                 GREEN if value >= 0 else RED)
        self.line_series(painter, df, "MACD", rect, lo, hi, CYAN)
        self.line_series(painter, df, "MACD_SIGNAL", rect, lo, hi, YELLOW)
        painter.restore()
        legend = [("MACD " + self.fmt(self.latest(df, "MACD"), 3), CYAN),
                  ("Signal " + self.fmt(self.latest(df, "MACD_SIGNAL"), 3), YELLOW),
                  ("Hist " + self.fmt(self.latest(df, "MACD_HIST"), 3), GREEN)]
        self.panel_title(painter, rect, "MACD (12,26,9)", legend)

    def draw_volume(self, painter, df, rect):
        hi = max(1.0, self.value_range(df, ("Volume", "VOLUME_AVG20"), True)[1])
        self.draw_grid(painter, rect, 0, hi, "volume", 4)
        painter.save()
        painter.setClipRect(rect)
        step = rect.width() / len(df)
        for i, (_, candle) in enumerate(df.iterrows()):
            volume = self.numeric(candle.get("Volume"))
            if volume is None:
                continue
            x = rect.left() + (i + .5) * step
            y = self.map_y(volume, 0, hi, rect)
            op, cl = self.numeric(candle.get("Open")), self.numeric(candle.get("Close"))
            color = GREEN if op is not None and cl is not None and cl >= op else RED
            painter.fillRect(QRectF(x - step * .3, y, max(1., step * .6),
                                    max(1., rect.bottom() - y)), color)
        self.line_series(painter, df, "VOLUME_AVG20", rect, 0, hi, YELLOW)
        painter.restore()
        legend = [("Volume " + self.compact(self.latest(df, "Volume")), CYAN),
                  ("Avg20 " + self.compact(self.latest(df, "VOLUME_AVG20")), YELLOW)]
        self.panel_title(painter, rect, "VOLUME", legend)

    def draw_inspector(self, painter, df, start, rects):
        if self.hover_index is None or not self.show_crosshair:
            return
        local = self.hover_index - start
        if not 0 <= local < len(df):
            return
        first = rects["price"]
        last = list(rects.values())[-1]
        x = first.left() + (local + .5) * first.width() / len(df)
        painter.setPen(QPen(MUTED, 1, Qt.DashLine))
        painter.drawLine(QPointF(x, first.top()), QPointF(x, last.bottom()))
        row = self.data.iloc[self.hover_index]
        date = self.data.index[self.hover_index]
        date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10]
        lines = [
            date_str,
            "Open   " + self.fmt(row.get("Open")) + "     High  " + self.fmt(row.get("High")),
            "Low    " + self.fmt(row.get("Low")) + "     Close " + self.fmt(row.get("Close")),
            "Volume " + self.compact(row.get("Volume")) + "   Avg20 " + self.compact(row.get("VOLUME_AVG20")),
            "SMA20  " + self.fmt(row.get("SMA20")) + "   SMA50 " + self.fmt(row.get("SMA50")),
            "SMA200 " + self.fmt(row.get("SMA200")) + "   RSI   " + self.fmt(row.get("RSI")),
            "MACD   " + self.fmt(row.get("MACD"), 3) + "   Signal " + self.fmt(row.get("MACD_SIGNAL"), 3),
            "Hist   " + self.fmt(row.get("MACD_HIST"), 3),
        ]
        w, h = 300, 180
        box_x = first.right() - w - 12 if x < first.center().x() else first.left() + 12
        box_y = first.top() + 12
        box = QRectF(box_x, box_y, w, h)
        painter.fillRect(box, QColor("#101827"))
        painter.setPen(QPen(BLUE, 1))
        painter.drawRect(box)
        for i, line in enumerate(lines):
            self.label(painter, box_x + 12, box_y + 21 + i * 21, line,
                       QColor("#F8FAFC") if i == 0 else MUTED)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), BACKGROUND)
        df, start = self.visible_data()
        if df is None or df.empty:
            self.label(painter, 30, 50, "Load a stock to display technical charts.")
            painter.end()
            return
        rects = self.panel_rectangles()
        methods = {"price": self.draw_price, "rsi": self.draw_rsi,
                   "macd": self.draw_macd, "volume": self.draw_volume}
        for name, rect in rects.items():
            painter.setPen(QPen(BORDER, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            methods[name](painter, df, rect)
        count = len(df)
        last = list(rects.values())[-1]
        price = rects["price"]
        for i in range(0, count, max(1, count // 7)):
            date = df.index[i]
            label = date.strftime("%b %d '%y") if hasattr(date, "strftime") else str(date)[:10]
            x = price.left() + (i + .5) * price.width() / count
            self.label(painter, x - 28, last.bottom() + 22, label)
        self.draw_inspector(painter, df, start, rects)
        painter.end()

    def mouseMoveEvent(self, event):
        if self.data is None or self.data.empty:
            return
        x = event.position().x()
        rect = self.panel_rectangles()["price"]
        if self.drag_position is not None:
            delta = x - self.drag_position
            self.drag_position = x
            df, _ = self.visible_data()
            if df is not None and not df.empty:
                step = rect.width() / len(df)
                self.drag_remainder += delta / max(step, .001)
                shift = int(self.drag_remainder)
                if shift:
                    self.end_index = max(self.visible_count,
                                         min(len(self.data), self.end_index - shift))
                    self.drag_remainder -= shift
                    self.update()
            return
        df, start = self.visible_data()
        if df is not None and not df.empty and rect.left() <= x <= rect.right():
            index = int((x - rect.left()) / rect.width() * len(df))
            self.hover_index = start + max(0, min(len(df) - 1, index))
        else:
            self.hover_index = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.position().x()
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
            self.visible_count = max(15, int(self.visible_count * .85))
        elif direction < 0:
            self.visible_count = min(len(self.data), max(15, int(self.visible_count * 1.15)))
        self.end_index = max(self.visible_count, self.end_index)
        self.update()


class TechnicalMixin:

    def build_technical(self):
        """Research-terminal layout: compact header, chart workspace and data rail."""
        page = QWidget()
        page.setObjectName("TechnicalResearchPage")
        page.setStyleSheet("""
            #TechnicalResearchPage { background: #0b1220; color: #e5edf9; }
            QFrame#TechPanel { background: #131f31; border: 1px solid #293a52;
                               border-radius: 8px; }
            QLabel#TechCaption { color: #91a4c0; font-size: 11px; }
            QLabel#TechBig { color: #f4f8ff; font-size: 24px; font-weight: 700; }
            QLabel#TechSection { color: #f4f8ff; font-size: 13px; font-weight: 700; }
            QCheckBox { color: #dbe7fa; spacing: 5px; }
            QScrollArea { border: none; background: transparent; }
        """)
        root = QVBoxLayout(page)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Search / title
        top = QHBoxLayout()
        title = QLabel("Technical Analysis")
        title.setObjectName("Title")
        top.addWidget(title)
        top.addStretch()
        self.technical_input = QLineEdit()
        self.technical_input.setPlaceholderText("Ticker (e.g. AAPL)")
        self.technical_input.setFixedWidth(170)
        self.technical_input.returnPressed.connect(self.search_technical)
        top.addWidget(self.technical_input)
        self.technical_analyze = QPushButton("Analyze")
        self.technical_analyze.setObjectName("Primary")
        self.technical_analyze.clicked.connect(self.search_technical)
        top.addWidget(self.technical_analyze)
        root.addLayout(top)

        # Stock snapshot: separate metric tiles with clear visual hierarchy.
        snapshot = QFrame()
        snapshot.setObjectName("TechPanel")
        snapshot_layout = QHBoxLayout(snapshot)
        snapshot_layout.setContentsMargins(14, 12, 14, 12)
        snapshot_layout.setSpacing(10)

        identity = QFrame()
        identity.setObjectName("TechIdentity")
        identity.setStyleSheet("""
            QFrame#TechIdentity { background: #101b2d; border: 1px solid #30445f;
                                  border-radius: 9px; }
            QFrame#TechIdentity QLabel { border: none; background: transparent; }
        """)
        name_col = QVBoxLayout(identity)
        name_col.setContentsMargins(15, 11, 15, 11)
        name_col.setSpacing(5)
        self.technical_company = QLabel("Select a stock")
        self.technical_company.setObjectName("TechCaption")
        self.technical_company.setStyleSheet(
            "font-size: 12px; color: #a5b8d4; font-weight: 600;")
        self.technical_price = QLabel("—")
        self.technical_price.setObjectName("TechBig")
        self.technical_price.setStyleSheet(
            "font-size: 28px; color: #f8fafc; font-weight: 800;")
        self.technical_change = QLabel("Load a ticker to begin")
        self.technical_change.setObjectName("TechCaption")
        name_col.addWidget(self.technical_company)
        name_col.addWidget(self.technical_price)
        name_col.addWidget(self.technical_change)
        snapshot_layout.addWidget(identity, 3)

        self.technical_snapshot = {}
        for label in ("Open", "High", "Low", "Prev Close", "Volume", "Avg Volume"):
            tile = QFrame()
            tile.setObjectName("TechMetric")
            tile.setStyleSheet("""
                QFrame#TechMetric { background: #17263b; border: 1px solid #2a3b53;
                                    border-radius: 9px; }
                QFrame#TechMetric QLabel { border: none; background: transparent; }
            """)
            col = QVBoxLayout(tile)
            col.setContentsMargins(11, 11, 11, 11)
            col.setSpacing(9)
            caption = QLabel(label.upper())
            caption.setStyleSheet(
                "color: #93a9c8; font-size: 10px; font-weight: 700;")
            value = QLabel("—")
            value.setStyleSheet(
                "color: #f1f6ff; font-size: 15px; font-weight: 750;")
            value.setMinimumWidth(68)
            col.addWidget(caption)
            col.addWidget(value)
            col.addStretch()
            snapshot_layout.addWidget(tile, 1)
            self.technical_snapshot[label] = value
        root.addWidget(snapshot)

        # Single compact control bar
        controls_frame = QFrame()
        controls_frame.setObjectName("TechPanel")
        controls = QHBoxLayout(controls_frame)
        controls.setContentsMargins(12, 7, 12, 7)
        controls.setSpacing(9)
        controls.addWidget(QLabel("Timeframe"))
        self.technical_period = QComboBox()
        self.technical_period.addItems(list(PERIODS.keys()))
        self.technical_period.setCurrentText("1Y")
        self.technical_period.currentTextChanged.connect(self.technical_period_changed)
        controls.addWidget(self.technical_period)
        controls.addSpacing(12)
        self.technical_sma20 = QCheckBox("SMA 20")
        self.technical_sma50 = QCheckBox("SMA 50")
        self.technical_sma200 = QCheckBox("SMA 200")
        self.technical_sma20.setChecked(True)
        self.technical_sma50.setChecked(True)
        for checkbox in (self.technical_sma20, self.technical_sma50,
                         self.technical_sma200):
            checkbox.stateChanged.connect(self.update_technical_overlays)
            controls.addWidget(checkbox)
        controls.addSpacing(12)
        self.technical_rsi_toggle = QCheckBox("RSI")
        self.technical_macd_toggle = QCheckBox("MACD")
        self.technical_volume_toggle = QCheckBox("Volume")
        for toggle in (self.technical_rsi_toggle, self.technical_macd_toggle,
                       self.technical_volume_toggle):
            toggle.setChecked(True)
            toggle.stateChanged.connect(self.update_technical_panels)
            controls.addWidget(toggle)
        controls.addStretch()
        root.addWidget(controls_frame)

        # Charts take the remaining width; right-hand rail keeps readings visible.
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        chart_frame = QFrame()
        chart_frame.setObjectName("TechPanel")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(8, 10, 8, 8)
        self.technical_chart = TechnicalChart()
        self.technical_chart.setMinimumHeight(760)
        self.technical_chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_layout.addWidget(self.technical_chart)
        workspace.addWidget(chart_frame, 1)

        rail = QWidget()
        rail.setFixedWidth(236)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(10)

        indicators = QFrame()
        indicators.setObjectName("TechPanel")
        ind_layout = QVBoxLayout(indicators)
        ind_layout.setSpacing(7)
        heading = QLabel("LATEST INDICATORS")
        heading.setObjectName("TechSection")
        ind_layout.addWidget(heading)
        self.technical_values = {}
        indicator_colors = {
            "Price": "#f8fafc", "SMA 20": "#facc15",
            "SMA 50": "#3b82f6", "SMA 200": "#a78bfa",
            "RSI": "#a78bfa", "MACD": "#22d3ee",
            "MACD Signal": "#facc15", "MACD Hist": "#22c55e",
            "Volume": "#e2e8f0", "Avg Volume": "#facc15",
            "Volume Z": "#e2e8f0",
        }
        for label in ("Price", "SMA 20", "SMA 50", "SMA 200", "RSI",
                      "MACD", "MACD Signal", "MACD Hist", "Volume",
                      "Avg Volume", "Volume Z"):
            row = QHBoxLayout()
            key = QLabel(label)
            key.setObjectName("TechCaption")
            value = QLabel("—")
            value.setStyleSheet("font-weight: 700; color: %s;" %
                                indicator_colors.get(label, "#e2e8f0"))
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(key)
            row.addStretch()
            row.addWidget(value)
            ind_layout.addLayout(row)
            self.technical_values[label] = value
        rail_layout.addWidget(indicators)

        status_panel = QFrame()
        status_panel.setObjectName("TechPanel")
        status_layout = QVBoxLayout(status_panel)
        heading = QLabel("MARKET CONDITIONS")
        heading.setObjectName("TechSection")
        status_layout.addWidget(heading)
        for name in ("Trend", "Momentum", "Volume Status"):
            row = QHBoxLayout()
            label = QLabel(name)
            label.setObjectName("TechCaption")
            value = QLabel("—")
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(label)
            row.addStretch()
            row.addWidget(value)
            status_layout.addLayout(row)
            self.technical_values[name] = value
        rail_layout.addWidget(status_panel)

        view_panel = QFrame()
        view_panel.setObjectName("TechPanel")
        view_layout = QVBoxLayout(view_panel)
        label = QLabel("CHART CONTROLS")
        label.setObjectName("TechSection")
        view_layout.addWidget(label)
        self.technical_grid_toggle = QCheckBox("Show grid")
        self.technical_grid_toggle.setChecked(True)
        self.technical_grid_toggle.stateChanged.connect(self.update_technical_panels)
        view_layout.addWidget(self.technical_grid_toggle)
        self.technical_crosshair_toggle = QCheckBox("Crosshair / inspector")
        self.technical_crosshair_toggle.setChecked(True)
        self.technical_crosshair_toggle.stateChanged.connect(self.update_technical_panels)
        view_layout.addWidget(self.technical_crosshair_toggle)
        reset = QPushButton("Reset chart view")
        reset.clicked.connect(self.reset_technical_view)
        view_layout.addWidget(reset)
        rail_layout.addWidget(view_panel)
        rail_layout.addStretch()
        workspace.addWidget(rail)
        root.addLayout(workspace, 1)

        self.technical_status = QLabel(
            "Mouse wheel: zoom   •   Drag: pan   •   Hover: inspect historical values"
        )
        self.technical_status.setObjectName("TechCaption")
        root.addWidget(self.technical_status)

        # Retain interpretation and analyst consensus, below the chart.
        details = QFrame()
        details.setObjectName("TechPanel")
        details_layout = QVBoxLayout(details)
        interpretation_label = QLabel("INDICATOR INTERPRETATION")
        interpretation_label.setObjectName("TechSection")
        details_layout.addWidget(interpretation_label)
        self.technical_explanation = QLabel(
            "Run an analysis to view current technical conditions."
        )
        self.technical_explanation.setWordWrap(True)
        self.technical_explanation.setObjectName("TechCaption")
        details_layout.addWidget(self.technical_explanation)
        root.addWidget(details)

        self.analyst_consensus = AnalystConsensus(self.threadpool)
        root.addWidget(self.analyst_consensus)

        # Scroll the page vertically on smaller screens while retaining full chart width.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)
        self.pages.addWidget(wrapper)

        self.technical_worker = None
        self.technical_data = None
        self.technical_requested_ticker = None
        self.technical_pending_ticker = None

    def update_technical_panels(self):
        if not hasattr(self, "technical_chart"):
            return
        chart = self.technical_chart
        chart.show_rsi = self.technical_rsi_toggle.isChecked()
        chart.show_macd = self.technical_macd_toggle.isChecked()
        chart.show_volume = self.technical_volume_toggle.isChecked()
        chart.show_grid = self.technical_grid_toggle.isChecked()
        chart.show_crosshair = self.technical_crosshair_toggle.isChecked()
        chart.update()

    def reset_technical_view(self):
        if self.technical_data is not None:
            self.technical_chart.set_data(
                self.technical_data["history"],
                self.technical_period.currentText()
            )

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

        self.technical_values["Trend"].setText(str(summary.get("trend", "—")))
        self.technical_values["Momentum"].setText(str(summary.get("momentum", "—")))
        self.technical_values["Volume Status"].setText(str(summary.get("volume", "—")))
        mapping = {
            "Price": "price", "SMA 20": "sma20", "SMA 50": "sma50",
            "SMA 200": "sma200", "RSI": "rsi", "MACD": "macd",
            "MACD Signal": "signal", "Volume Z": "volume_z"
        }
        for label, key in mapping.items():
            self.technical_values[label].setText(display_number(values.get(key)))
        latest = history.iloc[-1] if not history.empty else None
        previous = history.iloc[-2] if len(history) > 1 else None
        if latest is not None:
            number = self.technical_chart.numeric
            fmt = self.technical_chart.fmt
            compact = self.technical_chart.compact
            close = number(latest.get("Close"))
            prev_close = number(previous.get("Close")) if previous is not None else None
            self.technical_price.setText(fmt(close))
            if close is not None and prev_close not in (None, 0):
                change = close - prev_close
                percent = 100 * change / prev_close
                color = "#22c55e" if change >= 0 else "#ef4444"
                self.technical_change.setText(f"{change:+.2f} ({percent:+.2f}%) vs previous close")
                self.technical_change.setStyleSheet(f"color: {color}; font-weight: 700;")
            else:
                self.technical_change.setText("Latest available close")
            for label, column in (("Open", "Open"), ("High", "High"),
                                  ("Low", "Low")):
                self.technical_snapshot[label].setText(fmt(latest.get(column)))
            self.technical_snapshot["Prev Close"].setText(
                fmt(previous.get("Close")) if previous is not None else "—")
            self.technical_snapshot["Volume"].setText(compact(latest.get("Volume")))
            self.technical_snapshot["Avg Volume"].setText(compact(latest.get("VOLUME_AVG20")))
            self.technical_values["MACD Hist"].setText(fmt(latest.get("MACD_HIST"), 3))
            self.technical_values["Volume"].setText(compact(latest.get("Volume")))
            self.technical_values["Avg Volume"].setText(compact(latest.get("VOLUME_AVG20")))
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
