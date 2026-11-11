"""
A fixed colour scheme, so the GUI looks the same on every machine.

By default Qt takes its colours from the operating system: the dark/light
setting, a Windows high-contrast theme, a KDE/GTK theme, a Qt style plugin such as
Kvantum or qt6ct. Garibaldi hard-codes a few colours of its own (the amber thread
warning, the greyed-out derived paths, the grey rows in the statistics table) and
draws matplotlib figures on a white background. Those assume a light surface, so a
dark system theme can leave text unreadable.

``apply_theme`` pins three things, in this order — each later step would be undone
by the one before it if the order changed:

1. the *style* to Fusion, which is drawn by Qt itself and honours the palette on
   every OS (the native Windows 11 and macOS styles ignore parts of it);
2. the *colour scheme* to light, which also stops the OS from restyling the window
   frame and from re-applying its own palette when the user flips dark mode while
   Garibaldi is running;
3. the *palette* to an explicit one that sets every role, so nothing is left to be
   filled in from the system.

Call it once, right after the ``QApplication`` is created and before any widget.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

# Every role, in all three groups (active / inactive / disabled). Inactive matches
# active on purpose: a selection must stay readable in a window that lost focus.
_ROLES = {
    QPalette.Window: "#f0f0f0",
    QPalette.WindowText: "#1a1a1a",
    QPalette.Base: "#ffffff",
    QPalette.AlternateBase: "#f4f4f4",
    QPalette.Text: "#1a1a1a",
    QPalette.PlaceholderText: "#6e6e6e",
    QPalette.Button: "#e6e6e6",
    QPalette.ButtonText: "#1a1a1a",
    QPalette.BrightText: "#ffffff",
    QPalette.ToolTipBase: "#ffffdc",
    QPalette.ToolTipText: "#1a1a1a",
    QPalette.Highlight: "#2a82da",
    QPalette.HighlightedText: "#ffffff",
    QPalette.Accent: "#2a82da",
    QPalette.Link: "#0b57d0",
    QPalette.LinkVisited: "#6a1b9a",
    # Bevel and frame shades Fusion derives its borders and sliders from.
    QPalette.Light: "#ffffff",
    QPalette.Midlight: "#f5f5f5",
    QPalette.Mid: "#c4c4c4",
    QPalette.Dark: "#9a9a9a",
    QPalette.Shadow: "#6b6b6b",
}

# Disabled widgets: dimmed but still legible (the busy state freezes controls).
_DISABLED = {
    QPalette.WindowText: "#7d7d7d",
    QPalette.Text: "#7d7d7d",
    QPalette.ButtonText: "#7d7d7d",
    QPalette.PlaceholderText: "#a0a0a0",
    QPalette.Base: "#f0f0f0",
    QPalette.Button: "#ececec",
    QPalette.Highlight: "#c8c8c8",
    QPalette.HighlightedText: "#7d7d7d",
    QPalette.Accent: "#c8c8c8",
}


def build_palette():
    """The explicit light palette, every role set in every group."""
    palette = QPalette()
    for role, colour in _ROLES.items():
        palette.setColor(role, QColor(colour))
    for role, colour in _DISABLED.items():
        palette.setColor(QPalette.Disabled, role, QColor(colour))
    return palette


def apply_theme(app):
    """Make ``app`` ignore the system theme. See the module docstring for the order."""
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(build_palette())
