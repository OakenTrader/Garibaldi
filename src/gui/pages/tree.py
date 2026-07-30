"""
Tree view (P2) — browse an extracted save blob.

Two changes from the tkinter DictViewer, both about the size of the data (a
country_manager blob runs to tens of MB):

- **Lazy population.** ``populate_tree`` built every node up front, which is why
  opening the viewer took so long. Here a branch gets a placeholder child and is
  filled in the first time it is expanded.
- **Search over the data, not the widget.** Because the tree is lazy, searching
  visible items would only find what happens to be expanded. Instead the search
  walks the underlying Python object, then expands the path to each hit — so it
  finds keys that have never been rendered.

``get_size`` is memoised bottom-up, as the original's own TODO asked: the tkinter
version recomputed a subtree's size once per node, making it quadratic.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeView, QVBoxLayout, QWidget,
)

from src.helpers.utility import zopen

OBJECT_ROLE = Qt.UserRole + 1
PLACEHOLDER_ROLE = Qt.UserRole + 2
MAX_MATCHES = 500


def human_bytes(count):
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:.0f} {unit}" if unit == "B" else f"{count:.1f} {unit}"
        count /= 1024


class SizeCalculator:
    """Recursive object sizing with memoisation, keyed by object identity.

    Safe because the loaded blob is held for the lifetime of the page, so no id()
    can be recycled underneath the cache.
    """

    def __init__(self):
        self._cache = {}

    def size_of(self, obj):
        key = id(obj)
        if key in self._cache:
            return self._cache[key]
        if isinstance(obj, dict):
            total = sum(self.size_of(v) for v in obj.values())
        elif isinstance(obj, list):
            total = sum(self.size_of(v) for v in obj)
        else:
            total = sys.getsizeof(obj)
        self._cache[key] = total
        return total


def children_of(obj):
    """(key, value) pairs for a container, or None for a leaf."""
    if isinstance(obj, dict):
        return list(obj.items())
    if isinstance(obj, list):
        return list(enumerate(obj))
    return None


class TreePage(QWidget):
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.data = None
        self.show_size = False
        self.sizes = SizeCalculator()
        self._matches = []
        self._match_index = -1

        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Search:"))
        self.search_entry = QLineEdit()
        self.search_entry.returnPressed.connect(self.find_next)
        bar.addWidget(self.search_entry, 1)
        self.find_next_button = QPushButton("Find next")
        self.find_next_button.clicked.connect(self.find_next)
        bar.addWidget(self.find_next_button)
        self.find_prev_button = QPushButton("Find prev")
        self.find_prev_button.clicked.connect(self.find_prev)
        bar.addWidget(self.find_prev_button)
        collapse = QPushButton("Collapse all")
        collapse.clicked.connect(self._collapse_all)
        bar.addWidget(collapse)
        back = QPushButton("Back")
        back.clicked.connect(self.view.go_savefile)
        bar.addWidget(back)
        layout.addLayout(bar)

        self.tree = QTreeView()
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.expanded.connect(self._on_expanded)
        layout.addWidget(self.tree, 1)

        self.status = QLabel("")
        layout.addWidget(self.status)

    # -- loading -----------------------------------------------------------

    def load(self, path, show_size=False):
        self.show_size = show_size
        self.sizes = SizeCalculator()
        self.status.setText(f"Loading {path}…")
        self.data = zopen(path)

        model = QStandardItemModel()
        headers = ["Key", "Value"] + (["Size"] if show_size else [])
        model.setHorizontalHeaderLabels(headers)
        self._fill(model.invisibleRootItem(), self.data)
        self.tree.setModel(model)
        self.tree.setColumnWidth(0, 320)
        self.tree.setColumnWidth(1, 320)
        self._matches = []
        self._match_index = -1
        self.status.setText(f"{path} — {len(children_of(self.data) or [])} top-level entries")

    def _row_for(self, key, value):
        key_item = QStandardItem(str(key))
        key_item.setEditable(False)
        key_item.setData(value, OBJECT_ROLE)
        children = children_of(value)
        if children:
            value_item = QStandardItem("")
            # A placeholder keeps the expand arrow without building the subtree.
            key_item.appendRow([QStandardItem(""), QStandardItem("")])
            key_item.setData(True, PLACEHOLDER_ROLE)
        else:
            value_item = QStandardItem("" if children is not None else str(value))
        value_item.setEditable(False)
        row = [key_item, value_item]
        if self.show_size:
            size_item = QStandardItem(human_bytes(self.sizes.size_of(value)))
            size_item.setEditable(False)
            row.append(size_item)
        return row

    def _fill(self, parent_item, obj):
        for key, value in children_of(obj) or []:
            parent_item.appendRow(self._row_for(key, value))

    def _on_expanded(self, index):
        model = self.tree.model()
        item = model.itemFromIndex(index)
        if item is None or not item.data(PLACEHOLDER_ROLE):
            return
        item.setData(False, PLACEHOLDER_ROLE)
        item.removeRows(0, item.rowCount())
        self._fill(item, item.data(OBJECT_ROLE))

    def _collapse_all(self):
        self.tree.collapseAll()

    # -- search ------------------------------------------------------------

    def _walk(self, obj, query, path, out):
        """Collect paths whose key or leaf value contains ``query``."""
        for key, value in children_of(obj) or []:
            here = path + [key]
            if query in str(key).lower():
                out.append(here)
            elif children_of(value) is None and query in str(value).lower():
                out.append(here)
            if len(out) >= MAX_MATCHES:
                return
            if children_of(value) is not None:
                self._walk(value, query, here, out)
                if len(out) >= MAX_MATCHES:
                    return

    def _ensure_matches(self):
        query = self.search_entry.text().strip().lower()
        if not query or self.data is None:
            self._matches = []
            return False
        if getattr(self, "_query", None) != query:
            self._query = query
            self._matches = []
            self._walk(self.data, query, [], self._matches)
            self._match_index = -1
            capped = " (capped)" if len(self._matches) >= MAX_MATCHES else ""
            self.status.setText(f"{len(self._matches)} match(es) for '{query}'{capped}")
        return bool(self._matches)

    def find_next(self):
        if not self._ensure_matches():
            self.status.setText("No matches.")
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        self._reveal(self._matches[self._match_index])

    def find_prev(self):
        if not self._ensure_matches():
            self.status.setText("No matches.")
            return
        self._match_index = (self._match_index - 1) % len(self._matches)
        self._reveal(self._matches[self._match_index])

    def _reveal(self, path):
        """Expand down to a path, populating lazily as it goes, then select it."""
        model = self.tree.model()
        parent = model.invisibleRootItem()
        index = None
        for key in path:
            if parent.data(PLACEHOLDER_ROLE):
                parent.setData(False, PLACEHOLDER_ROLE)
                parent.removeRows(0, parent.rowCount())
                self._fill(parent, parent.data(OBJECT_ROLE))
            match = None
            for row in range(parent.rowCount()):
                child = parent.child(row, 0)
                if child is not None and child.text() == str(key):
                    match = child
                    break
            if match is None:
                return
            index = match.index()
            self.tree.expand(index)
            parent = match
        if index is not None:
            self.tree.setCurrentIndex(index)
            self.tree.scrollTo(index)
            self.status.setText(
                f"Match {self._match_index + 1}/{len(self._matches)}: "
                + " / ".join(str(p) for p in path)
            )
