"""
View window (W2) — the read-only half of the app.

A QStackedWidget rather than more spawned windows: the menu, the savefile picker,
the tree and the statistics page are steps of one flow, and Back returns along it.
Pages keep their state, so returning to the picker preserves the chosen save.
"""

import os

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from src.gui.base import GaribaldiWindow
from src.gui.pages.savefile import SavefilePage
from src.gui.pages.tree import TreePage

PAGE_MENU, PAGE_SAVEFILE, PAGE_TREE, PAGE_STATISTICS = range(4)


class ViewWindow(GaribaldiWindow):
    def __init__(self, parent=None):
        super().__init__("View", parent)
        self.resize(1100, 720)

        layout = QVBoxLayout(self)

        # The statistics page carries its own campaign selector in its top row, so
        # this header is hidden there rather than costing a second row.
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(QLabel("Campaign:"))
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentTextChanged.connect(self._on_campaign_changed)
        header.addWidget(self.campaign_combo, 1)
        layout.addWidget(self.header)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_menu())
        self.savefile_page = SavefilePage(self)
        self.stack.addWidget(self.savefile_page)
        self.tree_page = TreePage(self)
        self.stack.addWidget(self.tree_page)
        from src.gui.pages.statistics import StatisticsPage

        self.statistics_page = StatisticsPage(self)
        self.stack.addWidget(self.statistics_page)
        layout.addWidget(self.stack, 1)

        self._refresh_campaigns()

    def _build_menu(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.savefile_button = QPushButton("View\nSavefile")
        self.savefile_button.setFixedSize(200, 120)
        self.savefile_button.clicked.connect(self.go_savefile)
        row.addWidget(self.savefile_button)
        row.addSpacing(40)
        self.statistics_button = QPushButton("View\nStatistics")
        self.statistics_button.setFixedSize(200, 120)
        self.statistics_button.clicked.connect(self.go_statistics)
        row.addWidget(self.statistics_button)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        return page

    # -- campaign ----------------------------------------------------------

    def campaign(self):
        return self.campaign_combo.currentText()

    def _refresh_campaigns(self):
        os.makedirs("saves", exist_ok=True)
        campaigns = sorted(
            name for name in os.listdir("saves")
            if os.path.isdir(os.path.join("saves", name))
        )
        current = str(self.settings.get("Campaign Folder"))
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaign_combo.addItems(campaigns)
        if current in campaigns:
            self.campaign_combo.setCurrentText(current)
        self.campaign_combo.blockSignals(False)
        self._update_buttons()

    def _on_campaign_changed(self, name):
        self.set_campaign(name)

    def set_campaign(self, name):
        """Single entry point for a campaign change, whichever selector triggered it.

        Both the header combo and the statistics page's own combo route through
        here, so the two can never drift apart.
        """
        if not name:
            return
        self.settings.set("Campaign Folder", name)
        if self.campaign_combo.currentText() != name:
            self.campaign_combo.blockSignals(True)
            self.campaign_combo.setCurrentText(name)
            self.campaign_combo.blockSignals(False)
        self._update_buttons()
        # Both pages are campaign-scoped; the stat tree in particular has leaves
        # that come from this campaign's CSV headers.
        self.savefile_page.refresh()
        self.statistics_page.set_campaign(name)

    def _update_buttons(self):
        has_campaign = bool(self.campaign())
        self.savefile_button.setEnabled(has_campaign)
        self.statistics_button.setEnabled(has_campaign)

    # -- navigation --------------------------------------------------------

    def go_menu(self):
        self.header.setVisible(True)
        self.stack.setCurrentIndex(PAGE_MENU)

    def go_savefile(self):
        self.header.setVisible(True)
        self.savefile_page.refresh()
        self.stack.setCurrentIndex(PAGE_SAVEFILE)

    def show_tree(self, path, show_size=False):
        self.header.setVisible(True)
        self.tree_page.load(path, show_size=show_size)
        self.stack.setCurrentIndex(PAGE_TREE)

    def go_statistics(self):
        self.statistics_page.set_campaign(self.campaign())
        self.statistics_page.refresh_campaigns()
        self.header.setVisible(False)
        self.stack.setCurrentIndex(PAGE_STATISTICS)
