"""Generates the application icon: file_compressor/resources/icon.png and icon.ico."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
RESOURCES = Path(__file__).resolve().parent.parent / "file_compressor" / "resources"

TOP_COLOR = (64, 145, 255)
BOTTOM_COLOR = (24, 76, 196)
ARROW_COLOR = (30, 98, 222)
FOLD_COLOR = (200, 218, 245)


def _gradient(size: int) -> Image.Image:
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        gradient.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(TOP_COLOR, BOTTOM_COLOR)))
    return gradient.resize((size, size))


def draw_icon() -> Image.Image:
    s = SIZE
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, s - 40, s - 40), radius=210, fill=255)
    icon.paste(_gradient(s), (0, 0), mask)

    draw = ImageDraw.Draw(icon)
    left, top, right, bottom, fold = 262, 170, 762, 854, 150
    page = [(left, top), (right - fold, top), (right, top + fold), (right, bottom), (left, bottom)]
    draw.rounded_rectangle((left + 12, top + 24, right + 12, bottom + 24), radius=40, fill=(10, 40, 120, 90))
    draw.polygon(page, fill="white")
    draw.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=FOLD_COLOR)

    # Two arrows pressing towards a centre bar: the "compress" symbol.
    cx, cy = (left + right) // 2, (top + bottom) // 2 + 30
    bar_half, bar_h = 170, 34
    draw.rounded_rectangle((cx - bar_half, cy - bar_h // 2, cx + bar_half, cy + bar_h // 2), radius=17, fill=ARROW_COLOR)
    for direction in (-1, 1):
        tip_y = cy + direction * 60
        base_y = cy + direction * 190
        shaft_end = cy + direction * 290
        draw.polygon([(cx, tip_y), (cx - 125, base_y), (cx + 125, base_y)], fill=ARROW_COLOR)
        draw.rectangle((cx - 42, min(base_y, shaft_end), cx + 42, max(base_y, shaft_end)), fill=ARROW_COLOR)
    return icon


def main() -> None:
    RESOURCES.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(RESOURCES / "icon.png", optimize=True)
    icon.save(
        RESOURCES / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Icons written to {RESOURCES}")


if __name__ == "__main__":
    main()
