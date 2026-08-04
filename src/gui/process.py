"""
Process window (W1) — save watching and parsing.

Collapses the tkinter SaveWatcher, SaveExtractor and SaveAnalyzer into one window.
Parsing runs extraction, then every checker, then the batch plot: checking is no
longer selective, so there is nothing to tick.

Watching and parsing are mutually exclusive. That is not enforced here — it falls
out of the app-wide freeze, which disables every control except the Stop button of
whichever job is running.
"""

import glob
import multiprocessing
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QProgressBar, QPushButton, QRadioButton, QSlider,
    QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from src.checkers.manager import all_check_keys, plot_results_job
from src.gui.base import GaribaldiWindow, readonly_line_edit
from src.gui.jobs import JobRunner, Phase
from src.helpers.extraction import parse_files
from src.helpers.save_watch import watch_save_job
from src.helpers.utility import is_reserved_folder

# Above this many worker processes the UI warns; the machine's core count is the cap.
THREAD_WARN_ABOVE = 4


def split_evenly(items, n):
    """Deal ``items`` round-robin into ``n`` lists, as the tkinter GUI did."""
    n = max(1, min(n, len(items) or 1))
    return [[item for j, item in enumerate(items) if j % n == i] for i in range(n)]


class ProcessWindow(GaribaldiWindow):
    def __init__(self, stop_event, parent=None):
        super().__init__("Process", parent)
        self.resize(820, 560)
        self.stop_event = stop_event
        self.runner = JobRunner(stop_event, self)
        self.runner.phase_started.connect(self._on_phase_started)
        self.runner.progress.connect(self._on_progress)
        self.runner.finished.connect(self._on_finished)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_campaign())
        layout.addWidget(self._build_watch())
        layout.addWidget(self._build_parse())
        layout.addWidget(self._build_progress())
        layout.addStretch(1)
        self.status = QStatusBar()
        layout.addWidget(self.status)

        self._refresh_campaigns()
        self.watch_stop.setEnabled(False)
        self.parse_stop.setEnabled(False)

    # -- campaign ----------------------------------------------------------

    def _build_campaign(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Select Campaign:"))
        from PySide6.QtWidgets import QComboBox

        self.campaign_combo = QComboBox()
        self.campaign_combo.currentTextChanged.connect(self._on_campaign_changed)
        row.addWidget(self.campaign_combo, 1)
        new = QPushButton("New…")
        new.clicked.connect(self._new_campaign)
        row.addWidget(new)
        return box

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
        elif campaigns:
            self.settings.set("Campaign Folder", campaigns[0])
        self.campaign_combo.blockSignals(False)

    def _on_campaign_changed(self, name):
        if name:
            self.settings.set("Campaign Folder", name)

    def _new_campaign(self):
        name, ok = QInputDialog.getText(self, "Create new campaign folder", "Folder name:")
        name = name.strip()
        if not ok or not name:
            return
        path = os.path.join("saves", name)
        if os.path.exists(path):
            QMessageBox.critical(self, "Error", "Folder already exists!")
            return
        os.makedirs(path)
        self.settings.set("Campaign Folder", name)
        self._refresh_campaigns()
        self.campaign_combo.setCurrentText(name)

    # -- watch -------------------------------------------------------------

    def _build_watch(self):
        box = QGroupBox("Watch")
        outer = QVBoxLayout(box)

        row = QHBoxLayout()
        row.addWidget(QLabel("Watch save:"))
        self.autosave_entry = readonly_line_edit(self.settings.get("Autosave Location"))
        row.addWidget(self.autosave_entry, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_autosave)
        row.addWidget(browse)
        outer.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Save every"))
        self.freq_spin = QSpinBox()
        self.freq_spin.setMinimum(1)
        self.freq_spin.setMaximum(999)
        self.freq_spin.setValue(1)
        row2.addWidget(self.freq_spin)
        row2.addWidget(QLabel("autosave(s)"))
        row2.addStretch(1)
        self.watch_start = QPushButton("Start")
        self.watch_start.clicked.connect(self._start_watch)
        row2.addWidget(self.watch_start)
        self.watch_stop = QPushButton("Stop")
        self.watch_stop.clicked.connect(self.runner.stop)
        row2.addWidget(self.watch_stop)
        outer.addLayout(row2)
        return box

    def _browse_autosave(self):
        path = self.browse_file("Autosave Location")
        if path is not None:
            self.autosave_entry.setText(path)

    def _start_watch(self):
        target = str(self.settings.get("Autosave Location"))
        if not target or not os.path.isfile(target):
            QMessageBox.critical(self, "Error", "Set a valid autosave location first (Config, or Browse above).")
            return
        campaign = self.campaign_combo.currentText()
        if not campaign:
            QMessageBox.critical(self, "Error", "Select a campaign folder first.")
            return
        freq = self.freq_spin.value()

        def build(stop_event, queue):
            finish_event = multiprocessing.Event()
            process = multiprocessing.Process(
                target=watch_save_job,
                args=(target, campaign, stop_event, finish_event, queue, freq),
            )
            return [process], [finish_event], 0

        self._current_job = "watch"
        self.runner.start([Phase("Watching", build)], exempt=[self.watch_stop])
        self.watch_stop.setEnabled(True)

    # -- parse -------------------------------------------------------------

    def _build_parse(self):
        box = QGroupBox("Parse")
        grid = QGridLayout(box)

        grid.addWidget(QLabel("Delete autosave after successful parse:"), 0, 0)
        delete_row = QHBoxLayout()
        self.delete_yes = QRadioButton("Yes")
        self.delete_no = QRadioButton("No")
        self.delete_no.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.delete_yes)
        group.addButton(self.delete_no)
        delete_row.addWidget(self.delete_yes)
        delete_row.addWidget(self.delete_no)
        delete_row.addStretch(1)
        grid.addLayout(delete_row, 0, 1)

        cores = os.cpu_count() or 1
        grid.addWidget(QLabel("Threads:"), 1, 0)
        thread_row = QHBoxLayout()
        thread_row.addWidget(QLabel("1"))
        self.thread_slider = QSlider(Qt.Horizontal)
        self.thread_slider.setMinimum(1)
        self.thread_slider.setMaximum(cores)
        self.thread_slider.setValue(1)
        self.thread_slider.setTickInterval(1)
        self.thread_slider.setTickPosition(QSlider.TicksBelow)
        self.thread_slider.valueChanged.connect(self._on_threads_changed)
        thread_row.addWidget(self.thread_slider, 1)
        thread_row.addWidget(QLabel(f"All ({cores})"))
        self.thread_value = QLabel("1")
        thread_row.addWidget(self.thread_value)
        grid.addLayout(thread_row, 1, 1)

        self.thread_warning = QLabel(f"⚠ above {THREAD_WARN_ABOVE} threads: at your own risk")
        self.thread_warning.setStyleSheet("color: #b36b00;")
        self.thread_warning.setVisible(False)
        grid.addWidget(self.thread_warning, 2, 1)

        # Restored from the old Analyze window, in the position it held there:
        # directly above Start/Stop.
        year_row = QHBoxLayout()
        year_row.addWidget(QLabel("Start year"))
        self.start_year = QSpinBox()
        self.start_year.setRange(1, 9999)
        self.start_year.setValue(int(self.settings.get("Start Year")))
        self.start_year.valueChanged.connect(lambda v: self.settings.set("Start Year", v))
        year_row.addWidget(self.start_year)
        year_row.addSpacing(20)
        year_row.addWidget(QLabel("End year"))
        self.end_year = QSpinBox()
        self.end_year.setRange(1, 9999)
        self.end_year.setValue(int(self.settings.get("End Year")))
        self.end_year.valueChanged.connect(lambda v: self.settings.set("End Year", v))
        year_row.addWidget(self.end_year)
        year_row.addStretch(1)
        grid.addLayout(year_row, 3, 1)

        button_row = QHBoxLayout()
        self.parse_start = QPushButton("Start")
        self.parse_start.clicked.connect(self._start_parse)
        button_row.addWidget(self.parse_start)
        button_row.addStretch(1)
        self.parse_stop = QPushButton("Stop")
        self.parse_stop.clicked.connect(self.runner.stop)
        button_row.addWidget(self.parse_stop)
        grid.addLayout(button_row, 4, 1)
        grid.setColumnStretch(1, 1)
        return box

    def _on_threads_changed(self, value):
        self.thread_value.setText(str(value))
        self.thread_warning.setVisible(value > THREAD_WARN_ABOVE)

    def _start_parse(self):
        campaign = self.campaign_combo.currentText()
        if not campaign:
            QMessageBox.critical(self, "Error", "Select a campaign folder first.")
            return
        start_year = self.start_year.value()
        end_year = self.end_year.value()
        if end_year < start_year:
            QMessageBox.critical(self, "Error", "End year must not be before start year.")
            return
        delete = self.delete_yes.isChecked()
        if delete:
            proceed = QMessageBox.question(
                self, "Wait a sec",
                "Save files will be deleted after being successfully extracted. Proceed?",
            )
            if proceed != QMessageBox.Yes:
                return
        threads = self.thread_slider.value()
        checks = all_check_keys()

        def build_parse(stop_event, queue):
            # Extraction and checking run as one phase, so the parsed tree goes
            # straight to the checkers.
            #
            # Targets are raw .v3 files and existing save folders alike; a folder with
            # nothing left to melt is still checked, from its cached blobs.
            #
            # Year filtering happens inside the worker, since a raw
            # autosave_<timestamp>.v3 carries no date until melted.
            targets = glob.glob(f"./saves/{campaign}/*.v3") + glob.glob(f"./saves/{campaign}/*/")
            targets = [t for t in targets if not is_reserved_folder(t)]
            processes, events = [], []
            for subset in split_evenly(targets, threads):
                if not subset:
                    continue
                event = multiprocessing.Event()
                events.append(event)
                processes.append(multiprocessing.Process(
                    target=parse_files,
                    args=(campaign, subset, checks, stop_event, event, queue, delete,
                          start_year, end_year),
                ))
            return processes, events, len(targets)

        def build_plot(stop_event, queue):
            # The reduction: reads across every save, so exactly one process.
            event = multiprocessing.Event()
            process = multiprocessing.Process(
                target=plot_results_job,
                args=(checks, campaign, start_year, end_year, stop_event, event, queue),
            )
            return [process], [event], 1

        self._current_job = "parse"
        self.runner.start([
            Phase("Parsing", build_parse),
            Phase("Plotting", build_plot),
        ], exempt=[self.parse_stop])
        self.parse_stop.setEnabled(True)

    # -- progress ----------------------------------------------------------

    def _build_progress(self):
        box = QGroupBox("Progress")
        grid = QGridLayout(box)
        self.progress_label = QLabel("Idle")
        grid.addWidget(self.progress_label, 0, 0)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        grid.addWidget(self.progress_bar, 0, 1)
        grid.setColumnStretch(1, 1)
        return box

    def _on_phase_started(self, label, total):
        self.progress_label.setText(label)
        # total == 0 means open-ended (the watcher): show a busy indicator.
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.status.showMessage(f"{label}…")

    def _on_progress(self, label, done, total):
        if total:
            self.progress_bar.setValue(min(done, total))
            self.progress_label.setText(f"{label} {done}/{total}")
        else:
            self.progress_label.setText(f"{label} — {done} copied")

    def _on_finished(self, ok, message):
        self.watch_stop.setEnabled(False)
        self.parse_stop.setEnabled(False)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(1 if ok else 0)
        self.progress_label.setText("Done" if ok else "Stopped")
        if ok:
            self.status.showMessage("Finished.", 8000)
        else:
            self.status.showMessage(message, 12000)
            if message and not message.startswith("Stopped"):
                QMessageBox.warning(self, "Job ended", message)

    # -- shutdown ----------------------------------------------------------

    def closeEvent(self, event):
        self.runner.shutdown()
        super().closeEvent(event)
