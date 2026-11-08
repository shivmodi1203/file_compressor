from __future__ import annotations

import zipfile
from pathlib import Path

from .images import encode_image
from .settings import CompressionSettings

OFFICE_EXTENSIONS = {
    ".docx", ".docm", ".dotx",
    ".xlsx", ".xlsm", ".xltx",
    ".pptx", ".pptm", ".ppsx", ".potx",
    ".odt", ".ods", ".odp", ".odg",
    ".epub",
}

_EMBEDDED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".webp"}


def compress_office(src: Path, dst: Path, settings: CompressionSettings) -> None:
    """Office/ODF/EPUB files are ZIP containers: shrink embedded images and repack at max level."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if Path(info.filename).suffix.lower() in _EMBEDDED_IMAGE_EXTENSIONS:
                data = _shrink_embedded_image(data, settings)

            out_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            out_info.external_attr = info.external_attr
            # ODF and EPUB require the "mimetype" entry to be stored uncompressed.
            if info.filename == "mimetype":
                out_info.compress_type = zipfile.ZIP_STORED
                zout.writestr(out_info, data)
            else:
                out_info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(out_info, data, compresslevel=9)


def _shrink_embedded_image(data: bytes, settings: CompressionSettings) -> bytes:
    # Documents reference images by file name, so the format must stay the same.
    try:
        encoded, _ = encode_image(data, settings, allow_format_change=False)
    except Exception:
        return data
    return encoded if len(encoded) < len(data) else data
