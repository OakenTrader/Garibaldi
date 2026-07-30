"""
Shared foundation for the Qt windows: settings persistence and a window base
class providing path browsing and participation in the app-wide freeze.

The settings half is a straight port of ``Garibaldi_gui``'s ``get_var`` /
``set_var`` / ``save_settings`` — they never depended on tkinter. Paths stay
relative to the process working directory, as before, so the app must be launched
from the project root.
"""

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLineEdit, QWidget

from src.gui.busy import busy, busy_controller, find_freezable
from src.helpers.utility import jopen

VARIABLES_FILE = "./src/variables.json"
USER_VARIABLES_FILE = "./user_variables.json"


class Settings:
    """The user_variables.json store, shared by every window."""

    def __init__(self):
        self.variables = jopen(VARIABLES_FILE)
        self.defaults = self.variables["default_directories"]
        try:
            self.user_variables = jopen(USER_VARIABLES_FILE)
        except (FileNotFoundError, json.JSONDecodeError):
            self.user_variables = self.defaults.copy()
        if self._migrate():
            self.save()

    def _migrate(self):
        """Bring an older user_variables.json up to the current schema.

        Returns whether anything changed. Kept here rather than in the Config
        window so a migrated file is never read half-converted by another window.
        """
        changed = False
        # "Mods Directory" (single path) became "Mod Directories" (a list).
        legacy = self.user_variables.pop("Mods Directory", None)
        if legacy is not None:
            changed = True
            if "Mod Directories" not in self.user_variables:
                self.user_variables["Mod Directories"] = [legacy] if legacy else []
        # "Tree File Location" is unused now that the save viewer uses dropdowns.
        if self.user_variables.pop("Tree File Location", None) is not None:
            changed = True
        if self._infer_steamapp_location():
            changed = True
        return changed

    def _infer_steamapp_location(self):
        """Back-fill "Steamapp Location" from an existing Common Directory.

        Config presents the three directory keys as *derived from* the Steamapp
        location unless explicitly overridden. An upgraded config has real paths
        but no Steamapp location, so without this they would look derived from
        nothing — and resetting a row would replace a working path with the
        "./common" shipped default. Inferring the root keeps that display honest.
        """
        if self.user_variables.get("Steamapp Location"):
            return False
        common = str(self.user_variables.get("Common Directory", ""))
        suffix = os.path.join("game", "common")
        if not common.endswith(suffix):
            return False
        root = common[: -len(suffix)].rstrip("/\\")
        if not root:
            return False
        self.user_variables["Steamapp Location"] = root
        return True

    def get(self, key):
        """Read a user variable, falling back to (and recording) the default."""
        if key not in self.user_variables:
            self.set(key, self.defaults[key])
        return self.user_variables[key]

    def set(self, key, value):
        self.user_variables[key] = value
        self.save()

    def restore_default(self, key):
        self.set(key, self.defaults[key])
        return self.user_variables[key]

    def save(self):
        with open(USER_VARIABLES_FILE, "w") as file:
            json.dump(self.user_variables, file, indent=4)


settings = Settings()


class GaribaldiWindow(QWidget):
    """Base for the spawned top-level windows (Process, View, Config).

    Registers itself with the busy controller so its controls take part in the
    app-wide freeze, and offers the browse helpers every window needs. The tkinter
    ``is_browsing`` re-entrancy flag has no equivalent here: Qt's file dialogs are
    application-modal, so a second one cannot be opened.
    """

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window)
        self.setWindowTitle(title)
        self.settings = settings
        busy_controller.register(self)

    # -- freeze participation ---------------------------------------------

    def freezable_widgets(self):
        """Controls this window contributes to a freeze."""
        return find_freezable(self)

    def closeEvent(self, event):
        busy_controller.unregister(self)
        super().closeEvent(event)

    # -- settings-backed path pickers -------------------------------------

    def browse_folder(self, key, initial_dir=None, only_folder_name=False):
        """Pick a folder, store it under ``key``, and return the stored value.

        Returns None if the dialog was cancelled. ``only_folder_name`` stores just
        the final path component, which is how campaign folders are recorded.
        """
        if initial_dir is None:
            initial_dir = os.path.dirname(str(self.settings.get(key)))
        with busy():
            path = QFileDialog.getExistingDirectory(self, "Select folder", initial_dir)
        if not path:
            return None
        if only_folder_name:
            path = os.path.basename(path.rstrip("/\\"))
        self.settings.set(key, path)
        return path

    def browse_file(self, key, initial_dir=None):
        """Pick a file, store it under ``key``, and return the stored value."""
        if initial_dir is None:
            initial_dir = os.path.dirname(str(self.settings.get(key)))
        with busy():
            path, _ = QFileDialog.getOpenFileName(self, "Select file", initial_dir)
        if not path:
            return None
        self.settings.set(key, path)
        return path


def readonly_line_edit(text=""):
    """A path display: readable and selectable, never typed into directly."""
    entry = QLineEdit(str(text))
    entry.setReadOnly(True)
    entry.setCursorPosition(0)
    return entry
