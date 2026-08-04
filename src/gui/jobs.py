"""
Driving the multiprocessing backend from Qt.

The worker side is untouched: ``parse_files`` and ``plot_results_job`` both take
``(…, stop_event, finish_event, queue)`` and are run as plain
``multiprocessing.Process`` objects, exactly as the tkinter GUI ran them.
What changes is the supervision. The old code interleaved two ``after()`` loops —
``check_progress`` every second and ``end_task`` every half second — and each
window re-implemented joining, error handling and re-enabling its own controls.

Here one QTimer polls the queue and the finish events, and the runner emits
signals. Crucially it owns the app-wide freeze: ``begin`` on start and ``end`` in
every terminating path, so a freeze can never be left on by an early return or an
exception. That was the failure mode of ``toggle_tinkerable``, which had to be
re-called by hand on every branch.
"""

import multiprocessing

from PySide6.QtCore import QObject, QTimer, Signal

from src.gui.busy import busy_controller

POLL_MS = 500


class Phase:
    """One step of a job.

    ``build`` is called when the phase starts (not when the job is queued) and
    returns ``(processes, finish_events, total)``. Deferring it matters: the
    checking phase must enumerate save folders that the extraction phase creates.
    """

    def __init__(self, label, build):
        self.label = label
        self.build = build


class JobRunner(QObject):
    """Runs a sequence of phases, reporting progress and owning the busy state."""

    phase_started = Signal(str, int)      # label, total
    progress = Signal(str, int, int)      # label, done, total
    finished = Signal(bool, str)          # ok, error message ("" when ok)

    def __init__(self, stop_event, parent=None):
        super().__init__(parent)
        self.stop_event = stop_event
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._reset()

    def _reset(self):
        self._phases = []
        self._index = -1
        self._processes = []
        self._finish_events = []
        self._queue = None
        self._label = ""
        self._total = 0
        self._done = 0
        self._frozen = False
        self._stopping = False

    @property
    def is_running(self):
        return self._timer.isActive()

    # -- lifecycle ---------------------------------------------------------

    def start(self, phases, exempt=()):
        """Begin a job. ``exempt`` stays interactive — in practice, the Stop button.

        The first phase is entered on the next event-loop turn rather than inline.
        A job whose phases build no processes at all would otherwise run to
        completion inside this call and emit ``finished`` before the caller had
        returned, so anything connecting after ``start`` would never hear it.
        """
        if self.is_running:
            return False
        self._reset()
        self._phases = list(phases)
        self.stop_event.clear()
        busy_controller.begin(exempt=exempt)
        self._frozen = True
        self._timer.start()
        QTimer.singleShot(0, self._advance)
        return True

    def stop(self):
        """Ask the workers to wind up. They set finish events on their way out."""
        self._stopping = True
        self.stop_event.set()

    def _advance(self):
        """Move to the next phase. Returns False once the job is over."""
        self._index += 1
        if self._index >= len(self._phases):
            self._finish(True, "")
            return False
        phase = self._phases[self._index]
        self._queue = multiprocessing.Queue()
        try:
            processes, finish_events, total = phase.build(self.stop_event, self._queue)
        except Exception as e:
            self._finish(False, f"{phase.label} failed to start: {e}")
            return False
        self._processes = processes
        self._finish_events = finish_events
        self._label = phase.label
        self._total = total
        self._done = 0
        self.phase_started.emit(self._label, self._total)
        for process in processes:
            process.start()
        if not processes:
            # An empty phase (nothing to extract, say) completes immediately.
            return self._advance()
        return True

    def _poll(self):
        self._drain_queue()
        events_done = all(event.is_set() for event in self._finish_events) if self._finish_events else True
        alive = any(process.is_alive() for process in self._processes)

        # Wait only while there is something still working. Liveness is checked as
        # well as the finish events because a worker killed outright — an OOM kill
        # is the realistic case, since running every checker loads the union of
        # their requirements — never reaches its `finally` and so never sets its
        # event. Trusting the event alone left the job polling forever, and with an
        # app-wide freeze that locks the entire UI.
        if not events_done and alive:
            return

        self._drain_queue()
        died_silently = not events_done and not alive
        exit_codes = [process.exitcode for process in self._processes]
        self._join()

        if died_silently:
            self._finish(False, (
                f"{self._label}: a worker exited without finishing (exit codes {exit_codes}). "
                "It was most likely killed for running out of memory — try fewer threads."
            ))
            return
        if self.stop_event.is_set():
            if self._stopping:
                self._finish(False, "Stopped.")
            else:
                failed = [code for code in exit_codes if code not in (0, None)]
                detail = f" (exit codes {failed})" if failed else ""
                self._finish(False, f"{self._label}: a worker reported an error{detail}.")
            return
        self._advance()

    def _drain_queue(self):
        if self._queue is None:
            return
        try:
            while True:
                self._done += self._queue.get(block=False)
                self.progress.emit(self._label, self._done, self._total)
        except Exception:
            pass  # queue.Empty, or the queue is already closed

    def _join(self):
        for process in self._processes:
            if process.is_alive():
                process.join(timeout=1)
            else:
                process.join()
        self._processes = []
        self._finish_events = []

    def _finish(self, ok, message):
        self._timer.stop()
        self._join()
        if self._frozen:
            busy_controller.end()
            self._frozen = False
        self.stop_event.clear()
        self.finished.emit(ok, message)

    def shutdown(self):
        """Tear down without emitting — for window close."""
        self.stop_event.set()
        self._timer.stop()
        self._join()
        if self._frozen:
            busy_controller.end()
            self._frozen = False
