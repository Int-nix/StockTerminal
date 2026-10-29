"""
StockTerminal - Fundamental Analysis

Features:
- Company overview
- Financial metric cards
- Annual and quarterly income statements
- Annual and quarterly balance sheets
- Annual and quarterly cash flow statements
- Discounted Cash Flow (DCF) valuation
- Editable valuation assumptions
- Projected free cash flows
- Valuation sensitivity analysis
"""

import math

from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QTabWidget,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QScrollArea,
    QGridLayout,
    QDoubleSpinBox,
    QSpinBox,
    QGroupBox
)

from core.fundamentals import (
    FundamentalWorker,
    percentage_change
)


# ============================================================
# METRIC DESCRIPTIONS
# ============================================================

METRIC_HELP = {
    "Market Cap": (
        "Market value of outstanding shares."
    ),
    "Enterprise Value": (
        "Market capitalization plus net debt and other claims."
    ),
    "Revenue (TTM)": (
        "Total revenue over the trailing twelve months."
    ),
    "Revenue (latest FY)": (
        "Revenue in the latest fiscal year."
    ),
    "Net Income (TTM)": (
        "Net income over the trailing twelve months."
    ),
    "Net Income (latest FY)": (
        "Net income in the latest fiscal year."
    ),
    "Profit Margin": (
        "Net profit divided by revenue."
    ),
    "Return on Equity": (
        "Net income relative to shareholders' equity."
    ),
    "Free Cash Flow (TTM)": (
        "Operating cash flow minus capital expenditures."
    ),
    "Free Cash Flow (latest FY)": (
        "Free cash flow in the latest fiscal year."
    ),
    "Debt / Equity": (
        "Total debt relative to shareholders' equity."
    )
}


# ============================================================
# FORMATTING
# ============================================================

def format_amount(value):

    if value is None:
        return "—"

    try:
        value = float(value)

        if not math.isfinite(value):
            return "—"

    except (TypeError, ValueError):
        return "—"

    sign = "-" if value < 0 else ""
    value = abs(value)

    for threshold, suffix in (
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K")
    ):

        if value >= threshold:
            return (
                f"{sign}"
                f"{value / threshold:,.2f}"
                f"{suffix}"
            )

    return f"{sign}{value:,.2f}"


def format_metric(value, kind):

    if value is None:
        return "—"

    if kind == "percent":
        return f"{value * 100:,.2f}%"

    if kind == "de_ratio":
        return f"{value / 100:,.2f}x"

    return format_amount(value)


def safe_number(value):

    if value is None:
        return None

    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return None


def first_number(info, *keys):

    for key in keys:

        value = safe_number(info.get(key))

        if value is not None:
            return value

    return None


# ============================================================
# FUNDAMENTALS MIXIN
# ============================================================

