"""
EntroPy - GUI
PySide6 and PyQtGraph interface for core.py.
Features clean legend lines without fill swatches, translucent area fills under curves,
fixed UI proportions, 512-byte semi-transparent region highlight, drag-and-drop file loading,
zoom limits, scaled high-readability fonts, top-right specification panel, Cramer's V metric,
unabbreviated probability labels, and interactive offset hex inspection.
"""

import json
import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSplitter, QTextEdit, QPlainTextEdit,
    QProgressBar, QGroupBox, QGridLayout, QMessageBox, QToolButton,
    QStackedLayout, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent

import pyqtgraph as pg
import core


class AnalysisThread(QThread):
    """Worker thread analyzing a queue of files sequentially.

    Results are accumulated in Python-side attributes (``reports``,
    ``summaries``) and only primitive-typed signals are emitted, keeping
    cross-thread signal marshalling safe. Progress is a global 0-100%
    percentage spanning the whole queue.
    """
    file_done = Signal(int)          # index of the file just analyzed
    progress_updated = Signal(int, str)
    analysis_finished = Signal()     # queue fully processed (see reports[])
    analysis_failed = Signal(str)    # fatal / cancelled run

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = list(file_paths)
        self.reports: list = []
        self.summaries: list = []

    def run(self):
        total = len(self.file_paths)
        for index, path in enumerate(self.file_paths):
            base = int(index * 100 / total)
            span = max(1, int(100 / total) - 1)

            def progress_cb(percent: int, status_msg: str,
                            _base=base, _span=span):
                self.progress_updated.emit(_base + min(_span, percent), status_msg)

            try:
                report = core.analyze_file(path, progress_callback=progress_cb)
                self.reports.append(report)
                self.summaries.append(
                    f"{os.path.basename(path)}: {report.trend.dominant_category}"
                )
            except Exception as exc:
                self.reports.append(None)
                self.summaries.append(f"{os.path.basename(path)}: ERROR — {exc}")
            self.file_done.emit(index)

        self.progress_updated.emit(100, "Analysis complete.")
        self.analysis_finished.emit()


