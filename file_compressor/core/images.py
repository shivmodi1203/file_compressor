from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

from .settings import CompressionSettings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

# Formats with no useful built-in compression are re-encoded losslessly as PNG.
_FORMAT_REMAP = {"BMP": "PNG"}


class UnsupportedImageError(ValueError):
    pass


def image_output_suffix(src: Path, settings: CompressionSettings) -> str:
    return ".png" if src.suffix.lower() == ".bmp" else src.suffix


def compress_image_file(src: Path, dst: Path, settings: CompressionSettings) -> None:
    data, _ = encode_image(src.read_bytes(), settings)
    dst.write_bytes(data)


def encode_image(
    data: bytes, settings: CompressionSettings, allow_format_change: bool = True
) -> tuple[bytes, str]:
    """Re-encode image bytes with the given settings. Returns (bytes, PIL format)."""
    with Image.open(io.BytesIO(data)) as original:
        src_format = original.format
        out_format = _FORMAT_REMAP.get(src_format, src_format) if allow_format_change else src_format
        if out_format not in _SAVERS:
            raise UnsupportedImageError(f"Unsupported image format: {src_format}")

        buf = io.BytesIO()
        if getattr(original, "is_animated", False):
            _save_animated(original, buf, out_format, settings)
            return buf.getvalue(), out_format

        icc_profile = original.info.get("icc_profile")
        img = ImageOps.exif_transpose(original)
        img = downscale(img, settings.max_image_dimension)
        if settings.grayscale:
            img = to_grayscale(img)
            # A colour ICC profile is invalid on a grayscale image.
            icc_profile = None
        _SAVERS[out_format](img, buf, settings, icc_profile)
        return buf.getvalue(), out_format


def downscale(img: Image.Image, max_dimension: int | None) -> Image.Image:
    if max_dimension and max(img.size) > max_dimension:
        img = img.copy()
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return img


def to_grayscale(img: Image.Image) -> Image.Image:
    if img.mode in ("1", "L", "LA"):
        return img
    has_alpha = "A" in img.mode or "transparency" in img.info
    return img.convert("LA" if has_alpha else "L")


def _icc_kwargs(icc_profile: bytes | None) -> dict:
    return {"icc_profile": icc_profile} if icc_profile else {}


def _save_jpeg(img, buf, settings, icc_profile):
    if img.mode not in ("RGB", "L", "CMYK"):
        img = img.convert("RGB")
    img.save(
        buf,
        "JPEG",
        quality=settings.jpeg_quality,
        optimize=True,
        progressive=True,
        **_icc_kwargs(icc_profile),
    )


def _save_png(img, buf, settings, icc_profile):
    if settings.png_max_colors and img.mode in ("RGB", "RGBA"):
        method = Image.Quantize.FASTOCTREE if img.mode == "RGBA" else Image.Quantize.MEDIANCUT
        img = img.quantize(colors=settings.png_max_colors, method=method)
    img.save(buf, "PNG", optimize=True, **_icc_kwargs(icc_profile))


def _save_webp(img, buf, settings, icc_profile):
    if img.mode not in ("RGB", "RGBA"):
        has_alpha = "A" in img.mode or "transparency" in img.info
        img = img.convert("RGBA" if has_alpha else "RGB")
    img.save(buf, "WEBP", quality=settings.jpeg_quality, method=6, **_icc_kwargs(icc_profile))


def _save_tiff(img, buf, settings, icc_profile):
    img.save(buf, "TIFF", compression="tiff_adobe_deflate", **_icc_kwargs(icc_profile))


def _save_gif(img, buf, settings, icc_profile):
    img.save(buf, "GIF", optimize=True)


def _save_animated(img, buf, out_format, settings):
    options = {
        "GIF": {"optimize": True},
        "PNG": {"optimize": True},
        "WEBP": {"quality": settings.jpeg_quality, "method": 6},
        "TIFF": {"compression": "tiff_adobe_deflate"},
    }
    if out_format not in options:
        raise UnsupportedImageError(f"Unsupported animated image format: {out_format}")
    img.save(buf, out_format, save_all=True, **options[out_format])


_SAVERS = {
    "JPEG": _save_jpeg,
    "PNG": _save_png,
    "WEBP": _save_webp,
    "TIFF": _save_tiff,
    "GIF": _save_gif,
}
