"""
App-wide busy state: the successor to the tkinter ``toggle_tinkerable``.

While a watch or parse job runs, or while a file dialog is open, every control in
every registered window is disabled except the ones explicitly exempted (in
practice, the running job's Stop button). This is deliberately app-wide: starting
the watcher freezes the parse section too, which is what makes watching and
parsing mutually exclusive without any extra bookkeeping.

Two behaviours are carried over from ``toggle_tinkerable`` because getting them
wrong is subtle:

- **Save and restore, not blanket-enable.** A control that was *already* disabled
  for its own reasons (a Stop button before its job starts, the View buttons on an
  unparsed campaign) must still be disabled once the freeze lifts. Only controls
  this class actually disabled are re-enabled.
- **Re-entrancy.** ``toggle_tinkerable`` guarded with a single boolean, which
  cannot survive nesting. Here each ``begin`` pushes its own snapshot, so a browse
  dialog opened during a running job restores the job's exempt Stop button when it
  closes rather than leaving it dead.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSlider, QAbstractSpinBox,
    QComboBox, QLineEdit, QWidget,
)

# Widget classes considered interactive. Labels, layouts, canvases and the like are
# left alone: disabling them only greys out text without preventing anything.
FREEZABLE = (
    QAbstractButton, QComboBox, QLineEdit, QAbstractSlider, QAbstractSpinBox,
    QAbstractItemView,
)


def find_freezable(root):
    """Every interactive control under ``root``.

    PySide6's ``findChildren`` takes one type (PyQt's tuple overload does not
    exist here), so sweep for QWidget once and filter.
    """
    return [child for child in root.findChildren(QWidget) if isinstance(child, FREEZABLE)]


class BusyController(QObject):
    """Freezes and restores the controls of every registered window."""

    busy_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._windows = []
        self._stack = []

    # -- registration -----------------------------------------------------

    def register(self, window):
        """Register a window whose controls take part in the freeze."""
        if window not in self._windows:
            self._windows.append(window)
            # A window opened mid-freeze must not come up live.
            if self.is_busy:
                self._freeze_widgets(self._widgets_of(window), set(), self._stack[-1])

    def unregister(self, window):
        if window in self._windows:
            self._windows.remove(window)
        # Drop any snapshot entries belonging to it; its widgets are going away.
        for snapshot in self._stack:
            snapshot[:] = [(w, s) for w, s in snapshot if not _is_child_of(w, window)]

    @property
    def is_busy(self):
        return bool(self._stack)

    # -- freeze / restore -------------------------------------------------

    def begin(self, exempt=()):
        """Freeze every registered control except ``exempt``.

        Nestable: each call pushes a snapshot that its matching ``end`` restores.
        """
        exempt = set(exempt)
        snapshot = []
        for window in list(self._windows):
            self._freeze_widgets(self._widgets_of(window), exempt, snapshot)
        self._stack.append(snapshot)
        if len(self._stack) == 1:
            self.busy_changed.emit(True)

    def end(self):
        """Undo the most recent ``begin``."""
        if not self._stack:
            return
        for widget, was_enabled in self._stack.pop():
            try:
                widget.setEnabled(was_enabled)
            except RuntimeError:
                pass  # underlying C++ widget already destroyed
        if not self._stack:
            self.busy_changed.emit(False)

    def _widgets_of(self, window):
        try:
            getter = window.freezable_widgets
        except AttributeError:
            return find_freezable(window)
        return getter()

    @staticmethod
    def _freeze_widgets(widgets, exempt, snapshot):
        for widget in widgets:
            if widget in exempt:
                continue
            try:
                if not widget.isEnabled():
                    continue  # already disabled: leave it, and leave it out of the snapshot
                widget.setEnabled(False)
            except RuntimeError:
                continue
            snapshot.append((widget, True))


def _is_child_of(widget, window):
    try:
        parent = widget
        while parent is not None:
            if parent is window:
                return True
            parent = parent.parent()
    except RuntimeError:
        return True  # destroyed: drop it either way
    return False


class _BusyScope:
    """Context manager form, so a freeze cannot be left on by an early return."""

    def __init__(self, controller, exempt):
        self._controller = controller
        self._exempt = exempt

    def __enter__(self):
        self._controller.begin(self._exempt)
        return self._controller

    def __exit__(self, *exc_info):
        self._controller.end()
        return False


busy_controller = BusyController()


def busy(exempt=()):
    """``with busy(): ...`` — freeze for the duration of the block."""
    return _BusyScope(busy_controller, exempt)
