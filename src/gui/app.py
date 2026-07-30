"""
Application bootstrap and the launcher window (W0).

The launcher spawns Process, View and Config as separate top-level windows —
one instance of each, re-focused if it is already open. It stays enabled while
they are open; what disables controls now is the app-wide busy state, not the
presence of a child window.
"""

import multiprocessing
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from src.gui.busy import busy_controller, find_freezable

BUTTON_SIZE = (200, 120)


class Launcher(QMainWindow):
    """Garibaldi's front door."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Garibaldi")
        # Shared with every worker so closing the launcher tears them all down.
        self.stop_event = multiprocessing.Event()
        self.stop_event.clear()
        self._windows = {}

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(50, 20, 50, 20)
        layout.setSpacing(10)
        for label, factory in (
            ("Process", self._make_process),
            ("View", self._make_view),
            ("Config", self._make_config),
        ):
            button = QPushButton(label)
            button.setFixedSize(*BUTTON_SIZE)
            button.clicked.connect(lambda _=False, f=factory, k=label: self.spawn(k, f))
            layout.addWidget(button, alignment=Qt.AlignHCenter)
        self.setCentralWidget(central)

        busy_controller.register(self)

    def freezable_widgets(self):
        return find_freezable(self)

    # -- window spawning ---------------------------------------------------

    def spawn(self, key, factory):
        """Open a window, or raise the existing one."""
        window = self._windows.get(key)
        if window is not None and window.isVisible():
            window.raise_()
            window.activateWindow()
            return window
        window = factory()
        window.destroyed.connect(lambda _=None, k=key: self._windows.pop(k, None))
        self._windows[key] = window
        window.show()
        return window

    def _make_process(self):
        from src.gui.process import ProcessWindow

        return ProcessWindow(self.stop_event)

    def _make_view(self):
        from src.gui.view import ViewWindow

        return ViewWindow()

    def _make_config(self):
        from src.gui.config import ConfigWindow

        return ConfigWindow()

    # -- shutdown ----------------------------------------------------------

    def closeEvent(self, event):
        """Tear down every worker and child window (as the tkinter app did)."""
        self.stop_event.set()
        for window in list(self._windows.values()):
            try:
                window.close()
            except RuntimeError:
                pass
        self._windows.clear()
        busy_controller.unregister(self)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    launcher = Launcher()
    launcher.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
