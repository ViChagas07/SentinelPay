import io
import random
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _font(size: int = 64) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def clean_image(width: int = 1600, height: int = 1200) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = _font(72)
    draw.text(
        (80, 90),
        "PAYSENTINELIQ SYNTHETIC DOCUMENT",
        fill="black",
        font=font,
    )
    draw.text(
        (80, 220),
        "ACCOUNT 12345 - TEST ONLY",
        fill="black",
        font=_font(52),
    )
    draw.line((80, 330, width - 80, 330), fill="black", width=4)
    for index in range(6):
        draw.line(
            (80, 390 + index * 70, width - 150, 390 + index * 70),
            fill="black",
            width=2,
        )
    draw.rectangle(
        (width - 420, height - 260, width - 80, height - 80),
        outline="black",
        width=5,
    )
    return image


def clean_image_bytes(width: int = 1600, height: int = 1200) -> bytes:
    return _png_bytes(clean_image(width, height))


def blurred_image_bytes() -> bytes:
    return _png_bytes(clean_image().filter(ImageFilter.GaussianBlur(6)))


def small_image_bytes() -> bytes:
    return _png_bytes(clean_image(400, 300))


def pasted_image_bytes() -> bytes:
    image = clean_image()
    rng = random.Random(7)
    patch = Image.new("RGB", (180, 180), "white")
    draw = ImageDraw.Draw(patch)
    for _ in range(22):
        x0 = rng.randint(0, 150)
        y0 = rng.randint(0, 150)
        x1 = min(179, x0 + rng.randint(8, 35))
        y1 = min(179, y0 + rng.randint(8, 35))
        color = "black" if rng.random() > 0.35 else "gray"
        draw.rectangle((x0, y0, x1, y1), fill=color)
    draw.line((0, 90, 180, 90), fill="black", width=6)
    draw.ellipse((45, 35, 135, 125), outline="black", width=7)

    patch_array = np.array(patch).astype(np.int16)
    noise_rng = np.random.default_rng(7)
    noise = np.repeat(
        noise_rng.integers(-35, 36, size=(180, 180, 1), dtype=np.int16),
        3,
        axis=2,
    )
    noisy_patch = Image.fromarray(np.clip(patch_array + noise, 0, 255).astype(np.uint8))
    image.paste(noisy_patch, (220, 500))
    image.paste(noisy_patch, (1080, 760))
    return _png_bytes(image)


def native_pdf_bytes(pages: int = 1) -> bytes:
    document = pymupdf.open()
    document.set_metadata(
        {
            "producer": "PaySentinelIQ Synthetic",
            "creator": "tests",
            "creationDate": "D:20260101000000Z",
            "modDate": "D:20260102000000Z",
        }
    )
    for index in range(pages):
        page = document.new_page(width=595, height=842)
        page.insert_text(
            (72, 100),
            "PAYSENTINELIQ SYNTHETIC PDF",
            fontsize=24,
        )
        page.insert_text(
            (72, 150),
            f"Page {index + 1} - test only - 12345",
            fontsize=16,
        )
        page.insert_text(
            (72, 200),
            "This document has a native text layer.",
            fontsize=16,
        )
    data = bytes(document.tobytes())
    document.close()
    return data


def scanned_pdf_bytes() -> bytes:
    png = clean_image_bytes(900, 1200)
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=png)
    data = bytes(document.tobytes())
    document.close()
    return data


def pdf_with_incremental_marker() -> bytes:
    return native_pdf_bytes() + b"\n%%EOF\n% /Prev 1 0 R\n"


def pdf_with_layers_marker() -> bytes:
    return native_pdf_bytes() + b"\n/OCProperties\n"


def write_fixtures(directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "clean.png": clean_image_bytes(),
        "pasted.png": pasted_image_bytes(),
        "blurred.png": blurred_image_bytes(),
        "small.png": small_image_bytes(),
        "native.pdf": native_pdf_bytes(),
        "scanned.pdf": scanned_pdf_bytes(),
        "incremental.pdf": pdf_with_incremental_marker(),
        "layers.pdf": pdf_with_layers_marker(),
    }
    written: list[Path] = []
    for name, data in files.items():
        path = directory / name
        path.write_bytes(data)
        written.append(path)
    return written


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
