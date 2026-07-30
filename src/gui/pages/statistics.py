"""
Statistics page (P3) — the reason for the whole port.

The stat tree on the left is built from the checker registry at runtime and
rebuilt whenever the campaign changes (see ``src/gui/registry.py``). Selecting a
leaf loads its whole category into the table — the selected column first, so it
can be compared against its siblings — and its figure onto an embedded canvas, so
plots are no longer blocking pop-up windows.

Nothing here computes: the page only reads CSVs a parse has already produced. The
year range and the date slider are view controls and never trigger re-checking.

Layout is deliberately two rows of chrome and nothing else: every control that is
not the tree, the table or the canvas lives in the top or bottom strip.
"""

import os

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSlider, QSpinBox, QSplitter, QStackedWidget, QTableView,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from src.checkers.manager import figures_for
from src.gui.busy import busy
from src.gui.registry import available_files, build_categories
from src.helpers.utility import iter_save_folders

LEAF_ROLE = Qt.UserRole + 1
CANVAS_FIGSIZE = (11, 5.5)
# Columns that identify a row rather than measure it; always kept at the left.
IDENTITY_COLUMNS = ("tag", "country", "company_name", "company_type")


class DataFrameModel(QAbstractTableModel):
    """Read-only view of one save's CSV, sortable on the underlying dtypes.

    Sorting is done here rather than through a QSortFilterProxyModel because a
    proxy compares the *display* strings, which would order a numeric column
    lexicographically ("100" before "9").
    """

    def __init__(self, frame=None):
        super().__init__()
        self._frame = frame if frame is not None else pd.DataFrame()

    def set_frame(self, frame):
        self.beginResetModel()
        self._frame = frame
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._frame.index)

    def columnCount(self, parent=None):
        return len(self._frame.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        value = self._frame.iloc[index.row(), index.column()]
        if isinstance(value, float):
            return f"{value:,.4g}"
        return str(value)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._frame.columns[section])
        return str(self._frame.index[section])

    def sort(self, column, order=Qt.AscendingOrder):
        if self._frame.empty or not (0 <= column < len(self._frame.columns)):
            return
        self.layoutAboutToBeChanged.emit()
        self._frame = self._frame.sort_values(
            by=self._frame.columns[column],
            ascending=(order == Qt.AscendingOrder),
            kind="mergesort",      # stable, so equal values keep CSV order
            na_position="last",
        )
        self.layoutChanged.emit()


