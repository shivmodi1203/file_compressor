from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .archive import archive_output_suffix, compress_to_archive
from .images import IMAGE_EXTENSIONS, compress_image_file, image_output_suffix
from .office import OFFICE_EXTENSIONS, compress_office
from .pdf import PDF_EXTENSIONS, compress_pdf
from .settings import DEFAULT_PRESET, PRESETS, CompressionSettings

OUTPUT_TAG = "_compressed"


@dataclass(frozen=True)
class Handler:
    category: str
    output_suffix: Callable[[Path, CompressionSettings], str]
    compress: Callable[[Path, Path, CompressionSettings], None]


IMAGE_HANDLER = Handler("Image", image_output_suffix, compress_image_file)
PDF_HANDLER = Handler("PDF", lambda src, _settings: src.suffix, compress_pdf)
OFFICE_HANDLER = Handler("Document", lambda src, _settings: src.suffix, compress_office)
ARCHIVE_HANDLER = Handler("Other (archive)", archive_output_suffix, compress_to_archive)


@dataclass(frozen=True)
class CompressionResult:
    source: Path
    output: Path | None
    original_size: int
    compressed_size: int

    @property
    def reduced(self) -> bool:
        return self.output is not None

    @property
    def saved_bytes(self) -> int:
        return self.original_size - self.compressed_size

    @property
    def saved_percent(self) -> float:
        return 100.0 * self.saved_bytes / self.original_size if self.original_size else 0.0


def get_handler(path: Path) -> Handler:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return IMAGE_HANDLER
    if ext in PDF_EXTENSIONS:
        return PDF_HANDLER
    if ext in OFFICE_EXTENSIONS:
        return OFFICE_HANDLER
    return ARCHIVE_HANDLER


def compress_file(
    src: str | Path,
    output_dir: str | Path | None = None,
    settings: CompressionSettings = PRESETS[DEFAULT_PRESET],
) -> CompressionResult:
    """Compress one file. The output is only written if it is smaller than the original."""
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(f"File not found: {src}")

    out_dir = Path(output_dir) if output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    handler = get_handler(src)
    suffix = handler.output_suffix(src, settings)
    original_size = src.stat().st_size

    with tempfile.TemporaryDirectory(dir=out_dir, prefix=".compressing-") as tmp:
        tmp_output = Path(tmp) / f"output{suffix}"
        handler.compress(src, tmp_output, settings)
        new_size = tmp_output.stat().st_size
        if new_size >= original_size:
            return CompressionResult(src, None, original_size, original_size)

        destination = unique_path(out_dir, f"{src.stem}{OUTPUT_TAG}", suffix)
        shutil.move(str(tmp_output), destination)
        return CompressionResult(src, destination, original_size, new_size)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
