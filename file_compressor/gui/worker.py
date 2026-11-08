from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..core import CompressionSettings, compress_file


class CompressionWorker(QObject):
    file_started = Signal(int)
    file_finished = Signal(int, object)
    file_failed = Signal(int, str)
    finished = Signal()

    def __init__(
        self,
        jobs: list[tuple[int, Path]],
        output_dir: Path | None,
        settings: CompressionSettings,
    ) -> None:
        super().__init__()
        self._jobs = jobs
        self._output_dir = output_dir
        self._settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        for row, path in self._jobs:
            if self._cancelled:
                break
            self.file_started.emit(row)
            try:
                result = compress_file(path, self._output_dir, self._settings)
            except Exception as exc:
                self.file_failed.emit(row, str(exc) or type(exc).__name__)
            else:
                self.file_finished.emit(row, result)
        self.finished.emit()