class StatisticsPage(QWidget):
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.campaign = None
        self.categories = []
        self.saves = []           # [(save_folder, year_number, label)]
        self._figure_cache = {}
        self._figures = []
        self._marker = None
        self._current_leaf = None
        self.canvas = None
        self.toolbar = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(self._build_top_row())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_tree())
        right = QSplitter(Qt.Vertical)
        right.addWidget(self._build_table())
        right.addWidget(self._build_canvas())
        right.setSizes([200, 460])
        splitter.addWidget(right)
        splitter.setSizes([240, 860])
        layout.addWidget(splitter, 1)

        layout.addWidget(self._build_bottom_row())

    # -- chrome ------------------------------------------------------------

    def _build_top_row(self):
        """Campaign, year range, date slider and the players filter, in one strip."""
        bar = QFrame()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)

        row.addWidget(QLabel("Campaign:"))
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(140)
        self.campaign_combo.currentTextChanged.connect(self._on_campaign_selected)
        row.addWidget(self.campaign_combo)

        row.addSpacing(12)
        row.addWidget(QLabel("Years"))
        self.start_year = QSpinBox()
        self.start_year.setRange(1, 9999)
        self.start_year.setValue(int(self.view.settings.get("Start Year")))
        self.start_year.editingFinished.connect(self._on_range_changed)
        row.addWidget(self.start_year)
        row.addWidget(QLabel("–"))
        self.end_year = QSpinBox()
        self.end_year.setRange(1, 9999)
        self.end_year.setValue(int(self.view.settings.get("End Year")))
        self.end_year.editingFinished.connect(self._on_range_changed)
        row.addWidget(self.end_year)
        reset = QPushButton("Reset")
        reset.setToolTip("Widen the range to every parsed save in this campaign")
        reset.clicked.connect(self._reset_range)
        row.addWidget(reset)

        row.addSpacing(12)
        row.addWidget(QLabel("Date:"))
        self.date_slider = QSlider(Qt.Horizontal)
        self.date_slider.setMinimum(0)
        self.date_slider.setMaximum(0)
        self.date_slider.setMinimumWidth(120)
        self.date_slider.valueChanged.connect(self._on_date_changed)
        row.addWidget(self.date_slider, 1)
        self.date_label = QLabel("—")
        self.date_label.setMinimumWidth(70)
        row.addWidget(self.date_label)

        self.players_only = QCheckBox("Players only")
        self.players_only.setChecked(True)
        self.players_only.toggled.connect(self._on_players_toggled)
        row.addWidget(self.players_only)
        return bar

    def _build_bottom_row(self):
        """Plot picker, status text and the save / back buttons, in one strip."""
        bar = QFrame()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Plot:"))
        self.figure_combo = QComboBox()
        self.figure_combo.setMinimumWidth(150)
        self.figure_combo.currentIndexChanged.connect(self._show_figure)
        row.addWidget(self.figure_combo)
        self.status = QLabel("")
        row.addWidget(self.status, 1)
        self.save_overwrite = QPushButton("Save overwrite")
        self.save_overwrite.clicked.connect(self._save_overwrite)
        row.addWidget(self.save_overwrite)
        self.save_somewhere = QPushButton("Save somewhere")
        self.save_somewhere.clicked.connect(self._save_somewhere)
        row.addWidget(self.save_somewhere)
        back = QPushButton("Back")
        back.clicked.connect(self.view.go_menu)
        row.addWidget(back)
        return bar

    def _build_tree(self):
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Statistics")
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.currentItemChanged.connect(self._on_leaf_selected)
        return self.tree

    def _build_table(self):
        self.table = QTableView()
        self.table_model = DataFrameModel()
        self.table.setModel(self.table_model)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        return self.table

    def _build_canvas(self):
        """A stack of canvases — one per figure, built once and kept.

        Matplotlib's event callbacks live on the *figure*
        (``canvas.callbacks`` is ``figure._canvas_callbacks``), not on the canvas.
        Since figures here are cached and reused, that makes both obvious
        approaches wrong:

        - Rebuilding a canvas + toolbar around a cached figure adds another set of
          connections to that figure's registry every time. The discarded toolbars
          stay connected, and each raises ``RuntimeError: Internal C++ object
          (QLabel) already deleted`` on every mouse move once Qt has destroyed it.
        - Reassigning ``canvas.figure`` in place leaves the toolbar connected to
          the *previous* figure's registry, so pan and zoom silently stop working.

        Pairing each figure with its own canvas and toolbar for as long as the
        figure is cached avoids both: every connection is made exactly once, to
        the figure it belongs to.
        """
        self._canvas_stack = QStackedWidget()
        self._mounts = {}
        self._blank = self._make_mount(Figure(figsize=CANVAS_FIGSIZE))
        self._show_mount(self._blank)
        return self._canvas_stack

    def _make_mount(self, figure):
        """Build the canvas + toolbar that will serve ``figure`` for its lifetime."""
        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        canvas = FigureCanvasQTAgg(figure)
        toolbar = NavigationToolbar2QT(canvas, container)
        box.addWidget(toolbar)
        box.addWidget(canvas, 1)
        self._canvas_stack.addWidget(container)
        mount = (container, canvas, toolbar)
        self._mounts[figure] = mount
        return mount

    def _show_mount(self, mount):
        container, canvas, toolbar = mount
        self._canvas_stack.setCurrentWidget(container)
        self.canvas = canvas
        self.toolbar = toolbar

    def _set_figure(self, figure):
        mount = self._mounts.get(figure) or self._make_mount(figure)
        self._show_mount(mount)

    def _dispose_figures(self, figures):
        """Drop cached figures and the widgets bound to them."""
        for figure in figures:
            mount = self._mounts.pop(figure, None)
            if mount is None:
                continue
            container, canvas, toolbar = mount
            # The figure is being discarded with its callback registry, so this is
            # belt and braces — but leaving a toolbar connected to a figure that
            # outlives it is precisely the bug this class is avoiding.
            for attr in ("_id_press", "_id_release", "_id_drag"):
                cid = getattr(toolbar, attr, None)
                if cid is not None:
                    try:
                        canvas.mpl_disconnect(cid)
                    except Exception:
                        pass
            self._canvas_stack.removeWidget(container)
            container.setParent(None)
            container.deleteLater()

    def _clear_figure_cache(self):
        cached = [figure for figures in self._figure_cache.values() for figure in figures]
        self._figure_cache.clear()
        self._figures = []
        self._show_mount(self._blank)
        self._dispose_figures(cached)

    # -- campaign / tree ---------------------------------------------------

    def refresh_campaigns(self):
        os.makedirs("saves", exist_ok=True)
        campaigns = sorted(
            name for name in os.listdir("saves")
            if os.path.isdir(os.path.join("saves", name))
        )
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaign_combo.addItems(campaigns)
        if self.campaign in campaigns:
            self.campaign_combo.setCurrentText(self.campaign)
        self.campaign_combo.blockSignals(False)

    def _on_campaign_selected(self, name):
        # Routed through the window so the header combo stays in step.
        self.view.set_campaign(name)

    def set_campaign(self, campaign):
        if campaign == self.campaign:
            return
        self.campaign = campaign
        self._clear_figure_cache()
        self._current_leaf = None
        self.refresh_campaigns()
        self._rebuild_tree()
        self._refresh_saves()

    def _rebuild_tree(self):
        self.tree.clear()
        if not self.campaign:
            return
        self.categories = build_categories(self.campaign)
        present = available_files(self.campaign)
        grey = QBrush(QColor(140, 140, 140))
        for category in self.categories:
            parent = QTreeWidgetItem([category.name])
            for leaf in category.leaves:
                item = QTreeWidgetItem([leaf.label])
                item.setData(0, LEAF_ROLE, leaf)
                if leaf.input_file not in present:
                    # Visible but unusable: the stat exists, this campaign has not
                    # been parsed for it.
                    item.setForeground(0, grey)
                    item.setToolTip(0, f"{leaf.input_file} not found — parse this campaign first")
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                parent.addChild(item)
            self.tree.addTopLevelItem(parent)

    def _category_of(self, leaf):
        for category in self.categories:
            if leaf in category.leaves:
                return category
        return None

    # -- date range / slider ----------------------------------------------

    def _range(self):
        return self.start_year.value(), self.end_year.value()

    def _on_range_changed(self):
        start, end = self._range()
        if end < start:
            self.end_year.setValue(start)
        self.view.settings.set("Start Year", self.start_year.value())
        self.view.settings.set("End Year", self.end_year.value())
        self._clear_figure_cache()
        self._refresh_saves()
        self._render_current()

    def _reset_range(self):
        """Widen to every parsed save — the stored range may be narrower than disk."""
        if not self.campaign:
            return
        years = [year for _, year, _ in iter_save_folders(self.campaign, need_metadata=False)]
        if not years:
            self.status.setText("No parsed saves in this campaign.")
            return
        self.start_year.setValue(int(min(years)))
        self.end_year.setValue(int(max(years)) + 1)
        self._on_range_changed()

    def _refresh_saves(self):
        """Bound the slider to the saves inside the current year range."""
        start, end = self._range()
        self.saves = []
        if self.campaign:
            for folder, year, _ in iter_save_folders(self.campaign, start, end, need_metadata=False):
                self.saves.append((folder, year, os.path.basename(folder)))
        self.saves.sort(key=lambda entry: entry[1])
        self.date_slider.blockSignals(True)
        self.date_slider.setMaximum(max(0, len(self.saves) - 1))
        self.date_slider.setValue(max(0, len(self.saves) - 1))
        self.date_slider.blockSignals(False)
        self._update_date_label()

    def _current_save(self):
        if not self.saves:
            return None
        index = min(self.date_slider.value(), len(self.saves) - 1)
        return self.saves[index]

    def _update_date_label(self):
        current = self._current_save()
        self.date_label.setText(f"{current[1]:.2f}" if current else "—")

    def _on_date_changed(self, _value):
        self._update_date_label()
        self._load_table()
        self._draw_marker()

    def _on_players_toggled(self, _checked):
        self._clear_figure_cache()
        self._render_current()

    # -- selection ---------------------------------------------------------

    def _on_leaf_selected(self, current, _previous):
        leaf = current.data(0, LEAF_ROLE) if current is not None else None
        if leaf is None:
            return  # a category row: expand/collapse only
        self._current_leaf = leaf
        self._render_current()

    def _render_current(self):
        if self._current_leaf is None:
            return
        self._load_table()
        self._load_figures()

    def _load_table(self):
        """Show the whole category, with the plotted column first among the values.

        Seeing one number in isolation is rarely useful — literacy means more
        beside standard of living and population — so the table carries every
        sibling stat that shares the selected leaf's CSV.
        """
        leaf = self._current_leaf
        current = self._current_save()
        if leaf is None or current is None:
            self.table_model.set_frame(pd.DataFrame())
            return
        path = os.path.join(current[0], leaf.input_file)
        if not os.path.isfile(path):
            self.table_model.set_frame(pd.DataFrame())
            self.status.setText(f"{leaf.input_file} missing at {current[2]}")
            return
        frame = pd.read_csv(path)

        identity = [c for c in IDENTITY_COLUMNS if c in frame.columns]
        category = self._category_of(leaf)
        siblings = []
        if category is not None:
            siblings = [
                other.column for other in category.leaves
                if other.input_file == leaf.input_file
                and other.column in frame.columns
                and other.column != leaf.column
            ]
        values = ([leaf.column] if leaf.column in frame.columns else []) + siblings
        if values:
            frame = frame[identity + values]
        self.table_model.set_frame(frame)
        self.table.resizeColumnsToContents()

    def _load_figures(self):
        leaf = self._current_leaf
        start, end = self._range()
        key = (leaf.column, leaf.input_file, self.players_only.isChecked(), start, end)
        if key not in self._figure_cache:
            self.status.setText(f"Rendering {leaf.label}…")
            with busy():
                try:
                    self._figure_cache[key] = figures_for(
                        self.campaign, leaf.column, leaf.input_file,
                        players=self.players_only.isChecked(),
                        start_date=start, end_date=end, figsize=CANVAS_FIGSIZE,
                    )
                except Exception as e:
                    self._figure_cache[key] = []
                    self.status.setText(f"Could not plot {leaf.label}: {e}")
        self._figures = self._figure_cache[key]

        self.figure_combo.blockSignals(True)
        self.figure_combo.clear()
        self.figure_combo.addItems(self._figure_names(leaf))
        self.figure_combo.blockSignals(False)
        self.figure_combo.setEnabled(len(self._figures) > 1)
        self._show_figure(0)
        if self._figures:
            self.status.setText(f"{leaf.label} — {len(self.saves)} saves in {start}–{end}")

    def _figure_names(self, leaf):
        """Read each figure's own label rather than inferring it from position.

        A company stat yields one figure per *non-empty* level band plus a
        leaderboard, so the Nth figure is not the Nth band — labelling by index
        mislabels the picker and, worse, sends Save overwrite to another band's
        filename.
        """
        return [getattr(fig, "garibaldi_name", leaf.label) for fig in self._figures]

    def _show_figure(self, index):
        if not self._figures:
            self._show_mount(self._blank)
            self.canvas.draw_idle()
            return
        index = max(0, min(index, len(self._figures) - 1))
        self._set_figure(self._figures[index])
        self._draw_marker()

    def _draw_marker(self):
        """Mark the slider's date on the plot, so table and graph agree.

        The marker is tracked on the figure rather than on the page: figures now
        outlive a selection, so each keeps its own line to remove.
        """
        current = self._current_save()
        figure = getattr(self.canvas, "figure", None)
        if figure is None or not figure.get_axes():
            return
        ax = figure.get_axes()[0]
        marker = getattr(figure, "garibaldi_marker", None)
        if marker is not None:
            try:
                marker.remove()
            except (ValueError, NotImplementedError):
                pass
        figure.garibaldi_marker = None
        if current is not None:
            figure.garibaldi_marker = ax.axvline(
                current[1], color="black", linestyle=":", linewidth=1.5
            )
        self._marker = figure.garibaldi_marker
        self.canvas.draw_idle()

    # -- saving ------------------------------------------------------------

    def _current_figure(self):
        if not self._figures:
            return None
        return self._figures[max(0, min(self.figure_combo.currentIndex(), len(self._figures) - 1))]

    def _default_path(self):
        """Where the batch pass would have written this figure.

        The filename stem comes from the figure itself, for the same reason its
        display name does: skipped company bands make position meaningless.
        """
        leaf = self._current_leaf
        stem = leaf.input_file.replace(".csv", "")
        folder = os.path.join("saves", self.campaign, "campaign_data", stem)
        figure = self._current_figure()
        suffix = getattr(figure, "garibaldi_suffix", None) if figure is not None else None
        if leaf.input_file == "companies.csv":
            return os.path.join(folder, f"{leaf.column}_{suffix or 'plot'}.png")
        return os.path.join(folder, f"{suffix or leaf.column}.png")

    def _save_overwrite(self):
        figure = self._current_figure()
        if figure is None:
            self.status.setText("Nothing to save.")
            return
        path = self._default_path()
        if os.path.exists(path):
            confirm = QMessageBox.question(self, "Overwrite?", f"Replace {path}?")
            if confirm != QMessageBox.Yes:
                return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        figure.savefig(path)
        self.status.setText(f"Saved {path}")

    def _save_somewhere(self):
        figure = self._current_figure()
        if figure is None:
            self.status.setText("Nothing to save.")
            return
        with busy():
            path, _ = QFileDialog.getSaveFileName(
                self, "Save plot", os.path.basename(self._default_path()), "PNG image (*.png)"
            )
        if not path:
            return
        figure.savefig(path)
        self.status.setText(f"Saved {path}")
