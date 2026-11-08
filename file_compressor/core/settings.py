from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArchiveFormat(str, Enum):
    ZIP = "zip"
    SEVEN_ZIP = "7z"


@dataclass(frozen=True)
class CompressionSettings:
    jpeg_quality: int = 72
    max_image_dimension: int | None = 2560
    png_max_colors: int | None = None
    grayscale: bool = False
    archive_format: ArchiveFormat = ArchiveFormat.ZIP


PRESETS: dict[str, CompressionSettings] = {
    "Extreme (smallest, low quality)": CompressionSettings(
        jpeg_quality=35, max_image_dimension=1200, png_max_colors=64
    ),
    "Maximum compression": CompressionSettings(
        jpeg_quality=55, max_image_dimension=1600, png_max_colors=256
    ),
    "Balanced": CompressionSettings(jpeg_quality=72, max_image_dimension=2560),
    "High quality": CompressionSettings(jpeg_quality=85, max_image_dimension=None),
}

DEFAULT_PRESET = "Balanced"