class FundamentalsMixin:

    # ========================================================
    # BUILD FUNDAMENTAL ANALYSIS PAGE
    # ========================================================

    def build_fundamentals(self):

        page = QWidget()

        root = QVBoxLayout(page)

        root.setContentsMargins(
            25, 20, 25, 20
        )

        root.setSpacing(12)

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        top = QHBoxLayout()

        title = QLabel(
            "Fundamental Analysis"
        )

        title.setObjectName("Title")

        top.addWidget(title)
        top.addStretch()

        self.fund_input = QLineEdit()

        self.fund_input.setPlaceholderText(
            "Ticker: AAPL, MSFT, TD.TO..."
        )

        self.fund_input.setFixedWidth(230)

        self.fund_input.returnPressed.connect(
            self.search_fundamentals
        )

        top.addWidget(self.fund_input)

        self.fund_search = QPushButton(
            "Analyze"
        )

        self.fund_search.setObjectName(
            "Primary"
        )

        self.fund_search.clicked.connect(
            self.search_fundamentals
        )

        top.addWidget(self.fund_search)

        root.addLayout(top)

        # ----------------------------------------------------
        # COMPANY INFORMATION
        # ----------------------------------------------------

        self.fund_company = QLabel(
            "Search for a company to view its financial statements."
        )

        self.fund_company.setObjectName(
            "SectionTitle"
        )

        root.addWidget(self.fund_company)

        self.fund_details = QLabel(
            "Annual and quarterly data depend on Yahoo Finance availability."
        )

        self.fund_details.setObjectName(
            "Muted"
        )

        self.fund_details.setWordWrap(True)

        root.addWidget(self.fund_details)

        # ----------------------------------------------------
        # FINANCIAL METRIC CARDS
        # ----------------------------------------------------

        self.fund_cards = {}

        card_container = QWidget()

        grid = QGridLayout(
            card_container
        )

        grid.setContentsMargins(
            0, 0, 0, 0
        )

        grid.setSpacing(10)

        card_names = [
            "Market Cap",
            "Enterprise Value",
            "Revenue",
            "Net Income",
            "Profit Margin",
            "Return on Equity",
            "Free Cash Flow",
            "Debt / Equity"
        ]

        for index, name in enumerate(card_names):

            frame = QFrame()

            frame.setObjectName("Card")

            vertical = QVBoxLayout(frame)

            label = QLabel(name)

            label.setObjectName("Muted")

            value = QLabel("—")

            value.setStyleSheet(
                "font-size: 20px;"
                "font-weight: bold;"
            )

            vertical.addWidget(label)
            vertical.addWidget(value)

            grid.addWidget(
                frame,
                index // 4,
                index % 4
            )

            self.fund_cards[name] = (
                label,
                value
            )

        root.addWidget(card_container)

        # ----------------------------------------------------
        # FINANCIAL TABS
        # ----------------------------------------------------

        self.fund_tabs = QTabWidget()

        self.fund_tables = {}

        for name in (
            "Overview",
            "Income Statement",
            "Balance Sheet",
            "Cash Flow"
        ):

            if name == "Overview":

                overview = QWidget()

                ov = QVBoxLayout(
                    overview
                )

                self.fund_overview = QLabel(
                    "Select a ticker and click Analyze."
                )

                self.fund_overview.setWordWrap(
                    True
                )

                self.fund_overview.setAlignment(
                    Qt.AlignTop
                )

                ov.addWidget(
                    self.fund_overview
                )

                ov.addStretch()

                self.fund_tabs.addTab(
                    overview,
                    name
                )

            else:

                container = QWidget()

                vertical = QVBoxLayout(
                    container
                )

                controls = QHBoxLayout()

                controls.addWidget(
                    QLabel("Reporting period:")
                )

                period = QComboBox()

                period.addItems([
                    "Annual",
                    "Quarterly"
                ])

                period.currentTextChanged.connect(
                    lambda _text, n=name:
                    self.populate_fund_table(n)
                )

                controls.addWidget(period)
                controls.addStretch()

                vertical.addLayout(
                    controls
                )

                table = QTableWidget()

                table.setEditTriggers(
                    QAbstractItemView.NoEditTriggers
                )

                table.setSelectionBehavior(
                    QAbstractItemView.SelectRows
                )

                table.verticalHeader().setVisible(
                    False
                )

                table.horizontalHeader().setStretchLastSection(
                    True
                )

                table.setAlternatingRowColors(
                    True
                )

                vertical.addWidget(table)

                self.fund_tables[name] = (
                    table,
                    period
                )

                self.fund_tabs.addTab(
                    container,
                    name
                )

        # ----------------------------------------------------
        # NEW DCF TAB
        # ----------------------------------------------------

        self.build_dcf_tab()

        root.addWidget(
            self.fund_tabs,
            1
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.fund_status = QLabel(
            "Financial figures are informational "
            "and may be delayed or unavailable."
        )

        self.fund_status.setObjectName(
            "Muted"
        )

        root.addWidget(
            self.fund_status
        )

        self.pages.addWidget(page)

        # ----------------------------------------------------
        # WORKER STATE
        # ----------------------------------------------------

        self.fund_worker = None

        self.fund_data = None

        self.fund_requested_ticker = None

        self.fund_pending_ticker = None

    # ========================================================
    # SEARCH FUNDAMENTALS
    # ========================================================

    def search_fundamentals(self):

        self.load_fundamentals(
            self.fund_input.text()
        )

    # ========================================================
    # LOAD FUNDAMENTALS
    # ========================================================

    def load_fundamentals(self, ticker):

        ticker = ticker.strip().upper()

        if not ticker:
            return

        self.fund_input.setText(ticker)

        self.fund_requested_ticker = ticker

        if self.fund_worker is not None:

            self.fund_pending_ticker = ticker

            self.fund_status.setText(
                f"Waiting to load {ticker} "
                "after current request..."
            )

            return

        self._start_fund_worker(ticker)

    # ========================================================
    # START FUNDAMENTAL WORKER
    # ========================================================

    def _start_fund_worker(self, ticker):

        self.fund_status.setText(
            f"Loading financial statements for {ticker}..."
        )

        self.fund_company.setText(
            f"Loading {ticker}..."
        )

        self.fund_search.setEnabled(False)

        worker = FundamentalWorker(ticker)

        self.fund_worker = worker

        worker.signals.finished.connect(
            lambda data, w=worker:
            self.fund_loaded(data, w)
        )

        worker.signals.error.connect(
            lambda error, w=worker:
            self.fund_failed(error, w)
        )

        self.threadpool.start(worker)

    # ========================================================
    # FINISH FUNDAMENTAL REQUEST
    # ========================================================

    def _finish_fund_request(self, worker):

        if self.fund_worker is worker:
            self.fund_worker = None

        self.fund_search.setEnabled(True)

        pending = self.fund_pending_ticker

        self.fund_pending_ticker = None

        if pending and pending != worker.ticker:
            self._start_fund_worker(pending)

    # ========================================================
    # FUNDAMENTALS LOADED
    # ========================================================

    def fund_loaded(self, data, worker):

        if self.fund_requested_ticker != data["ticker"]:

            self._finish_fund_request(worker)

            return

        self.fund_data = data

        info = data["info"]

        ticker = data["ticker"]

        company = (
            info.get("longName")
            or info.get("shortName")
            or ticker
        )

        self.fund_company.setText(
            f"{company} ({ticker})"
        )

        self.fund_details.setText(
            "  ·  ".join(
                filter(
                    None,
                    [
                        info.get("sector"),
                        info.get("industry"),
                        info.get("exchange"),
                        (
                            "Reporting currency: "
                            f"{info.get('financialCurrency') or info.get('currency') or 'not specified'}"
                        )
                    ]
                )
            )
        )

        # ----------------------------------------------------
        # METRIC CARDS
        # ----------------------------------------------------

        card_names = list(
            self.fund_cards
        )

        for i, (name, value, kind) in enumerate(
            data["metrics"]
        ):

            if i >= len(card_names):
                break

            label, value_label = (
                self.fund_cards[card_names[i]]
            )

            label.setText(name)

            label.setToolTip(
                METRIC_HELP.get(
                    name,
                    "Financial metric reported by Yahoo Finance."
                )
            )

            value_label.setText(
                format_metric(value, kind)
            )

        # ----------------------------------------------------
        # COMPANY OVERVIEW
        # ----------------------------------------------------

        summary = (
            info.get("longBusinessSummary")
            or "No company description available."
        )

        self.fund_overview.setText(
            summary[:1800]
            + (
                "…"
                if len(summary) > 1800
                else ""
            )
        )

        # ----------------------------------------------------
        # FINANCIAL STATEMENTS
        # ----------------------------------------------------

        for name in self.fund_tables:
            self.populate_fund_table(name)

        # ----------------------------------------------------
        # POPULATE DCF
        # ----------------------------------------------------

        self.prepare_dcf(data)

        self.fund_status.setText(
            f"{ticker} loaded. "
            "FY = fiscal year; missing fields display as —. "
            "Year-over-year % is calculated "
            "for annual statements only."
        )

        self._finish_fund_request(worker)

    # ========================================================
    # FUNDAMENTALS FAILED
    # ========================================================

    def fund_failed(self, error, worker):

        if self.fund_requested_ticker == worker.ticker:

            self.fund_company.setText(
                f"Unable to load {worker.ticker}"
            )

            self.fund_status.setText(error)

        self._finish_fund_request(worker)

    # ========================================================
    # POPULATE FINANCIAL TABLE
    # ========================================================

    def populate_fund_table(self, name):

        if not self.fund_data:
            return

        table, selector = (
            self.fund_tables[name]
        )

        period = selector.currentText()

        statement = (
            self.fund_data["statements"][name][period]
        )

        dates = statement["dates"]

        rows = statement["rows"]

        table.setSortingEnabled(False)

        table.clear()

        table.setRowCount(
            len(rows)
        )

        table.setColumnCount(
            len(dates) + 2
        )

        table.setHorizontalHeaderLabels([
            "Metric",
            *dates,
            (
                "YoY %"
                if period == "Annual"
                else "Latest QoQ %"
            )
        ])

        for i, (label, values) in enumerate(rows):

            table.setItem(
                i,
                0,
                QTableWidgetItem(label)
            )

            for j, val in enumerate(values):

                cell = QTableWidgetItem(
                    "—"
                    if val is None
                    else format_amount(val)
                )

                if val is not None:

                    cell.setToolTip(
                        f"{val:,.4f}"
                    )

                table.setItem(
                    i,
                    j + 1,
                    cell
                )

            change = (
                percentage_change(
                    values[0],
                    values[1]
                )
                if len(values) >= 2
                else None
            )

            table.setItem(
                i,
                len(dates) + 1,
                QTableWidgetItem(
                    "—"
                    if change is None
                    else f"{change:+.2f}%"
                )
            )

        table.setColumnWidth(
            0,
            215
        )

        for col in range(
            1,
            table.columnCount()
        ):

            table.setColumnWidth(
                col,
                145
            )

        table.setSortingEnabled(False)

    # ========================================================
    # BUILD DCF TAB
    # ========================================================

    def build_dcf_tab(self):

        page = QWidget()

        outer = QVBoxLayout(page)

        outer.setContentsMargins(
            0, 0, 0, 0
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(
            QFrame.NoFrame
        )

        body = QWidget()

        layout = QVBoxLayout(body)

        layout.setContentsMargins(
            20, 20, 20, 20
        )

        layout.setSpacing(16)

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = QLabel(
            "Discounted Cash Flow Valuation"
        )

        title.setObjectName(
            "SectionTitle"
        )

        layout.addWidget(title)

        description = QLabel(
            "Estimate a company's intrinsic value "
            "using projected future free cash flows. "
            "The model uses a five-year forecast by default. "
            "Financial inputs and assumptions can be edited."
        )

        description.setWordWrap(True)

        description.setObjectName(
            "Muted"
        )

        layout.addWidget(description)

        # ----------------------------------------------------
        # INPUTS
        # ----------------------------------------------------

        assumptions = QGroupBox(
            "DCF Assumptions"
        )

        grid = QGridLayout(
            assumptions
        )

        grid.setSpacing(12)

        self.dcf_inputs = {}

        def add_input(
            key,
            label,
            row,
            column,
            default=0,
            minimum=0,
            maximum=1e12,
            suffix=""
        ):

            field = QDoubleSpinBox()

            field.setRange(
                minimum,
                maximum
            )

            field.setDecimals(2)

            field.setValue(default)

            field.setSuffix(suffix)

            field.setMinimumWidth(150)

            field.setGroupSeparatorShown(True)

            grid.addWidget(
                QLabel(label),
                row * 2,
                column
            )

            grid.addWidget(
                field,
                row * 2 + 1,
                column
            )

            self.dcf_inputs[key] = field

            return field

        add_input(
            "fcf",
            "Annual Free Cash Flow (Millions)",
            0, 0,
            minimum=-1e12
        )

        add_input(
            "cash",
            "Cash & Equivalents (Millions)",
            0, 1
        )

        add_input(
            "debt",
            "Total Debt (Millions)",
            0, 2
        )

        add_input(
            "shares",
            "Shares Outstanding (Millions)",
            1, 0
        )

        add_input(
            "growth",
            "Annual FCF Growth",
            1, 1,
            default=5,
            minimum=-50,
            maximum=100,
            suffix="%"
        )

        add_input(
            "discount",
            "Discount Rate",
            1, 2,
            default=10,
            minimum=0.1,
            maximum=100,
            suffix="%"
        )

        add_input(
            "terminal",
            "Terminal Growth Rate",
            2, 0,
            default=2.5,
            minimum=-10,
            maximum=30,
            suffix="%"
        )

        add_input(
            "price",
            "Current Market Price",
            2, 1,
            maximum=1e9
        )

        self.dcf_years = QSpinBox()

        self.dcf_years.setRange(
            3, 10
        )

        self.dcf_years.setValue(5)

        grid.addWidget(
            QLabel("Forecast Period"),
            4, 2
        )

        grid.addWidget(
            self.dcf_years,
            5, 2
        )

        layout.addWidget(
            assumptions
        )

        # ----------------------------------------------------
        # DATA SOURCE
        # ----------------------------------------------------

        self.dcf_source = QLabel(
            "Load a company to populate the DCF inputs."
        )

        self.dcf_source.setWordWrap(True)

        self.dcf_source.setObjectName(
            "Muted"
        )

        layout.addWidget(
            self.dcf_source
        )

        # ----------------------------------------------------
        # CALCULATE BUTTON
        # ----------------------------------------------------

        buttons = QHBoxLayout()

        self.dcf_calculate_button = QPushButton(
            "Calculate DCF"
        )

        self.dcf_calculate_button.setObjectName(
            "Primary"
        )

        self.dcf_calculate_button.clicked.connect(
            self.calculate_dcf
        )

        buttons.addWidget(
            self.dcf_calculate_button
        )

        buttons.addStretch()

        layout.addLayout(buttons)

        # ----------------------------------------------------
        # VALUATION RESULTS
        # ----------------------------------------------------

        results_group = QGroupBox(
            "Valuation Results"
        )

        results_layout = QGridLayout(
            results_group
        )

        self.dcf_results = {}

        result_names = [
            ("enterprise", "Enterprise Value"),
            ("equity", "Estimated Equity Value"),
            ("intrinsic", "Intrinsic Value Per Share"),
            ("market", "Current Market Price"),
            ("upside", "Potential Upside / Downside"),
            ("safety", "Margin of Safety")
        ]

        for index, (key, name) in enumerate(
            result_names
        ):

            frame = QFrame()

            frame.setObjectName("Card")

            vertical = QVBoxLayout(frame)

            label = QLabel(name)

            label.setObjectName(
                "Muted"
            )

            value = QLabel("—")

            value.setStyleSheet(
                "font-size: 21px;"
                "font-weight: bold;"
            )

            vertical.addWidget(label)
            vertical.addWidget(value)

            results_layout.addWidget(
                frame,
                index // 3,
                index % 3
            )

            self.dcf_results[key] = value

        layout.addWidget(
            results_group
        )

        # ----------------------------------------------------
        # PROJECTED CASH FLOWS
        # ----------------------------------------------------

        forecast_group = QGroupBox(
            "Projected Free Cash Flows"
        )

        forecast_layout = QVBoxLayout(
            forecast_group
        )

        self.dcf_forecast_table = QTableWidget()

        self.dcf_forecast_table.setColumnCount(4)

        self.dcf_forecast_table.setHorizontalHeaderLabels([
            "Year",
            "Projected FCF",
            "Discount Factor",
            "Present Value"
        ])

        self.dcf_forecast_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.dcf_forecast_table.setAlternatingRowColors(
            True
        )

        self.dcf_forecast_table.verticalHeader().setVisible(
            False
        )

        self.dcf_forecast_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.dcf_forecast_table.setMinimumHeight(
            220
        )

        forecast_layout.addWidget(
            self.dcf_forecast_table
        )

        layout.addWidget(
            forecast_group
        )

        # ----------------------------------------------------
        # VALUATION BREAKDOWN
        # ----------------------------------------------------

        breakdown_group = QGroupBox(
            "Valuation Breakdown"
        )

        breakdown_layout = QVBoxLayout(
            breakdown_group
        )

        self.dcf_breakdown = QLabel(
            "Calculate a valuation to view the breakdown."
        )

        self.dcf_breakdown.setWordWrap(True)

        self.dcf_breakdown.setTextFormat(
            Qt.PlainText
        )

        self.dcf_breakdown.setStyleSheet(
            "font-family: Consolas, monospace;"
            "font-size: 13px;"
            "padding: 12px;"
        )

        breakdown_layout.addWidget(
            self.dcf_breakdown
        )

        layout.addWidget(
            breakdown_group
        )

        # ----------------------------------------------------
        # SENSITIVITY ANALYSIS
        # ----------------------------------------------------

        sensitivity_group = QGroupBox(
            "Valuation Sensitivity Analysis"
        )

        sensitivity_layout = QVBoxLayout(
            sensitivity_group
        )

        sensitivity_description = QLabel(
            "Estimated intrinsic value per share under "
            "different discount rates and terminal growth rates."
        )

        sensitivity_description.setWordWrap(
            True
        )

        sensitivity_layout.addWidget(
            sensitivity_description
        )

        self.dcf_sensitivity_table = QTableWidget()

        self.dcf_sensitivity_table.setRowCount(5)

        self.dcf_sensitivity_table.setColumnCount(5)

        self.dcf_sensitivity_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.dcf_sensitivity_table.verticalHeader().setVisible(
            False
        )

        self.dcf_sensitivity_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.dcf_sensitivity_table.setMinimumHeight(
            210
        )

        sensitivity_layout.addWidget(
            self.dcf_sensitivity_table
        )

        layout.addWidget(
            sensitivity_group
        )

        # ----------------------------------------------------
        # WARNING
        # ----------------------------------------------------

        warning = QLabel(
            "DCF valuations are estimates, not predictions. "
            "Results are highly sensitive to growth rates, "
            "discount rates, terminal assumptions, and "
            "the quality of financial data. "
            "This model uses a simplified free-cash-flow "
            "approach and may not be appropriate for banks, "
            "insurers, or companies with unstable cash flows."
        )

        warning.setWordWrap(True)

        warning.setObjectName(
            "Muted"
        )

        layout.addWidget(warning)

        self.dcf_status = QLabel(
            "Waiting for financial data."
        )

        self.dcf_status.setWordWrap(True)

        layout.addWidget(
            self.dcf_status
        )

        layout.addStretch()

        scroll.setWidget(body)

        outer.addWidget(scroll)

        self.fund_tabs.addTab(
            page,
            "DCF Valuation"
        )

        self.dcf_missing_fields = []

        self.dcf_currency_warning = ""

    # ========================================================
    # EXTRACT FINANCIAL STATEMENT VALUE
    # ========================================================

    def dcf_statement_value(
        self,
        data,
        statement_name,
        possible_names
    ):

        try:

            statement = (
                data["statements"]
                [statement_name]
                ["Annual"]
            )

            rows = statement.get(
                "rows",
                []
            )

            for label, values in rows:

                normalized = (
                    str(label)
                    .strip()
                    .lower()
                    .replace("-", " ")
                )

                for possible in possible_names:

                    if normalized == possible.lower():

                        for value in values:

                            number = safe_number(
                                value
                            )

                            if number is not None:
                                return number

        except (
            KeyError,
            TypeError,
            IndexError,
            AttributeError
        ):
            pass

        return None

    # ========================================================
    # PREPARE DCF DATA
    # ========================================================

    def prepare_dcf(self, data):

        info = data.get(
            "info",
            {}
        ) or {}

        ticker = data.get(
            "ticker",
            ""
        )

        missing = []

        # ----------------------------------------------------
        # FREE CASH FLOW
        # ----------------------------------------------------

        fcf = self.dcf_statement_value(
            data,
            "Cash Flow",
            [
                "Free Cash Flow",
                "FreeCashFlow"
            ]
        )

        if fcf is None:

            operating = self.dcf_statement_value(
                data,
                "Cash Flow",
                [
                    "Operating Cash Flow",
                    "Operating Cashflow",
                    "Cash Flow From Continuing Operating Activities",
                    "Total Cash From Operating Activities"
                ]
            )

            capex = self.dcf_statement_value(
                data,
                "Cash Flow",
                [
                    "Capital Expenditure",
                    "Capital Expenditures",
                    "CapitalExpenditure"
                ]
            )

            if (
                operating is not None
                and capex is not None
            ):

                # Yahoo commonly reports capital
                # expenditure as a negative value.
                fcf = operating - abs(capex)

        if fcf is None:

            fcf = first_number(
                info,
                "freeCashflow"
            )

        # ----------------------------------------------------
        # CASH
        # ----------------------------------------------------

        cash = self.dcf_statement_value(
            data,
            "Balance Sheet",
            [
                "Cash And Cash Equivalents",
                "Cash And Cash Equivalents And Short Term Investments",
                "Cash Cash Equivalents And Short Term Investments",
                "Cash And Short Term Investments",
                "Cash"
            ]
        )

        if cash is None:

            cash = first_number(
                info,
                "totalCash"
            )

        # ----------------------------------------------------
        # DEBT
        # ----------------------------------------------------

        debt = self.dcf_statement_value(
            data,
            "Balance Sheet",
            [
                "Total Debt",
                "TotalDebt"
            ]
        )

        if debt is None:

            debt = first_number(
                info,
                "totalDebt"
            )

        # ----------------------------------------------------
        # SHARES
        # ----------------------------------------------------

        shares = first_number(
            info,
            "sharesOutstanding"
        )

        # ----------------------------------------------------
        # MARKET PRICE
        # ----------------------------------------------------

        price = first_number(
            info,
            "currentPrice",
            "regularMarketPrice",
            "previousClose"
        )

        # ----------------------------------------------------
        # SET INPUT VALUES
        # ----------------------------------------------------

        values = {
            "fcf": fcf,
            "cash": cash,
            "debt": debt,
            "shares": shares
        }

        for key, value in values.items():

            if value is None:

                missing.append(key)

                self.dcf_inputs[key].setValue(0)

            else:

                # Financial inputs are displayed
                # in millions.
                self.dcf_inputs[key].setValue(
                    value / 1_000_000
                )

        if price is None:

            missing.append("price")

            self.dcf_inputs["price"].setValue(
                0
            )

        else:

            self.dcf_inputs["price"].setValue(
                price
            )

        self.dcf_missing_fields = missing

        # ----------------------------------------------------
        # CURRENCY CHECK
        # ----------------------------------------------------

        financial_currency = info.get(
            "financialCurrency"
        )

        trading_currency = info.get(
            "currency"
        )

        self.dcf_currency_warning = ""

        if (
            financial_currency
            and trading_currency
            and financial_currency != trading_currency
        ):

            self.dcf_currency_warning = (
                f"WARNING: Financial statements use "
                f"{financial_currency}, while the stock "
                f"price uses {trading_currency}. "
                "Convert the values to a common currency "
                "before interpreting the per-share result."
            )

        # ----------------------------------------------------
        # SOURCE DESCRIPTION
        # ----------------------------------------------------

        source_text = (
            f"Loaded financial inputs for {ticker}. "
            "Amounts are displayed in millions."
        )

        if missing:

            source_text += (
                "\nMissing or unavailable inputs: "
                + ", ".join(missing)
                + ". Enter verified values manually."
            )

        if self.dcf_currency_warning:

            source_text += (
                "\n"
                + self.dcf_currency_warning
            )

        self.dcf_source.setText(
            source_text
        )

        # ----------------------------------------------------
        # RESET OLD RESULTS
        # ----------------------------------------------------

        for value in self.dcf_results.values():

            value.setText("—")

        self.dcf_forecast_table.setRowCount(
            0
        )

        self.dcf_sensitivity_table.clearContents()

        self.dcf_breakdown.setText(
            "Adjust the assumptions and calculate the DCF."
        )

        self.dcf_status.setText(
            "Financial inputs loaded. "
            "Review the assumptions before calculating."
        )

    # ========================================================
    # CORE DCF CALCULATION
    # ========================================================

    def dcf_model(
        self,
        fcf,
        cash,
        debt,
        shares,
        growth,
        discount,
        terminal,
        years
    ):

        if shares <= 0:
            raise ValueError(
                "Shares outstanding must be greater than zero."
            )

        if discount <= terminal:
            raise ValueError(
                "Discount rate must be greater "
                "than terminal growth rate."
            )

        if discount <= 0:
            raise ValueError(
                "Discount rate must be positive."
            )

        projections = []

        present_value_sum = 0

        current_fcf = fcf

        for year in range(
            1,
            years + 1
        ):

            current_fcf *= (
                1 + growth
            )

            discount_factor = (
                1 + discount
            ) ** year

            present_value = (
                current_fcf
                / discount_factor
            )

            present_value_sum += (
                present_value
            )

            projections.append({
                "year": year,
                "fcf": current_fcf,
                "factor": discount_factor,
                "pv": present_value
            })

        # ----------------------------------------------------
        # TERMINAL VALUE
        # ----------------------------------------------------

        terminal_fcf = (
            current_fcf
            * (1 + terminal)
        )

        terminal_value = (
            terminal_fcf
            / (discount - terminal)
        )

        terminal_present_value = (
            terminal_value
            / ((1 + discount) ** years)
        )

        # ----------------------------------------------------
        # ENTERPRISE VALUE
        # ----------------------------------------------------

        enterprise_value = (
            present_value_sum
            + terminal_present_value
        )

        # ----------------------------------------------------
        # EQUITY VALUE
        # ----------------------------------------------------

        equity_value = (
            enterprise_value
            + cash
            - debt
        )

        intrinsic_value = (
            equity_value
            / shares
        )

        return {
            "projections": projections,
            "pv_cashflows": present_value_sum,
            "terminal_value": terminal_value,
            "pv_terminal": terminal_present_value,
            "enterprise": enterprise_value,
            "equity": equity_value,
            "intrinsic": intrinsic_value
        }

    # ========================================================
    # CALCULATE DCF
    # ========================================================

    def calculate_dcf(self):

        try:

            # -----------------------------------------------
            # READ INPUTS
            # -----------------------------------------------

            fcf = self.dcf_inputs[
                "fcf"
            ].value()

            cash = self.dcf_inputs[
                "cash"
            ].value()

            debt = self.dcf_inputs[
                "debt"
            ].value()

            shares = self.dcf_inputs[
                "shares"
            ].value()

            growth = (
                self.dcf_inputs[
                    "growth"
                ].value() / 100
            )

            discount = (
                self.dcf_inputs[
                    "discount"
                ].value() / 100
            )

            terminal = (
                self.dcf_inputs[
                    "terminal"
                ].value() / 100
            )

            price = self.dcf_inputs[
                "price"
            ].value()

            years = self.dcf_years.value()

            # -----------------------------------------------
            # VALIDATE INPUTS
            # -----------------------------------------------

            if not self.fund_data:

                raise ValueError(
                    "Load a company before calculating."
                )

            if shares <= 0:

                raise ValueError(
                    "Enter a valid number of shares outstanding."
                )

            if fcf <= 0:

                raise ValueError(
                    "This simplified DCF requires positive "
                    "starting free cash flow. A company with "
                    "negative FCF needs a different forecast model."
                )

            if discount <= terminal:

                raise ValueError(
                    "The discount rate must exceed "
                    "the terminal growth rate."
                )

            # -----------------------------------------------
            # RUN MODEL
            # -----------------------------------------------

            result = self.dcf_model(
                fcf,
                cash,
                debt,
                shares,
                growth,
                discount,
                terminal,
                years
            )

            intrinsic = result[
                "intrinsic"
            ]

            # -----------------------------------------------
            # VALUATION COMPARISON
            # -----------------------------------------------

            upside = None
            margin_of_safety = None

            if price > 0:

                upside = (
                    (intrinsic - price)
                    / price
                    * 100
                )

            if intrinsic > 0 and price > 0:

                margin_of_safety = (
                    (intrinsic - price)
                    / intrinsic
                    * 100
                )

            # -----------------------------------------------
            # UPDATE RESULTS
            # -----------------------------------------------

            self.dcf_results[
                "enterprise"
            ].setText(
                format_amount(
                    result["enterprise"]
                    * 1_000_000
                )
            )

            self.dcf_results[
                "equity"
            ].setText(
                format_amount(
                    result["equity"]
                    * 1_000_000
                )
            )

            self.dcf_results[
                "intrinsic"
            ].setText(
                f"{intrinsic:,.2f}"
            )

            self.dcf_results[
                "market"
            ].setText(
                f"{price:,.2f}"
                if price > 0
                else "—"
            )

            self.dcf_results[
                "upside"
            ].setText(
                f"{upside:+.2f}%"
                if upside is not None
                else "—"
            )

            self.dcf_results[
                "safety"
            ].setText(
                f"{margin_of_safety:+.2f}%"
                if margin_of_safety is not None
                else "—"
            )

            # -----------------------------------------------
            # COLOUR VALUATION
            # -----------------------------------------------

            if upside is not None:

                color = (
                    "#22C55E"
                    if upside >= 0
                    else "#EF4444"
                )

                self.dcf_results[
                    "upside"
                ].setStyleSheet(
                    f"color: {color};"
                    "font-size: 21px;"
                    "font-weight: bold;"
                )

            else:

                self.dcf_results[
                    "upside"
                ].setStyleSheet(
                    "font-size: 21px;"
                    "font-weight: bold;"
                )

            # -----------------------------------------------
            # FORECAST TABLE
            # -----------------------------------------------

            projections = result[
                "projections"
            ]

            table = self.dcf_forecast_table

            table.setRowCount(
                len(projections)
            )

            for row, projection in enumerate(
                projections
            ):

                values = [
                    str(projection["year"]),
                    f"{projection['fcf']:,.2f}M",
                    f"{projection['factor']:,.4f}",
                    f"{projection['pv']:,.2f}M"
                ]

                for column, value in enumerate(
                    values
                ):

                    table.setItem(
                        row,
                        column,
                        QTableWidgetItem(
                            value
                        )
                    )

            # -----------------------------------------------
            # VALUATION BREAKDOWN
            # -----------------------------------------------

            breakdown = (
                "Present Value of Forecast Cash Flows:\n"
                f"    {result['pv_cashflows']:,.2f}M\n\n"

                "Undiscounted Terminal Value:\n"
                f"    {result['terminal_value']:,.2f}M\n\n"

                "Present Value of Terminal Value:\n"
                f"    {result['pv_terminal']:,.2f}M\n\n"

                "Enterprise Value:\n"
                f"    {result['enterprise']:,.2f}M\n\n"

                "Plus Cash & Equivalents:\n"
                f"    {cash:,.2f}M\n\n"

                "Less Total Debt:\n"
                f"    {debt:,.2f}M\n\n"

                "Estimated Equity Value:\n"
                f"    {result['equity']:,.2f}M\n\n"

                "Shares Outstanding:\n"
                f"    {shares:,.2f}M\n\n"

                "Estimated Intrinsic Value Per Share:\n"
                f"    {intrinsic:,.2f}"
            )

            self.dcf_breakdown.setText(
                breakdown
            )

            # -----------------------------------------------
            # SENSITIVITY TABLE
            # -----------------------------------------------

            self.populate_dcf_sensitivity(
                fcf,
                cash,
                debt,
                shares,
                growth,
                discount,
                terminal,
                years
            )

            # -----------------------------------------------
            # STATUS
            # -----------------------------------------------

            status = (
                "DCF calculated successfully. "
                "Values are model estimates."
            )

            if self.dcf_currency_warning:

                status += (
                    " "
                    + self.dcf_currency_warning
                )

            self.dcf_status.setText(
                status
            )

        except Exception as error:

            self.dcf_status.setText(
                f"DCF calculation error: {error}"
            )

    # ========================================================
    # SENSITIVITY ANALYSIS
    # ========================================================

    def populate_dcf_sensitivity(
        self,
        fcf,
        cash,
        debt,
        shares,
        growth,
        discount,
        terminal,
        years
    ):

        table = self.dcf_sensitivity_table

        # Discount rates:
        # -2%, -1%, base, +1%, +2%

        discount_rates = [
            discount - 0.02,
            discount - 0.01,
            discount,
            discount + 0.01,
            discount + 0.02
        ]

        # Terminal growth rates:
        # -1%, -0.5%, base, +0.5%, +1%

        terminal_rates = [
            terminal - 0.01,
            terminal - 0.005,
            terminal,
            terminal + 0.005,
            terminal + 0.01
        ]

        table.setRowCount(5)

        table.setColumnCount(5)

        table.setHorizontalHeaderLabels([
            f"{rate * 100:.2f}%"
            for rate in terminal_rates
        ])

        table.setVerticalHeaderLabels([
            f"{rate * 100:.2f}%"
            for rate in discount_rates
        ])

        table.verticalHeader().setVisible(
            True
        )

        for row, rate in enumerate(
            discount_rates
        ):

            for column, terminal_rate in enumerate(
                terminal_rates
            ):

                try:

                    result = self.dcf_model(
                        fcf,
                        cash,
                        debt,
                        shares,
                        growth,
                        rate,
                        terminal_rate,
                        years
                    )

                    value = result[
                        "intrinsic"
                    ]

                    text = f"{value:,.2f}"

                except ValueError:

                    text = "N/A"

                item = QTableWidgetItem(
                    text
                )

                item.setTextAlignment(
                    Qt.AlignCenter
                )

                # Highlight the central scenario.

                if row == 2 and column == 2:

                    item.setBackground(
                        Qt.darkBlue
                    )

                    item.setForeground(
                        Qt.white
                    )

                table.setItem(
                    row,
                    column,
                    item
                )
