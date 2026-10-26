"""GUI smoke tests (headless, offscreen Qt platform).

The entire module is skipped when Qt cannot be initialized in the current
environment (e.g. a CI runner missing system EGL/OpenGL libraries), so the
pure-NumPy core suite keeps running everywhere.
"""
import os
import time

import pytest

try:
    from PySide6 import QtWidgets
except ImportError as exc:
    pytest.skip(f"PySide6/Qt runtime not usable in this environment: {exc}",
                allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core
import gui


@pytest.fixture()
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_window_constructs(qapp):
    window = gui.EntroPyGUI()
    try:
        assert window.windowTitle() == "EntroPy - Entropy Analyzer"
        assert window._is_idle()
        assert window.btn_open.isEnabled()
        assert window.btn_export.isEnabled() is False  # nothing analyzed yet
    finally:
        window.close()


def test_multi_file_queue(qapp, tmp_path, monkeypatch):
    """Two dropped files are analyzed in order; per-file failures don't abort the queue."""
    real = core.analyze_file

    def fake_analysis(file_path, progress_callback=None, **kwargs):
        if "missing" in file_path:
            raise RuntimeError("synthetic failure")
        return real(file_path, progress_callback=progress_callback)

    monkeypatch.setattr(core, "analyze_file", fake_analysis)

    good = tmp_path / "good.bin"
    good.write_bytes(b"PK\x03\x04" + b"\x00" * 8192)
    missing = tmp_path / "missing.bin"  # never created

    window = gui.EntroPyGUI()
    try:
        window.start_analysis([str(good), str(missing)])
        assert window.thread is not None and window.thread.isRunning()
        window.thread.wait(15_000)
        # Deliver queued (cross-thread) signal emissions to their slots.
        for _ in range(10):
            qapp.processEvents()

        assert window.thread.reports[0] is not None
        assert window.thread.reports[1] is None  # failure isolated to that file
        assert any("ERROR" in s for s in window.thread.summaries)
        assert window.thread.summaries[0].startswith("good.bin")
        # UI restored: open re-enabled, results from the successful file shown.
        assert window.btn_open.isEnabled()
        assert window.btn_export.isEnabled()
        assert window.lbl_queue_summary.text().startswith("Queue:")
    finally:
        window.thread.wait(15_000)
        window.close()


def test_double_start_analysis_is_blocked(qapp, tmp_path, monkeypatch):
    """A second analysis request while a worker runs must be ignored (no leaked thread)."""
    real = core.analyze_file

    def slow_analysis(file_path, progress_callback=None, **kwargs):
        time.sleep(0.5)  # keep the worker thread alive for a deterministic window
        return real(file_path, progress_callback=progress_callback)

    monkeypatch.setattr(core, "analyze_file", slow_analysis)

    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"\x00" * 4096)

    window = gui.EntroPyGUI()
    try:
        window.start_analysis(str(sample))
        assert window.thread is not None and window.thread.isRunning()

        window.start_analysis(str(sample))  # must be a no-op
        first_thread = window.thread
        window.thread.wait(10_000)
        assert window.thread is first_thread  # original worker kept, no orphan
    finally:
        window.thread.wait(10_000)
        window.close()
