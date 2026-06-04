"""PDF loading and page orientation utilities."""

import numpy as np
from PIL import Image

try:
    import fitz
except ImportError:  # pragma: no cover - depends on the execution environment
    fitz = None


def pdf_to_images(pdf_path: str) -> list[Image.Image]:
    if fitz is None:
        print("PyMuPDF is not installed. Install it with: python3 -m pip install PyMuPDF")
        return []
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        print(f"Cannot open PDF {pdf_path}: {exc}")
        return []
    images = []
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)
    finally:
        doc.close()
    return images


def correct_orientation(image: Image.Image) -> Image.Image:
    if not isinstance(image, Image.Image) or image.width <= 0 or image.height <= 0:
        return Image.new("RGB", (1, 1), "white")
    # Compare dark pixel density in top vs bottom band to detect 180° flip
    arr = np.nan_to_num(np.array(image.convert("L")), nan=255.0, posinf=255.0, neginf=0.0)
    h = arr.shape[0]
    if h < 500:
        return image
    top_dark = np.sum(arr[250:420, :] < 150)
    bot_dark = np.sum(arr[h - 420:h - 250, :] < 150)
    if bot_dark > top_dark:
        return image.rotate(180)
    return image
