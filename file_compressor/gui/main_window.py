from __future__ import annotations

import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import (
    DEFAULT_PRESET,
    PRESETS,
    ArchiveFormat,
    CompressionResult,
    format_size,
    get_handler,
)
from .worker import CompressionWorker

COL_FILE, COL_TYPE, COL_ORIGINAL, COL_NEW, COL_SAVED, COL_STATUS = range(6)
HEADERS = ["File", "Type", "Original", "Compressed", "Saved", "Status"]

GREEN = QColor("#1b8a3a")
GREY = QColor("#777777")
RED = QColor("#c62828")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("File Compressor")
        self.resize(980, 620)
        self.setAcceptDrops(True)

        self._files: list[Path] = []
        self._outputs: dict[int, Path] = {}
        self._results: list[CompressionResult] = []
        self._thread: QThread | None = None
        self._worker: CompressionWorker | None = None

        self._build_ui()
        self._update_buttons()

    # ----- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        hint = QLabel(
            "Drag and drop files or folders here, or use the buttons below. "
            "Images, PDFs and Office documents are optimized; any other file is packed into an archive."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(self._open_output_for_row)
        layout.addWidget(self.table, stretch=1)

        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("Add files…")
        self.add_folder_btn = QPushButton("Add folder…")
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear list")
        self.add_files_btn.clicked.connect(self._choose_files)
        self.add_folder_btn.clicked.connect(self._choose_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear)
        for btn in (self.add_files_btn, self.add_folder_btn, self.remove_btn, self.clear_btn):
            file_buttons.addWidget(btn)
        file_buttons.addStretch()
        layout.addLayout(file_buttons)

        layout.addWidget(self._build_options())

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.summary_label = QLabel("")
        self.open_folder_btn = QPushButton("Open output folder")
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.compress_btn = QPushButton("Compress")
        self.compress_btn.setDefault(True)
        self.compress_btn.setMinimumWidth(120)
        self.compress_btn.clicked.connect(self._start)
        bottom.addWidget(self.progress, stretch=1)
        bottom.addWidget(self.open_folder_btn)
        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.compress_btn)
        layout.addWidget(self.summary_label)
        layout.addLayout(bottom)

        self.setCentralWidget(central)

    def _build_options(self) -> QGroupBox:
        box = QGroupBox("Options")
        form = QFormLayout(box)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS.keys())
        self.preset_combo.setCurrentText(DEFAULT_PRESET)
        self.preset_combo.setToolTip(
            "Maximum compression: smallest files, visible quality loss possible.\n"
            "Balanced: good size reduction with little visible difference.\n"
            "High quality: gentle compression, full image resolution kept."
        )
        form.addRow("Quality:", self.preset_combo)

        self.archive_combo = QComboBox()
        self.archive_combo.addItem("ZIP (opens everywhere)", ArchiveFormat.ZIP.value)
        self.archive_combo.addItem("7z (smaller, needs 7-Zip)", ArchiveFormat.SEVEN_ZIP.value)
        form.addRow("Other file types:", self.archive_combo)

        output_row = QHBoxLayout()
        self.same_folder_radio = QRadioButton("Next to original")
        self.custom_folder_radio = QRadioButton("Folder:")
        self.same_folder_radio.setChecked(True)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose an output folder")
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._choose_output_folder)
        self.custom_folder_radio.toggled.connect(self._update_buttons)
        output_row.addWidget(self.same_folder_radio)
        output_row.addWidget(self.custom_folder_radio)
        output_row.addWidget(self.output_edit, stretch=1)
        output_row.addWidget(self.browse_btn)
        form.addRow("Save to:", output_row)
        return box

    # ----- File list -------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and not self._is_running():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._add_paths(paths)
        event.acceptProposedAction()

    def _choose_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Choose files to compress")
        self._add_paths([Path(n) for n in names])

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder to compress")
        if folder:
            self._add_paths([Path(folder)])

    def _choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)
            self.custom_folder_radio.setChecked(True)

    def _add_paths(self, paths: list[Path]) -> None:
        known = {p.resolve() for p in self._files}
        for path in self._expand(paths):
            resolved = path.resolve()
            if resolved in known:
                continue
            known.add(resolved)
            self._files.append(path)
            self._append_row(path)
        self._update_buttons()

    @staticmethod
    def _expand(paths: list[Path]):
        for path in paths:
            if path.is_dir():
                yield from sorted(p for p in path.rglob("*") if p.is_file())
            elif path.is_file():
                yield path

    def _append_row(self, path: Path) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        file_item = QTableWidgetItem(path.name)
        file_item.setToolTip(str(path))
        self.table.setItem(row, COL_FILE, file_item)
        self.table.setItem(row, COL_TYPE, QTableWidgetItem(get_handler(path).category))
        self.table.setItem(row, COL_ORIGINAL, self._size_item(path.stat().st_size))
        for col in (COL_NEW, COL_SAVED, COL_STATUS):
            self.table.setItem(row, col, QTableWidgetItem(""))
        self._set_status(row, "Ready", GREY)

    def _remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            del self._files[row]
        self._outputs.clear()
        self._update_buttons()

    def _clear(self) -> None:
        self.table.setRowCount(0)
        self._files.clear()
        self._outputs.clear()
        self.summary_label.clear()
        self.progress.reset()
        self._update_buttons()

    # ----- Compression -----------------------------------------------------

    def _start(self) -> None:
        output_dir = None
        if self.custom_folder_radio.isChecked():
            text = self.output_edit.text().strip()
            if not text:
                QMessageBox.warning(self, "No output folder", "Please choose an output folder.")
                return
            output_dir = Path(text)

        settings = dataclasses.replace(
            PRESETS[self.preset_combo.currentText()],
            archive_format=ArchiveFormat(self.archive_combo.currentData()),
        )

        self._outputs.clear()
        self._results = []
        for row in range(self.table.rowCount()):
            self._set_status(row, "Waiting", GREY)
            self.table.item(row, COL_NEW).setText("")
            self.table.item(row, COL_SAVED).setText("")
        self.progress.setRange(0, len(self._files))
        self.progress.setValue(0)
        self.summary_label.setText("Compressing…")

        # Both objects stay referenced from Python until the thread has fully stopped;
        # deleting either one earlier (e.g. via deleteLater) crashes PySide.
        self._thread = QThread()
        self._worker = CompressionWorker(list(enumerate(self._files)), output_dir, settings)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_finished.connect(self._on_file_finished)
        self._worker.file_failed.connect(self._on_file_failed)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()
        self._update_buttons()

    def _cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.summary_label.setText("Cancelling after the current file…")

    def _on_file_started(self, row: int) -> None:
        self._set_status(row, "Compressing…", None)
        self.table.scrollToItem(self.table.item(row, COL_FILE))

    def _on_file_finished(self, row: int, result: CompressionResult) -> None:
        self._results.append(result)
        self.table.setItem(row, COL_NEW, self._size_item(result.compressed_size))
        if result.reduced:
            self._outputs[row] = result.output
            self.table.item(row, COL_SAVED).setText(f"{result.saved_percent:.0f}%")
            self._set_status(row, f"Saved as {result.output.name}", GREEN)
            self.table.item(row, COL_STATUS).setToolTip(str(result.output))
        else:
            self.table.item(row, COL_SAVED).setText("0%")
            self._set_status(row, "Already optimized - no smaller version possible", GREY)
        self.progress.setValue(self.progress.value() + 1)

    def _on_file_failed(self, row: int, message: str) -> None:
        self._set_status(row, f"Error: {message}", RED)
        self.table.item(row, COL_STATUS).setToolTip(message)
        self.progress.setValue(self.progress.value() + 1)

    def _on_finished(self) -> None:
        self._thread.wait()
        self._thread = None
        self._worker = None
        original = sum(r.original_size for r in self._results)
        compressed = sum(r.compressed_size for r in self._results)
        if original:
            saved = 100.0 * (original - compressed) / original
            self.summary_label.setText(
                f"Done: {len(self._results)} file(s), {format_size(original)} → "
                f"{format_size(compressed)} (saved {format_size(original - compressed)}, {saved:.0f}%)"
            )
        else:
            self.summary_label.setText("Done.")
        self._update_buttons()

    # ----- Helpers ---------------------------------------------------------

    def _is_running(self) -> bool:
        return self._thread is not None

    def _update_buttons(self) -> None:
        running = self._is_running()
        has_files = bool(self._files)
        for widget in (
            self.add_files_btn,
            self.add_folder_btn,
            self.clear_btn,
            self.preset_combo,
            self.archive_combo,
            self.same_folder_radio,
            self.custom_folder_radio,
        ):
            widget.setEnabled(not running)
        self.remove_btn.setEnabled(not running and bool(self.table.selectedIndexes()))
        custom = self.custom_folder_radio.isChecked()
        self.output_edit.setEnabled(not running and custom)
        self.browse_btn.setEnabled(not running)
        self.compress_btn.setEnabled(not running and has_files)
        self.cancel_btn.setEnabled(running)
        self.open_folder_btn.setEnabled(bool(self._outputs) and not running)

    def _set_status(self, row: int, text: str, color: QColor | None) -> None:
        item = self.table.item(row, COL_STATUS)
        item.setText(text)
        item.setToolTip("")
        item.setForeground(color or self.table.palette().color(QPalette.ColorRole.Text))

    @staticmethod
    def _size_item(num_bytes: int) -> QTableWidgetItem:
        item = QTableWidgetItem(format_size(num_bytes))
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _open_output_for_row(self, row: int, _column: int) -> None:
        output = self._outputs.get(row)
        if output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.parent)))

    def _open_output_folder(self) -> None:
        if self._outputs:
            folder = next(iter(self._outputs.values())).parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event) -> None:
        if self._is_running():
            answer = QMessageBox.question(
                self,
                "Compression in progress",
                "Files are still being compressed. Stop after the current file and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._thread.quit()
            self._thread.wait()
        event.accept()
