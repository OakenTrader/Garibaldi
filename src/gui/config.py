"""
Config window (W3) — game paths, localization language, mod folders.

Settings persist the moment they change; there is no Apply button, matching the
tkinter behaviour and the schematic.

One constraint shapes the whole window: ``load_def_multiple`` (utility.py:100)
re-reads ``user_variables.json`` from disk inside worker processes and indexes it
as ``user_variables["Common Directory"]``. So those three keys must *always* hold
a usable path. "Derived from the Steamapp location" is therefore not a special
empty value — the derived path is written into the key, and a separate
``Overridden Directories`` list records which ones the user has pointed elsewhere.
"""

import json
import os

from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from src.gui.base import GaribaldiWindow, readonly_line_edit

# Where each override lives underneath the Steamapp location.
DERIVED_SUBPATHS = {
    "Common Directory": os.path.join("game", "common"),
    "Events Directory": os.path.join("game", "events"),
    "Localization Directory": os.path.join("game", "localization"),
}

FALLBACK_LANGUAGES = [
    "english", "french", "german", "spanish", "polish",
    "braz_por", "russian", "simp_chinese", "japanese", "korean", "turkish",
]


class ConfigWindow(GaribaldiWindow):
    def __init__(self, parent=None):
        super().__init__("Config", parent)
        self.resize(760, 520)
        self._override_entries = {}
        self._mod_rows = []

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_steamapp())
        layout.addWidget(self._build_overrides())
        layout.addWidget(self._build_language())
        layout.addWidget(self._build_mod_folders())
        layout.addWidget(self._build_mod_selector())
        layout.addWidget(self._build_autosave())
        layout.addStretch(1)
        self.status = QStatusBar()
        layout.addWidget(self.status)

        self._refresh_overrides()
        self._refresh_languages()
        self._refresh_mod_list()

    # -- Steamapp location -------------------------------------------------

    def _build_steamapp(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Steamapp location:"))
        self.steamapp_entry = readonly_line_edit(self.settings.get("Steamapp Location"))
        row.addWidget(self.steamapp_entry, 1)
        button = QPushButton("Browse")
        button.clicked.connect(self._browse_steamapp)
        row.addWidget(button)
        return box

    def _browse_steamapp(self):
        path = self.browse_folder("Steamapp Location")
        if path is None:
            return
        self.steamapp_entry.setText(path)
        self._apply_derived()
        self._refresh_overrides()
        self._refresh_languages()
        self.status.showMessage(f"Steamapp location set to {path}", 5000)

    def _derived(self, key):
        root = self.settings.get("Steamapp Location")
        return os.path.join(root, DERIVED_SUBPATHS[key]) if root else ""

    def _overridden(self):
        return list(self.settings.get("Overridden Directories"))

    def _apply_derived(self):
        """Write the derived path into every override key the user has not claimed."""
        overridden = self._overridden()
        for key in DERIVED_SUBPATHS:
            if key in overridden:
                continue
            derived = self._derived(key)
            if derived:
                self.settings.set(key, derived)

    # -- Override rows -----------------------------------------------------

    def _build_overrides(self):
        box = QGroupBox("Override")
        grid = QGridLayout(box)
        for row, key in enumerate(DERIVED_SUBPATHS):
            label = key.replace(" Directory", "").lower()
            grid.addWidget(QLabel(label), row, 0)
            entry = readonly_line_edit(self.settings.get(key))
            self._override_entries[key] = entry
            grid.addWidget(entry, row, 1)
            browse = QPushButton("Browse")
            browse.clicked.connect(lambda _=False, k=key: self._browse_override(k))
            grid.addWidget(browse, row, 2)
            reset = QPushButton("Reset")
            reset.clicked.connect(lambda _=False, k=key: self._reset_override(k))
            grid.addWidget(reset, row, 3)
        grid.setColumnStretch(1, 1)
        return box

    def _browse_override(self, key):
        path = self.browse_folder(key)
        if path is None:
            return
        overridden = self._overridden()
        if key not in overridden:
            overridden.append(key)
            self.settings.set("Overridden Directories", overridden)
        self._refresh_overrides()
        if key == "Localization Directory":
            self._refresh_languages()
        self.status.showMessage(f"{key} overridden", 5000)

    def _reset_override(self, key):
        """Drop the override and fall back to the Steamapp-derived path.

        Refuses when there is no Steamapp location to derive from: falling back to
        the shipped "./common" default would silently replace a working path with
        one that resolves nowhere.
        """
        derived = self._derived(key)
        if not derived:
            self.status.showMessage(
                "Set a Steamapp location before resetting — there is nothing to derive from.", 8000
            )
            return
        overridden = [k for k in self._overridden() if k != key]
        self.settings.set("Overridden Directories", overridden)
        self.settings.set(key, derived)
        self._refresh_overrides()
        if key == "Localization Directory":
            self._refresh_languages()
        self.status.showMessage(f"{key} reset", 5000)

    def _refresh_overrides(self):
        """Show each effective path, greyed out where it is merely derived."""
        overridden = self._overridden()
        for key, entry in self._override_entries.items():
            entry.setText(str(self.settings.get(key)))
            entry.setCursorPosition(0)
            is_derived = key not in overridden
            entry.setFrame(not is_derived)
            entry.setStyleSheet("color: gray;" if is_derived else "")
            entry.setToolTip("Derived from the Steamapp location" if is_derived else "Overridden")

    # -- Localization language --------------------------------------------

    def _build_language(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Localization language:"))
        self.language_combo = QComboBox()
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        row.addWidget(self.language_combo, 1)
        return box

    def _refresh_languages(self):
        """List the language folders actually present, so a mod's extra languages show up."""
        directory = str(self.settings.get("Localization Directory"))
        try:
            languages = sorted(
                name for name in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, name))
            )
        except OSError:
            languages = []
        if not languages:
            languages = FALLBACK_LANGUAGES
        current = str(self.settings.get("Localization Language"))
        if current and current not in languages:
            languages = [current] + languages
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItems(languages)
        if current in languages:
            self.language_combo.setCurrentText(current)
        self.language_combo.blockSignals(False)

    def _on_language_changed(self, value):
        if value:
            self.settings.set("Localization Language", value)

    # -- Mod folders -------------------------------------------------------

    def _build_mod_folders(self):
        box = QGroupBox("More mod folder locations")
        outer = QVBoxLayout(box)
        self._mod_folder_container = QVBoxLayout()
        outer.addLayout(self._mod_folder_container)
        add = QPushButton("+ Add Folder")
        add.clicked.connect(self._add_mod_folder)
        outer.addWidget(add)
        self._rebuild_mod_folder_rows()
        return box

    def _mod_directories(self):
        value = self.settings.get("Mod Directories")
        return list(value) if isinstance(value, list) else [value] if value else []

    def _rebuild_mod_folder_rows(self):
        while self._mod_folder_container.count():
            item = self._mod_folder_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._mod_rows = []
        for index, path in enumerate(self._mod_directories()):
            self._mod_folder_container.addWidget(self._mod_folder_row(index, path))

    def _mod_folder_row(self, index, path):
        frame = QFrame()
        row = QHBoxLayout(frame)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(f"Folder {index + 1}"))
        entry = readonly_line_edit(path)
        row.addWidget(entry, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(lambda _=False, i=index: self._browse_mod_folder(i))
        row.addWidget(browse)
        remove = QPushButton("✕")
        remove.setFixedWidth(32)
        remove.clicked.connect(lambda _=False, i=index: self._remove_mod_folder(i))
        row.addWidget(remove)
        self._mod_rows.append(entry)
        return frame

    def _add_mod_folder(self):
        directories = self._mod_directories()
        directories.append("")
        self.settings.set("Mod Directories", directories)
        self._rebuild_mod_folder_rows()

    def _browse_mod_folder(self, index):
        directories = self._mod_directories()
        initial = os.path.dirname(directories[index]) if directories[index] else ""
        # Not browse_folder(): these live in a list, not under a settings key.
        from PySide6.QtWidgets import QFileDialog

        from src.gui.busy import busy

        with busy():
            path = QFileDialog.getExistingDirectory(self, "Select mod folder", initial)
        if not path:
            return
        directories[index] = path
        self.settings.set("Mod Directories", directories)
        self._rebuild_mod_folder_rows()
        self._refresh_mod_list()

    def _remove_mod_folder(self, index):
        directories = self._mod_directories()
        if 0 <= index < len(directories):
            directories.pop(index)
            self.settings.set("Mod Directories", directories)
            self._rebuild_mod_folder_rows()
            self._refresh_mod_list()

    # -- Mod selection -----------------------------------------------------

    def _build_mod_selector(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Select mod:"))
        self.mod_combo = QComboBox()
        self.mod_combo.currentTextChanged.connect(self._on_mod_selected)
        row.addWidget(self.mod_combo, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_mod_list)
        row.addWidget(refresh)
        return box

    def _scan_mods(self):
        """Map display label -> mod folder, across every configured mod directory.

        Port of ``Configure_windows.get_mod``: a mod is a folder carrying
        ``.metadata/metadata.json``, labelled ``"<folder> - <name>"`` when that
        file names it.
        """
        mods = {}
        for directory in self._mod_directories():
            if not directory or not os.path.isdir(directory):
                continue
            for folder in sorted(os.listdir(directory)):
                folder_dir = os.path.join(directory, folder)
                if not os.path.isdir(folder_dir):
                    continue
                label = folder
                metadata_path = os.path.join(folder_dir, ".metadata", "metadata.json")
                if os.path.isfile(metadata_path):
                    try:
                        with open(metadata_path) as file:
                            metadata = json.load(file)
                        if "name" in metadata:
                            label = f"{folder} - {metadata['name']}"
                    except (OSError, json.JSONDecodeError):
                        pass
                mods[label] = folder_dir
        return mods

    def _refresh_mod_list(self):
        self.mods = self._scan_mods()
        selected = str(self.settings.get("Selected Mod"))
        label_for_selected = ""
        for label, path in self.mods.items():
            if selected and os.path.abspath(path) == os.path.abspath(selected):
                label_for_selected = label
                break
        self.mod_combo.blockSignals(True)
        self.mod_combo.clear()
        self.mod_combo.addItem("")  # no mod
        self.mod_combo.addItems(list(self.mods))
        self.mod_combo.setCurrentText(label_for_selected)
        self.mod_combo.setEnabled(bool(self.mods))
        self.mod_combo.blockSignals(False)
        if selected and not label_for_selected:
            # The stored mod is no longer on disk; don't leave a dangling path.
            self.settings.set("Selected Mod", "")

    def _on_mod_selected(self, label):
        self.settings.set("Selected Mod", self.mods.get(label, ""))

    # -- Autosave location -------------------------------------------------

    def _build_autosave(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Autosave location:"))
        self.autosave_entry = readonly_line_edit(self.settings.get("Autosave Location"))
        row.addWidget(self.autosave_entry, 1)
        button = QPushButton("Browse")
        button.clicked.connect(self._browse_autosave)
        row.addWidget(button)
        return box

    def _browse_autosave(self):
        path = self.browse_file("Autosave Location")
        if path is not None:
            self.autosave_entry.setText(path)
            self.status.showMessage(f"Autosave location set to {path}", 5000)
