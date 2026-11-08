from __future__ import annotations

import zipfile
from pathlib import Path

from .settings import ArchiveFormat, CompressionSettings


def archive_output_suffix(src: Path, settings: CompressionSettings) -> str:
    return f"{src.suffix}.{settings.archive_format.value}"


def compress_to_archive(src: Path, dst: Path, settings: CompressionSettings) -> None:
    if settings.archive_format is ArchiveFormat.SEVEN_ZIP:
        import py7zr

        with py7zr.SevenZipFile(dst, "w") as archive:
            archive.write(src, arcname=src.name)
    else:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.write(src, arcname=src.name)