class EntroPyGUI(QMainWindow):
    """Main application window for EntroPy."""

    def __init__(self):
        super().__init__()
        self.current_report = None
        self.current_file_path = ""
        self.thread = None
        
        self.setWindowTitle("EntroPy - Entropy Analyzer")
        self.resize(1500, 980)
        self.setAcceptDrops(True)
        
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # --- TOP CONTROL & FILE INFO HEADER BAR ---
        header_container = QFrame()
        header_container.setStyleSheet("background-color: #1a1a1a; border-radius: 6px; padding: 6px;")
        header_layout = QHBoxLayout(header_container)

        # Left Header Controls: Open File Button + Drag & Drop Badge + File Name
        left_header_layout = QHBoxLayout()
        left_header_layout.setSpacing(14)

        self.btn_open = QPushButton("Open Files")
        self.btn_open.setFont(QFont("Arial", 12, QFont.Bold))
        self.btn_open.setFixedHeight(44)
        self.btn_open.setFixedWidth(140)
        self.btn_open.setStyleSheet(
            "QPushButton { background-color: #007acc; color: #ffffff; border-radius: 5px; font-size: 12pt; }"
            "QPushButton:hover { background-color: #0098ff; }"
            "QPushButton:pressed { background-color: #005c99; }"
        )
        self.btn_open.clicked.connect(self.select_file)

        # Visual Drag & Drop Indicator Badge
        self.lbl_drag_drop = QLabel("[ ⇩ Drag & Drop File Here ]")
        self.lbl_drag_drop.setFixedHeight(44)
        self.lbl_drag_drop.setAlignment(Qt.AlignCenter)
        self.lbl_drag_drop.setStyleSheet(
            "font-size: 11pt; font-weight: bold; color: #00b0ff; "
            "border: 2px dashed #00b0ff; border-radius: 5px; padding: 0px 14px; "
            "background-color: rgba(0, 176, 255, 0.08);"
        )
        
        self.lbl_file_name = QLabel("No file loaded.")
        self.lbl_file_name.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffffff;")

        left_header_layout.addWidget(self.btn_open)
        left_header_layout.addWidget(self.lbl_drag_drop)
        left_header_layout.addWidget(self.lbl_file_name, stretch=1)
        header_layout.addLayout(left_header_layout, stretch=1)

        # Right Header: File Specifications Panel (Size, Magic Bytes, Format)
        right_header_frame = QFrame()
        right_header_frame.setStyleSheet("background-color: #242424; border: 1px solid #383838; border-radius: 5px; padding: 6px 12px;")
        right_header_layout = QGridLayout(right_header_frame)
        right_header_layout.setVerticalSpacing(4)
        right_header_layout.setHorizontalSpacing(14)

        lbl_size_title = QLabel("File Size:")
        lbl_size_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #a0a0a0;")
        self.lbl_file_size_val = QLabel("-")
        self.lbl_file_size_val.setStyleSheet("font-size: 11.5pt; font-weight: bold; color: #00e676;")

        lbl_magic_title = QLabel("Magic Bytes:")
        lbl_magic_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #a0a0a0;")
        self.lbl_magic_bytes_val = QLabel("-")
        self.lbl_magic_bytes_val.setFont(QFont("Courier New", 11, QFont.Bold))
        self.lbl_magic_bytes_val.setStyleSheet("color: #00b0ff;")

        lbl_format_title = QLabel("Detected Format:")
        lbl_format_title.setStyleSheet("font-size: 11pt; font-weight: bold; color: #a0a0a0;")
        self.lbl_detected_format_val = QLabel("-")
        self.lbl_detected_format_val.setStyleSheet("font-size: 11.5pt; font-weight: bold; color: #00b0ff;")

        right_header_layout.addWidget(lbl_size_title, 0, 0)
        right_header_layout.addWidget(self.lbl_file_size_val, 0, 1)
        right_header_layout.addWidget(lbl_magic_title, 1, 0)
        right_header_layout.addWidget(self.lbl_magic_bytes_val, 1, 1)
        right_header_layout.addWidget(lbl_format_title, 2, 0)
        right_header_layout.addWidget(self.lbl_detected_format_val, 2, 1)

        header_layout.addWidget(right_header_frame)
        main_layout.addWidget(header_container)

        # --- VERTICAL SPLITTER (Top Plot vs Bottom Details) ---
        self.v_splitter = QSplitter(Qt.Vertical)
        self.v_splitter.setChildrenCollapsible(False)

        # --- TOP PANEL: PyQtGraph Plot with Progress Overlay ---
        plot_container = QWidget()
        self.plot_stacked_layout = QStackedLayout(plot_container)

        # Layer 0: Plot Widget
        pg.setConfigOption('background', '#121212')
        pg.setConfigOption('foreground', '#dcdcdc')

        self.plot_widget = pg.PlotWidget(
            title="Sliding Window Analysis (Shannon Entropy & Null-Byte Ratio)"
        )
        self.plot_widget.setLabel('left', 'bits/byte')
        self.plot_widget.setLabel('bottom', 'File Address Offset', units='Bytes')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(-0.2, 8.2)

        # Extra-Large Legend Container
        self.plot_legend = self.plot_widget.addLegend(
            labelTextSize='18pt',
            offset=(-20, 20)
        )

        # Plot Curves with 15% Opacity Area Fill (Without auto-legend binding)
        self.curve_entropy = self.plot_widget.plot(
            pen=pg.mkPen(color='#00ff7f', width=2.0),
            fillLevel=0.0,
            brush=pg.mkBrush(color=(0, 255, 127, 38))
        )
        self.curve_nulls = self.plot_widget.plot(
            pen=pg.mkPen(color='#ff4500', width=1.6, style=Qt.DashLine),
            fillLevel=0.0,
            brush=pg.mkBrush(color=(255, 69, 0, 35))
        )

        # Clean Line Swatches for Legend (No area fill polygon)
        sample_entropy = pg.PlotDataItem(pen=pg.mkPen(color='#00ff7f', width=2.5))
        sample_nulls = pg.PlotDataItem(pen=pg.mkPen(color='#ff4500', width=2.0, style=Qt.DashLine))

        self.plot_legend.addItem(sample_entropy, "Entropy H(X) [0.0 - 8.0 bits/byte]")
        self.plot_legend.addItem(sample_nulls, "Null-Byte Ratio [0% - 100% Scale]")

        # Semi-transparent 512-Byte Region Highlight Box (Blue #00b0ff)
        self.selection_region = pg.LinearRegionItem(
            values=[0, 512],
            orientation='vertical',
            brush=pg.mkBrush(color=(0, 176, 255, 60)),
            pen=pg.mkPen(color='#00b0ff', width=1.5),
            movable=False
        )
        self.selection_region.hide()
        self.plot_widget.addItem(self.selection_region)

        # Click interaction on graph
        self.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)
        self.plot_stacked_layout.addWidget(self.plot_widget)

        # Layer 1: Analysis Progress Overlay Frame
        self.overlay_frame = QFrame()
        self.overlay_frame.setStyleSheet("background-color: #121212;")
        overlay_layout = QVBoxLayout(self.overlay_frame)
        overlay_layout.setAlignment(Qt.AlignCenter)

        self.lbl_overlay_msg = QLabel("Initializing analysis...")
        self.lbl_overlay_msg.setStyleSheet("font-size: 18pt; font-weight: bold; color: #ffffff;")
        
        self.overlay_progress = QProgressBar()
        self.overlay_progress.setRange(0, 100)
        self.overlay_progress.setValue(0)
        self.overlay_progress.setFixedWidth(550)
        self.overlay_progress.setFixedHeight(32)
        self.overlay_progress.setStyleSheet(
            "QProgressBar { border: 2px solid #444; border-radius: 6px; text-align: center; "
            "background-color: #1e1e1e; color: #ffffff; font-size: 13pt; font-weight: bold; }"
            "QProgressBar::chunk { background-color: #00e676; border-radius: 4px; }"
        )

        overlay_layout.addWidget(self.lbl_overlay_msg, alignment=Qt.AlignCenter)
        overlay_layout.addWidget(self.overlay_progress, alignment=Qt.AlignCenter)

        self.plot_stacked_layout.addWidget(self.overlay_frame)
        self.plot_stacked_layout.setCurrentWidget(self.plot_widget)

        self.v_splitter.addWidget(plot_container)

        # --- BOTTOM PANEL: Horizontal Splitter (Metrics/Trend vs Hex View) ---
        self.h_splitter = QSplitter(Qt.Horizontal)
        self.h_splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Group 1: Global Statistical Metrics
        group_metrics = QGroupBox("Global Metrics")
        group_metrics.setStyleSheet("QGroupBox { font-size: 15pt; font-weight: bold; color: #ffffff; }")
        metrics_layout = QVBoxLayout(group_metrics)
        metrics_layout.setContentsMargins(10, 18, 10, 10)
        metrics_layout.setSpacing(6)

        self.lbl_md5, self.btn_copy_md5 = self.create_metric_row(
            metrics_layout, "MD5 Hash:", "Full file cryptographic MD5 checksum"
        )
        self.lbl_sha256, self.btn_copy_sha256 = self.create_metric_row(
            metrics_layout, "SHA-256 Hash:", "SHA-256 hash for chain of custody verification"
        )
        self.lbl_entropy, self.btn_copy_entropy = self.create_metric_row(
            metrics_layout, "Shannon Entropy (H):", "Global information density [0.0 - 8.0 bits/byte]"
        )
        self.lbl_cramers_v, self.btn_copy_cramers_v = self.create_metric_row(
            metrics_layout, "Cramer's V (V):", "Normalized non-uniformity index [0.0 = Uniform, 1.0 = Non-uniform]"
        )
        self.lbl_mean, self.btn_copy_mean = self.create_metric_row(
            metrics_layout, "Arithmetic Mean (x̄):", "Mean byte value [0-255] (Theoretical random = 127.5)"
        )
        self.lbl_correlation, self.btn_copy_correlation = self.create_metric_row(
            metrics_layout, "Serial Correlation (r₁):", "Lag-1 correlation between adjacent contiguous bytes"
        )
        self.lbl_pair, self.btn_copy_pair = self.create_metric_row(
            metrics_layout, "Pair Correlation (r₂):", "Lag-2 correlation between bytes two apart (alternating patterns)"
        )

        left_layout.addWidget(group_metrics)

        # Group 2: Data Trend & Rationale
        group_trend = QGroupBox("Data Trend & Rationale")
        group_trend.setStyleSheet("QGroupBox { font-size: 15pt; font-weight: bold; color: #ffffff; }")
        trend_layout = QVBoxLayout(group_trend)
        trend_layout.setContentsMargins(12, 18, 12, 12)

        self.lbl_dominant = QLabel("Dominant Classification: -")
        self.lbl_dominant.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffffff;")

        self.lbl_probabilities = QLabel("Probabilities: Corrupted: - | Compressed: - | Encrypted: - | Structured: - | Padding: -")
        self.lbl_probabilities.setStyleSheet("font-size: 12pt; color: #d0d0d0;")

        self.txt_rationale = QTextEdit()
        self.txt_rationale.setReadOnly(True)
        self.txt_rationale.setFont(QFont("Arial", 12.5))
        self.txt_rationale.setMinimumHeight(120)
        self.txt_rationale.setStyleSheet("background-color: #181818; color: #b0bec5; border: 1px solid #333333; padding: 10px; font-size: 12.5pt;")
        self.txt_rationale.setPlaceholderText("Statistical rationale explanations will appear here after analysis.")

        trend_layout.addWidget(self.lbl_dominant)
        trend_layout.addWidget(self.lbl_probabilities)
        trend_layout.addWidget(self.txt_rationale)

        self.lbl_queue_summary = QLabel("")
        self.lbl_queue_summary.setWordWrap(True)
        self.lbl_queue_summary.setStyleSheet("font-size: 11pt; color: #80cbc4;")

        self.btn_export = QPushButton("Export Report (JSON)")
        self.btn_export.setEnabled(False)
        self.btn_export.setFixedHeight(36)
        self.btn_export.setStyleSheet(
            "QPushButton { background-color: #2e2e2e; color: #d0d0d0; border: 1px solid #444444; "
            "border-radius: 4px; font-size: 11pt; font-weight: bold; }"
            "QPushButton:hover { background-color: #3e3e3e; color: #ffffff; }"
            "QPushButton:pressed { background-color: #007acc; }"
            "QPushButton:disabled { color: #777777; }"
        )
        self.btn_export.clicked.connect(self.export_report)

        trend_layout.addWidget(self.lbl_queue_summary)
        trend_layout.addWidget(self.btn_export)

        left_layout.addWidget(group_trend)
        self.h_splitter.addWidget(left_panel)

        # Hex Inspection Panel (Blue Monospace Text #00b0ff)
        group_hex = QGroupBox("Real-Time Offset Inspection (512-Byte Window)")
        group_hex.setStyleSheet("QGroupBox { font-size: 15pt; font-weight: bold; color: #ffffff; }")
        hex_layout = QVBoxLayout(group_hex)

        self.txt_hex = QPlainTextEdit()
        self.txt_hex.setReadOnly(True)
        self.txt_hex.setFont(QFont("Courier New", 13))
        self.txt_hex.setStyleSheet("background-color: #181818; color: #00b0ff; font-size: 12pt;")
        
        hex_layout.addWidget(self.txt_hex)
        self.h_splitter.addWidget(group_hex)

        self.h_splitter.setStretchFactor(0, 1)
        self.h_splitter.setStretchFactor(1, 1)

        self.v_splitter.addWidget(self.h_splitter)

        self.v_splitter.setStretchFactor(0, 48)
        self.v_splitter.setStretchFactor(1, 52)

        main_layout.addWidget(self.v_splitter)

        self.v_splitter.setSizes([430, 470])
        self.h_splitter.setSizes([700, 700])

    def create_metric_row(self, parent_layout: QVBoxLayout, title_text: str, subdesc_text: str):
        """Creates a metric card with title, inline sub-description, right-aligned value, and copy button."""
        row_frame = QFrame()
        row_frame.setStyleSheet("QFrame { background-color: #1e1e1e; border-radius: 5px; padding: 3px 8px; }")

        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(10, 5, 10, 5)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet("font-size: 13.5pt; font-weight: bold; color: #ffffff;")

        lbl_subdesc = QLabel(subdesc_text)
        lbl_subdesc.setStyleSheet("font-size: 11pt; color: #999999;")

        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subdesc)

        lbl_val = QLabel("-")
        lbl_val.setFont(QFont("Courier New", 13.5, QFont.Bold))
        lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_val.setStyleSheet("color: #ffffff; font-size: 13.5pt; padding-right: 14px;")
        lbl_val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        btn_copy = QToolButton()
        btn_copy.setText("Copy")
        btn_copy.setFixedWidth(70)
        btn_copy.setFixedHeight(32)
        btn_copy.setStyleSheet(
            "QToolButton { background-color: #2e2e2e; color: #d0d0d0; border: 1px solid #444444; "
            "border-radius: 4px; font-size: 11pt; font-weight: bold; padding: 2px; }"
            "QToolButton:hover { background-color: #3e3e3e; color: #ffffff; }"
            "QToolButton:pressed { background-color: #007acc; }"
        )
        btn_copy.clicked.connect(lambda: self.copy_to_clipboard(lbl_val.text(), btn_copy))

        row_layout.addWidget(title_box, stretch=1)
        row_layout.addWidget(lbl_val, stretch=1)
        row_layout.addWidget(btn_copy)

        parent_layout.addWidget(row_frame)

        return lbl_val, btn_copy

    def copy_to_clipboard(self, text: str, button: QToolButton):
        """Copies given text to clipboard and provides transient button feedback."""
        if text and text != "-":
            QApplication.clipboard().setText(text)
            button.setText("Copied!")
            QTimer.singleShot(1200, lambda: button.setText("Copy"))

    # --- Drag and Drop Handlers ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if not self._is_idle():
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        # De-duplicate while preserving order, keep existing files only.
        paths = [p for p in dict.fromkeys(paths) if os.path.isfile(p)]
        if paths:
            self.start_analysis(paths)

    def select_file(self):
        if not self._is_idle():
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Analyze", "", "All Files (*)"
        )
        if files:
            self.start_analysis(files)

    def _is_idle(self) -> bool:
        """True when no analysis worker thread is currently running."""
        return self.thread is None or not self.thread.isRunning()

    def start_analysis(self, file_paths):
        """Queues one or more files for sequential background analysis."""
        if not self._is_idle():
            return  # a worker thread is still running; ignore overlapping requests
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        if not file_paths:
            return

        self._reset_results_ui()
        names = ", ".join(os.path.basename(p) for p in file_paths[:3])
        if len(file_paths) > 3:
            names += f" (+{len(file_paths) - 3} more)"

        self.lbl_file_name.setText(names)
        self.btn_open.setEnabled(False)

        self.lbl_overlay_msg.setText(f"Analyzing {names}...")
        self.overlay_progress.setValue(0)
        self.plot_stacked_layout.setCurrentWidget(self.overlay_frame)

        QApplication.processEvents()

        self.thread = AnalysisThread(file_paths)
        self.thread.file_done.connect(self.on_file_done)
        self.thread.progress_updated.connect(self.on_progress_updated)
        self.thread.analysis_finished.connect(self.on_analysis_finished)
        self.thread.analysis_failed.connect(self.on_analysis_failed)
        self.thread.start()

    def on_progress_updated(self, percent: int, status_msg: str):
        self.overlay_progress.setValue(percent)
        self.lbl_overlay_msg.setText(f"{status_msg} ({percent}%)")

    def on_file_done(self, index: int):
        """Applies a freshly completed per-file report to the results UI."""
        report = self.thread.reports[index]
        if report is not None:
            self.current_file_path = self.thread.file_paths[index]
            self._apply_report(report)

    def on_progress_updated(self, percent: int, status_msg: str):
        self.overlay_progress.setValue(percent)
        self.lbl_overlay_msg.setText(f"{status_msg} ({percent}%)")

    def on_analysis_finished(self):
        self.plot_stacked_layout.setCurrentWidget(self.plot_widget)
        self.btn_open.setEnabled(True)
        self.btn_export.setEnabled(self.current_report is not None)
        self._show_queue_summary()
        if self.thread is not None and all(r is None for r in self.thread.reports):
            QMessageBox.critical(
                self, "Analysis Error",
                "No files could be analyzed.\n" + "\n".join(self.thread.summaries)
            )

    def on_analysis_failed(self, error_msg: str):
        self.plot_stacked_layout.setCurrentWidget(self.plot_widget)
        self.btn_open.setEnabled(True)
        self._show_queue_summary()
        QMessageBox.critical(self, "Analysis Error", f"Failed to analyze file:\n{error_msg}")

    # --- Result presentation helpers ---

    def _apply_report(self, report: core.AnalysisReport):
        """Populates the full results UI (header, metrics, trend, plot) for one report."""
        self.current_report = report

        meta = report.metadata
        metrics = report.global_metrics
        win = report.windowed_analysis
        trend = report.trend

        # Update Top Right File Specifications Panel
        size_mb = meta.file_size / (1024 * 1024)
        if size_mb >= 1024:
            size_str = f"{meta.file_size:,} bytes ({size_mb / 1024:.2f} GB)"
        else:
            size_str = f"{meta.file_size:,} bytes ({size_mb:.2f} MB)"
        self.lbl_file_size_val.setText(size_str)

        magic_hex = meta.magic_bytes[:16].hex(' ').upper()
        ascii_repr = "".join(chr(b) if 32 <= b <= 126 else "." for b in meta.magic_bytes[:16])
        self.lbl_magic_bytes_val.setText(f"{magic_hex}  |{ascii_repr}|")
        self.lbl_detected_format_val.setText(meta.detected_format)

        # Update Right-Aligned Global Metrics
        self.lbl_md5.setText(meta.md5)
        self.lbl_sha256.setText(meta.sha256)
        self.lbl_entropy.setText(f"{metrics.shannon_entropy:.6f} bits/byte")
        self.lbl_cramers_v.setText(f"{metrics.cramers_v:.6f} ({metrics.cramers_v * 100:.2f}%)")
        self.lbl_mean.setText(f"{metrics.arithmetic_mean:.4f}")
        self.lbl_correlation.setText(f"{metrics.serial_correlation:.6f}")
        self.lbl_pair.setText(f"{metrics.pair_correlation:.6f}")

        # Update Trend & Rationale Section
        self.lbl_dominant.setText(f"Dominant Classification: {trend.dominant_category}")
        self.lbl_dominant.setStyleSheet("font-size: 14pt; font-weight: bold; color: #ffffff;")

        self.lbl_probabilities.setText(
            f"Probabilities: Corrupted: {trend.prob_corrupted}% | "
            f"Compressed: {trend.prob_compressed}% | "
            f"Encrypted: {trend.prob_encrypted}% | "
            f"Structured: {trend.prob_structured}% | "
            f"Padding: {trend.prob_padding}%"
        )
        
        # Highlight 'CRITICAL ANOMALY:' in red inside Rationale box
        html_rationale = []
        for r in trend.rationale:
            if "CRITICAL ANOMALY:" in r:
                formatted_r = r.replace(
                    "CRITICAL ANOMALY:",
                    "<span style='color: #ff3366; font-weight: bold;'>CRITICAL ANOMALY:</span>"
                )
                html_rationale.append(f"• {formatted_r}")
            else:
                html_rationale.append(f"• {r}")

        self.txt_rationale.setHtml("<br><br>".join(html_rationale))

        # Update Plot Curves and Enforce Strict Zoom Out Limits
        offsets = win.block_offsets
        entropy_vals = win.entropy_series
        null_vals = win.null_ratio_series * 8.0

        max_offset = offsets[-1] + win.block_size if len(offsets) > 0 else meta.file_size
        
        self.plot_widget.setLimits(
            xMin=0,
            xMax=max_offset,
            yMin=-0.2,
            yMax=8.2
        )

        self.curve_entropy.setData(offsets, entropy_vals)
        self.curve_nulls.setData(offsets, null_vals)
        self.plot_widget.setXRange(0, max_offset)

        self.txt_hex.setPlainText("Click anywhere on the plot to inspect the hexadecimal dump at that offset.")
        self.btn_export.setEnabled(True)

    def _reset_results_ui(self):
        """Returns all result widgets to their pre-analysis state."""
        self.current_report = None
        self.lbl_file_size_val.setText("-")
        self.lbl_magic_bytes_val.setText("-")
        self.lbl_detected_format_val.setText("-")
        for lbl in (self.lbl_md5, self.lbl_sha256, self.lbl_entropy,
                    self.lbl_cramers_v, self.lbl_mean, self.lbl_correlation, self.lbl_pair):
            lbl.setText("-")
        self.lbl_dominant.setText("Dominant Classification: -")
        self.lbl_probabilities.setText(
            "Probabilities: Corrupted: - | Compressed: - | Encrypted: - | Structured: - | Padding: -"
        )
        self.lbl_queue_summary.setText("")
        self.txt_rationale.clear()
        self.txt_hex.setPlainText("Click anywhere on the plot to inspect the hexadecimal dump at that offset.")
        self.btn_export.setEnabled(False)
        self.selection_region.hide()

    def _show_queue_summary(self):
        """Shows a one-line-per-file classification summary for multi-file runs."""
        if self.thread is None or len(self.thread.file_paths) < 2:
            return
        self.lbl_queue_summary.setText("Queue: " + "  |  ".join(self.thread.summaries))

    def export_report(self):
        """Saves the current AnalysisReport as a human-readable JSON file."""
        if self.current_report is None or not self.current_file_path:
            return
        base_name = os.path.basename(self.current_file_path)
        default_name = f"{base_name}.entroPy.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Analysis Report", default_name, "JSON Report (*.json)"
        )
        if not file_path:
            return
        if not file_path.endswith(".json"):
            file_path += ".json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(core.report_to_dict(self.current_report), f, indent=2)
            self.btn_export.setText("Exported ✓")
            QTimer.singleShot(1500, lambda: self.btn_export.setText("Export Report (JSON)"))
        except OSError as exc:
            QMessageBox.warning(self, "Export Error", f"Could not write report:\n{exc}")

    def on_plot_clicked(self, event):
        if self.current_report is None or not self.current_file_path:
            return

        pos = event.scenePos()
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        target_offset = int(mouse_point.x())

        file_size = self.current_report.metadata.file_size
        if 0 <= target_offset < file_size:
            length = 512
            start_offset = max(0, target_offset - (length // 2))
            start_offset = (start_offset // 16) * 16
            read_length = min(length, file_size - start_offset)
            end_offset = start_offset + read_length

            # Highlight exact 512-byte aligned region on plot
            self.selection_region.setRegion([start_offset, end_offset])
            self.selection_region.show()

            # Load Hex View
            self.load_hex_preview(target_offset, length=length)

    def load_hex_preview(self, offset: int, length: int = 512):
        """Loads and formats a 512-byte hex view around the clicked offset."""
        if not os.path.exists(self.current_file_path):
            return

        file_size = os.path.getsize(self.current_file_path)
        start_offset = max(0, offset - (length // 2))
        start_offset = (start_offset // 16) * 16

        read_length = min(length, file_size - start_offset)

        try:
            with open(self.current_file_path, "rb") as f:
                f.seek(start_offset)
                chunk = f.read(read_length)

            hex_lines = []
            hex_lines.append(f"--- HEX DUMP | SELECTED OFFSET: {offset:,} (0x{offset:X}) ---\n")
            
            for i in range(0, len(chunk), 16):
                row = chunk[i:i + 16]
                row_offset = start_offset + i
                hex_vals = " ".join(f"{b:02X}" for b in row)
                ascii_vals = "".join(chr(b) if 32 <= b <= 126 else "." for b in row)
                
                prefix = ">" if row_offset <= offset < row_offset + 16 else " "
                hex_lines.append(f"{prefix} {row_offset:08X}  {hex_vals:<47}  |{ascii_vals}|")

            self.txt_hex.setPlainText("\n".join(hex_lines))
        except Exception as e:
            self.txt_hex.setPlainText(f"Error reading offset 0x{offset:X}: {e}")


def main():
    app = QApplication(sys.argv)
    window = EntroPyGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()