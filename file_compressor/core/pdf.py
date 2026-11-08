from __future__ import annotations

import io
from pathlib import Path

import pikepdf
from pikepdf import Array, Name, PdfImage

from .images import downscale
from .settings import CompressionSettings

PDF_EXTENSIONS = {".pdf"}

# Images smaller than this are not worth re-encoding.
_MIN_IMAGE_BYTES = 20_000
_SKIPPED_FILTERS = {Name.JBIG2Decode, Name.CCITTFaxDecode, Name.JPXDecode}


class EncryptedPdfError(ValueError):
    pass


def compress_pdf(src: Path, dst: Path, settings: CompressionSettings) -> None:
    try:
        pdf = pikepdf.open(src)
    except pikepdf.PasswordError as exc:
        raise EncryptedPdfError("PDF is password protected") from exc

    with pdf:
        if pdf.is_encrypted:
            raise EncryptedPdfError("Encrypted PDFs are not supported")

        images = [obj for obj in pdf.objects if _is_image(obj)]
        soft_masks = {img.SMask.objgen for img in images if isinstance(img.get("/SMask"), pikepdf.Stream)}
        for image in images:
            if image.objgen not in soft_masks:
                _recompress_image(image, settings)

        pdf.remove_unreferenced_resources()
        pdf.save(
            dst,
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )


def _is_image(obj) -> bool:
    return isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == Name.Image


def _filters(image: pikepdf.Stream) -> list:
    value = image.get("/Filter")
    if isinstance(value, Array):
        return list(value)
    return [value] if value is not None else []


def _is_simple_colorspace(cs) -> bool:
    """RGB/gray colour spaces that survive conversion to a DeviceRGB/DeviceGray JPEG."""
    if cs in (Name.DeviceRGB, Name.DeviceGray):
        return True
    if isinstance(cs, Array) and len(cs) >= 2:
        if cs[0] == Name.ICCBased:
            return int(cs[1].get("/N", 0)) in (1, 3)
        if cs[0] == Name.Indexed:
            return _is_simple_colorspace(cs[1])
    return False


def _target_colorspace(original_cs, channels: int):
    if (
        isinstance(original_cs, Array)
        and original_cs[0] == Name.ICCBased
        and int(original_cs[1].get("/N", 0)) == channels
    ):
        return original_cs
    return Name.DeviceRGB if channels == 3 else Name.DeviceGray


def _recompress_image(image: pikepdf.Stream, settings: CompressionSettings) -> None:
    if image.get("/ImageMask", False) or "/Decode" in image:
        return
    if image.get("/BitsPerComponent") != 8:
        return
    if any(f in _SKIPPED_FILTERS for f in _filters(image)):
        return
    colorspace = image.get("/ColorSpace")
    if not _is_simple_colorspace(colorspace):
        return

    raw_size = len(image.read_raw_bytes())
    if raw_size < _MIN_IMAGE_BYTES:
        return

    try:
        pil = PdfImage(image).as_pil_image()
    except Exception:
        return

    # Recent pikepdf versions merge the /SMask into the extracted image; the mask
    # stays in the PDF as its own object, so only the colour channels are re-encoded.
    if pil.mode in ("P", "RGBA"):
        pil = pil.convert("RGB")
    elif pil.mode == "LA":
        pil = pil.convert("L")
    if pil.mode not in ("RGB", "L"):
        return
    # Resizing would break the pixel correspondence with an attached soft mask.
    if "/SMask" not in image:
        pil = downscale(pil, settings.max_image_dimension)

    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=settings.jpeg_quality, optimize=True)
    encoded = buf.getvalue()
    if len(encoded) >= raw_size:
        return

    image.write(encoded, filter=Name.DCTDecode)
    image.Width = pil.width
    image.Height = pil.height
    image.ColorSpace = _target_colorspace(colorspace, 3 if pil.mode == "RGB" else 1)
    image.BitsPerComponent = 8
    if "/DecodeParms" in image:
        del image["/DecodeParms"]
