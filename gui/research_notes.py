"""Polished, ticker-specific StockTerminal research notebook."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "research_notes.db"


class ResearchNotes(QWidget):
    FIELDS = (
        ("thesis", "Investment Thesis", "Write your central argument about this company. What do you believe, and why?"),
        ("findings", "Key Findings", "Revenue trends, valuation observations, competitive advantages, catalysts..."),
        ("risks", "Risks & Concerns", "What could challenge your thesis? What evidence would change your view?"),
        ("sources", "Research Sources", "Paste links to articles, earnings reports, filings, and other supporting research..."),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(DB_PATH))
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS research_notes (
                ticker TEXT PRIMARY KEY,
                thesis TEXT NOT NULL DEFAULT '',
                findings TEXT NOT NULL DEFAULT '',
                risks TEXT NOT NULL DEFAULT '',
                sources TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()
        self.ticker = None
        self.dirty = False
        self.loading = False

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(1000)
        self.save_timer.timeout.connect(self.save)

        self.setStyleSheet("""
            QWidget#ResearchNotebook { background: #0e1726; }
            QFrame#ResearchPanel {
                background: #172235;
                border: 1px solid #29394f;
                border-radius: 12px;
            }
            QLabel#NotebookEyebrow {
                color: #60a5fa; font-size: 10px; font-weight: 800;
                letter-spacing: 2px; background: transparent;
            }
            QLabel#NotebookTitle {
                color: #f1f5f9; font-size: 25px; font-weight: 750;
                background: transparent;
            }
            QLabel#NotebookSubtle {
                color: #94a3b8; font-size: 12px; background: transparent;
            }
            QLabel#NotebookSection {
                color: #e2e8f0; font-size: 14px; font-weight: 700;
                background: transparent;
            }
            QLabel#NotebookHint {
                color: #94a3b8; font-size: 11px; background: transparent;
            }
            QLabel#NotebookBadge {
                color: #93c5fd; background: #1d3453;
                border: 1px solid #34577f; border-radius: 9px;
                padding: 5px 11px; font-weight: 700;
            }
            QTextEdit#NotebookEditor {
                color: #e2e8f0; background: #101b2c;
                border: 1px solid #304158; border-radius: 8px;
                padding: 12px; font-size: 13px;
                selection-background-color: #2563eb;
            }
            QTextEdit#NotebookEditor:focus { border: 1px solid #60a5fa; }
            QTextEdit#NotebookEditor:read-only { color: #64748b; }
            QPushButton#NotebookSave {
                background: #2563eb; color: white; border: none;
                border-radius: 8px; padding: 10px 18px; font-weight: 700;
            }
            QPushButton#NotebookSave:hover { background: #3b82f6; }
            QPushButton#NotebookSave:disabled { background: #24354b; color: #718096; }
        """)
        self.setObjectName("ResearchNotebook")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 16)
        root.setSpacing(14)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(14)
        title_group = QVBoxLayout()
        title_group.setSpacing(5)
        eyebrow = QLabel("STOCK EXPLORER  /  RESEARCH")
        eyebrow.setObjectName("NotebookEyebrow")
        title_group.addWidget(eyebrow)
        self.heading = QLabel("Research Notebook")
        self.heading.setObjectName("NotebookTitle")
        title_group.addWidget(self.heading)
        heading_row.addLayout(title_group, 1)
        self.ticker_badge = QLabel("NO TICKER")
        self.ticker_badge.setObjectName("NotebookBadge")
        heading_row.addWidget(self.ticker_badge, 0, Qt.AlignVCenter)
        self.save_button = QPushButton("Save Research")
        self.save_button.setObjectName("NotebookSave")
        self.save_button.clicked.connect(self.save)
        heading_row.addWidget(self.save_button, 0, Qt.AlignVCenter)
        root.addLayout(heading_row)

        info_row = QHBoxLayout()
        self.status = QLabel("Select a stock in Overview to begin.")
        self.status.setObjectName("NotebookSubtle")
        info_row.addWidget(self.status, 1)
        self.updated_label = QLabel("LOCAL NOTEBOOK  ·  AUTOSAVE ON")
        self.updated_label.setObjectName("NotebookSubtle")
        info_row.addWidget(self.updated_label)
        root.addLayout(info_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QWidget()
        content = QVBoxLayout(body)
        content.setContentsMargins(0, 4, 5, 8)
        content.setSpacing(14)
        self.editors = {}

        thesis = self._panel("thesis", "01  /  Investment Thesis",
                             "The central argument behind your assessment", 190)
        content.addWidget(thesis)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        middle.addWidget(self._panel("findings", "02  /  Key Findings",
                                     "Evidence, observations, and catalysts", 190), 1)
        middle.addWidget(self._panel("risks", "03  /  Risks & Concerns",
                                     "Uncertainties and counterarguments", 190), 1)
        content.addLayout(middle)

        content.addWidget(self._panel("sources", "04  /  Research Sources",
                                       "Reports, articles, filings, and useful links", 125))
        content.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.set_ticker(None)

    def _panel(self, key, title, hint, height):
        panel = QFrame()
        panel.setObjectName("ResearchPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("NotebookSection")
        layout.addWidget(label)
        caption = QLabel(hint)
        caption.setObjectName("NotebookHint")
        layout.addWidget(caption)
        placeholder = next(p for k, _, p in self.FIELDS if k == key)
        editor = QTextEdit()
        editor.setObjectName("NotebookEditor")
        editor.setPlaceholderText(placeholder)
        editor.setMinimumHeight(height)
        editor.textChanged.connect(self.changed)
        self.editors[key] = editor
        layout.addWidget(editor)
        return panel

    def changed(self):
        if self.loading or not self.ticker:
            return
        self.dirty = True
        self.status.setText(f"●  Unsaved changes for {self.ticker}")
        self.save_timer.start()

    def set_ticker(self, ticker):
        ticker = str(ticker).strip().upper() if ticker else None
        if ticker == self.ticker:
            return
        self.save_timer.stop()
        self.save()
        self.ticker = ticker
        self.loading = True
        try:
            row = None
            if ticker:
                row = self.connection.execute(
                    "SELECT thesis, findings, risks, sources, updated_at "
                    "FROM research_notes WHERE ticker = ?", (ticker,)
                ).fetchone()
            for index, (key, _, _) in enumerate(self.FIELDS):
                self.editors[key].setPlainText(row[index] if row else "")
                self.editors[key].setReadOnly(not bool(ticker))
            self.heading.setText("Research Notebook" if not ticker else f"Research Notebook  /  {ticker}")
            self.ticker_badge.setText(ticker or "NO TICKER")
            self.save_button.setEnabled(bool(ticker))
            if row:
                self.status.setText(f"✓  Research loaded for {ticker}")
                self.updated_label.setText(f"LAST SAVED  ·  {self._display_utc(row[4])}")
            else:
                self.status.setText(f"New research workspace for {ticker}" if ticker else
                                    "Select a stock in Overview to begin.")
                self.updated_label.setText("LOCAL NOTEBOOK  ·  AUTOSAVE ON")
            self.dirty = False
        finally:
            self.loading = False

    @staticmethod
    def _display_utc(value):
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            return dt.astimezone().strftime("%b %d, %Y  ·  %I:%M %p")
        except (TypeError, ValueError):
            return str(value)

    def save(self):
        if not self.ticker or not self.dirty:
            return
        values = [self.editors[key].toPlainText() for key, _, _ in self.FIELDS]
        try:
            with self.connection:
                self.connection.execute("""
                    INSERT INTO research_notes
                        (ticker, thesis, findings, risks, sources, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(ticker) DO UPDATE SET
                        thesis=excluded.thesis,
                        findings=excluded.findings,
                        risks=excluded.risks,
                        sources=excluded.sources,
                        updated_at=CURRENT_TIMESTAMP
                """, (self.ticker, *values))
            self.dirty = False
            self.status.setText(f"✓  All changes saved for {self.ticker}")
            self.updated_label.setText(
                "LAST SAVED  ·  " + datetime.now().astimezone().strftime("%b %d, %Y  ·  %I:%M %p")
            )
        except sqlite3.Error as exc:
            self.status.setText(f"Unable to save notes: {exc}")

    def closeEvent(self, event):
        self.save_timer.stop()
        self.save()
        self.connection.close()
        super().closeEvent(event)
