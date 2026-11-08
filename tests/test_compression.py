from __future__ import annotations

import dataclasses
import io
import random
import zipfile
from pathlib import Path

import pikepdf
import pytest
from PIL import Image
from pikepdf import Name

from file_compressor.core import PRESETS, ArchiveFormat, compress_file
from file_compressor.core.settings import CompressionSettings

BALANCED = PRESETS["Balanced"]


def _photo_like(size=(3000, 2000)) -> Image.Image:
    """Smooth gradient with noise: compresses like a real photo."""
    base = Image.linear_gradient("L").resize(size).convert("RGB")
    noise = Image.effect_noise(size, 40).convert("RGB")
    return Image.blend(base, noise, 0.3)


def test_jpeg_is_reduced_and_resized(tmp_path: Path):
    src = tmp_path / "photo.jpg"
    _photo_like().save(src, "JPEG", quality=98)

    result = compress_file(src, tmp_path / "out", BALANCED)

    assert result.reduced
    assert result.output.name == "photo_compressed.jpg"
    assert result.compressed_size < result.original_size
    with Image.open(result.output) as img:
        assert max(img.size) == BALANCED.max_image_dimension


def test_bmp_becomes_png(tmp_path: Path):
    src = tmp_path / "picture.bmp"
    Image.new("RGB", (800, 600), "steelblue").save(src)

    result = compress_file(src, settings=BALANCED)

    assert result.output == tmp_path / "picture_compressed.png"
    with Image.open(result.output) as img:
        assert img.format == "PNG"


def test_png_quantized_with_max_compression(tmp_path: Path):
    src = tmp_path / "chart.png"
    _photo_like((1200, 800)).save(src)

    result = compress_file(src, settings=PRESETS["Maximum compression"])

    assert result.reduced
    with Image.open(result.output) as img:
        assert img.mode == "P"


def test_already_small_file_is_not_written(tmp_path: Path):
    src = tmp_path / "tiny.png"
    Image.new("L", (4, 4)).save(src, optimize=True)

    result = compress_file(src, settings=BALANCED)

    assert not result.reduced
    assert result.output is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["tiny.png"]


def test_pdf_images_are_recompressed(tmp_path: Path):
    src = tmp_path / "scan.pdf"
    pages = [_photo_like((2480, 3508)) for _ in range(2)]
    pages[0].save(src, "PDF", save_all=True, append_images=pages[1:], quality=100)

    result = compress_file(src, settings=BALANCED)

    assert result.reduced
    assert result.saved_percent > 30
    with pikepdf.open(result.output) as pdf:
        assert len(pdf.pages) == 2


def _colour_pdf(path: Path) -> None:
    colour = Image.merge("RGB", [_photo_like((2480, 3508)).getchannel(0)] * 2 + [Image.new("L", (2480, 3508), 200)])
    colour.save(path, "PDF", quality=95)


def test_extreme_is_smaller_than_maximum(tmp_path: Path):
    src = tmp_path / "doc.pdf"
    _colour_pdf(src)

    maximum = compress_file(src, tmp_path / "max", PRESETS["Maximum compression"])
    extreme = compress_file(src, tmp_path / "extreme", PRESETS["Extreme (smallest, low quality)"])

    assert extreme.compressed_size < maximum.compressed_size


def test_grayscale_pdf_is_smaller_and_gray(tmp_path: Path):
    src = tmp_path / "doc.pdf"
    _colour_pdf(src)
    settings = PRESETS["Maximum compression"]

    colour = compress_file(src, tmp_path / "colour", settings)
    gray = compress_file(src, tmp_path / "gray", dataclasses.replace(settings, grayscale=True))

    assert gray.compressed_size < colour.compressed_size
    with pikepdf.open(gray.output) as pdf:
        image = next(iter(pdf.pages[0].Resources.XObject.values()))
        assert image.ColorSpace == Name.DeviceGray


def test_grayscale_image(tmp_path: Path):
    src = tmp_path / "photo.jpg"
    _photo_like().save(src, "JPEG", quality=98)

    result = compress_file(src, settings=dataclasses.replace(BALANCED, grayscale=True))

    with Image.open(result.output) as img:
        assert img.mode == "L"


def test_pdf_flate_image_with_soft_mask(tmp_path: Path):
    src = tmp_path / "transparent.pdf"
    img = _photo_like((2000, 1500))
    alpha = Image.linear_gradient("L").resize(img.size)
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(600, 450))
    image_args = dict(Type=Name.XObject, Subtype=Name.Image, Width=2000, Height=1500, BitsPerComponent=8)
    smask = pikepdf.Stream(pdf, alpha.tobytes(), ColorSpace=Name.DeviceGray, **image_args)
    image = pikepdf.Stream(pdf, img.tobytes(), ColorSpace=Name.DeviceRGB, SMask=smask, **image_args)
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    page.Contents = pdf.make_stream(b"q 600 0 0 450 0 0 cm /Im0 Do Q")
    pdf.save(src)

    result = compress_file(src, settings=BALANCED)

    assert result.saved_percent > 50
    with pikepdf.open(result.output) as out:
        compressed = out.pages[0].Resources.XObject.Im0
        assert compressed.Filter == Name.DCTDecode
        assert compressed.Width == 2000
        assert compressed.SMask.Width == 2000


def test_docx_media_is_shrunk(tmp_path: Path):
    src = tmp_path / "report.docx"
    image = io.BytesIO()
    _photo_like().save(image, "JPEG", quality=98)
    with zipfile.ZipFile(src, "w", zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml", "<Types/>" * 50)
        z.writestr("word/document.xml", "<w:document>hello</w:document>" * 200)
        z.writestr("word/media/image1.jpeg", image.getvalue())

    result = compress_file(src, settings=BALANCED)

    assert result.reduced
    with zipfile.ZipFile(result.output) as z:
        assert z.namelist() == ["[Content_Types].xml", "word/document.xml", "word/media/image1.jpeg"]
        assert z.testzip() is None
        with Image.open(io.BytesIO(z.read("word/media/image1.jpeg"))) as img:
            assert img.format == "JPEG"


def test_odt_keeps_mimetype_stored(tmp_path: Path):
    src = tmp_path / "notes.odt"
    with zipfile.ZipFile(src, "w", zipfile.ZIP_STORED) as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        z.writestr("content.xml", "<office:text>lorem ipsum</office:text>" * 500)

    result = compress_file(src, settings=BALANCED)

    with zipfile.ZipFile(result.output) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED


@pytest.mark.parametrize("archive_format, suffix", [(ArchiveFormat.ZIP, ".txt.zip"), (ArchiveFormat.SEVEN_ZIP, ".txt.7z")])
def test_other_files_are_archived(tmp_path: Path, archive_format, suffix):
    src = tmp_path / "log.txt"
    rng = random.Random(0)
    src.write_text("\n".join(f"line {rng.randint(0, 50)} status=OK" for _ in range(20000)))

    settings = CompressionSettings(archive_format=archive_format)
    result = compress_file(src, settings=settings)

    assert result.output.name == f"log_compressed{suffix}"
    assert result.saved_percent > 50


def test_existing_output_is_not_overwritten(tmp_path: Path):
    src = tmp_path / "data.csv"
    src.write_text("a,b,c\n" * 10000)
    first = compress_file(src, settings=BALANCED)
    second = compress_file(src, settings=BALANCED)

    assert first.output.name == "data_compressed.csv.zip"
    assert second.output.name == "data_compressed (2).csv.zip"
