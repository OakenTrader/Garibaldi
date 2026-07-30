"""
Savefile picker (P1) — choose a save and one of its extracted blobs.

Replaces DictViewer's free-form "File location" + Browse with two constrained
dropdowns, so a file outside the campaign can no longer be picked by accident.
That also retires the "Tree File Location" setting.
"""

import os

from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)

from src.helpers.utility import is_reserved_folder

# zopen sniffs magic bytes, so both the current zstandard blobs and legacy gzip
# ones are readable.
BLOB_SUFFIXES = (".zst", ".gz")


class SavefilePage(QWidget):
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Select save:"), 0, 0)
        self.save_combo = QComboBox()
        self.save_combo.currentTextChanged.connect(self._on_save_changed)
        grid.addWidget(self.save_combo, 0, 1)

        grid.addWidget(QLabel("Select file:"), 1, 0)
        self.file_combo = QComboBox()
        grid.addWidget(self.file_combo, 1, 1)

        grid.addWidget(QLabel("Get object size:"), 2, 0)
        size_row = QHBoxLayout()
        self.size_yes = QRadioButton("Yes")
        self.size_no = QRadioButton("No")
        self.size_no.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.size_yes)
        group.addButton(self.size_no)
        size_row.addWidget(self.size_yes)
        size_row.addWidget(self.size_no)
        size_row.addStretch(1)
        grid.addLayout(size_row, 2, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self.go_button = QPushButton("Go")
        self.go_button.clicked.connect(self._on_go)
        buttons.addWidget(self.go_button)
        buttons.addStretch(1)
        back = QPushButton("Back")
        back.clicked.connect(self.view.go_menu)
        buttons.addWidget(back)
        layout.addLayout(buttons)
        layout.addStretch(1)

    def refresh(self):
        """Repopulate for the current campaign, keeping the selection if it survives."""
        campaign = self.view.campaign()
        previous = self.save_combo.currentText()
        root = os.path.join("saves", campaign)
        try:
            saves = sorted(
                name for name in os.listdir(root)
                if os.path.isdir(os.path.join(root, name)) and not is_reserved_folder(name)
            )
        except OSError:
            saves = []
        self.save_combo.blockSignals(True)
        self.save_combo.clear()
        self.save_combo.addItems(saves)
        if previous in saves:
            self.save_combo.setCurrentText(previous)
        self.save_combo.blockSignals(False)
        self._on_save_changed(self.save_combo.currentText())

    def _on_save_changed(self, save_name):
        previous = self.file_combo.currentText()
        self.file_combo.clear()
        if not save_name:
            self.go_button.setEnabled(False)
            return
        blob_dir = os.path.join("saves", self.view.campaign(), save_name, "extracted_save")
        try:
            files = sorted(f for f in os.listdir(blob_dir) if f.endswith(BLOB_SUFFIXES))
        except OSError:
            files = []
        self.file_combo.addItems(files)
        if previous in files:
            self.file_combo.setCurrentText(previous)
        self.go_button.setEnabled(bool(files))

    def selected_path(self):
        save_name = self.save_combo.currentText()
        file_name = self.file_combo.currentText()
        if not save_name or not file_name:
            return None
        return os.path.join("saves", self.view.campaign(), save_name, "extracted_save", file_name)

    def _on_go(self):
        path = self.selected_path()
        if path:
            self.view.show_tree(path, show_size=self.size_yes.isChecked())
