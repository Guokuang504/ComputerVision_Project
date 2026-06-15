"""Field extraction from PAGE-01 and EXAM pages."""

import cv2
import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# PAGE-01 ROI definitions (pixel coords for ~2482x3510 images)
# ---------------------------------------------------------------------------

HEADER_Y = (330, 420)
MODULE_X = (330, 700)
PROFESSOR_X = (900, 1180)
DATE_X = (1500, 1820)
CODE_X = (1980, 2445)

FIRSTNAME_ROI = (160, 615, 1200, 710)
LASTNAME_ROI = (160, 775, 1200, 870)

NOTE_MAX_ROI = (1350, 2420, 1540, 2540)
NOTE_VALID_ROI = (1350, 2590, 1540, 2700)

# ---------------------------------------------------------------------------
# Numeric answer box size thresholds
# ---------------------------------------------------------------------------

MANTISSE_SIZE = {"min_w": 250, "max_w": 450, "min_h": 100, "max_h": 160}
EXPOSANT_SIZE = {"min_w": 100, "max_w": 220, "min_h": 70, "max_h": 140}


# ---------------------------------------------------------------------------
# PAGE-01 field cropping
# ---------------------------------------------------------------------------

def extract_printed_crops(image: Image.Image) -> dict[str, Image.Image]:
    image = _safe_image(image)
    y0, y1 = HEADER_Y
    return {
        "module": _safe_crop(image, (MODULE_X[0], y0, MODULE_X[1], y1)),
        "professor": _safe_crop(image, (PROFESSOR_X[0], y0, PROFESSOR_X[1], y1)),
        "date": _safe_crop(image, (DATE_X[0], y0, DATE_X[1], y1)),
        "code": _safe_crop(image, (CODE_X[0], y0, CODE_X[1], y1)),
        "note_max": _safe_crop(image, NOTE_MAX_ROI),
        "note_valid": _safe_crop(image, NOTE_VALID_ROI),
    }


def extract_handwritten_crops(image: Image.Image) -> dict[str, Image.Image]:
    image = _safe_image(image)
    return {
        "firstname": _safe_crop(image, FIRSTNAME_ROI),
        "lastname": _safe_crop(image, LASTNAME_ROI),
    }


# ---------------------------------------------------------------------------
# EXAM page — numeric answer zone detection
# ---------------------------------------------------------------------------

def find_numeric_zones(image: Image.Image) -> list[dict]:
    image = _safe_image(image)
    arr = np.array(image)
    if arr.size == 0:
        return []
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Find quadrilateral contours in the answer-box size range
    rects = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw <= 0 or bh <= 0:
            continue
        peri = cv2.arcLength(cnt, True)
        if peri <= 0:
            continue
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        if bw < 80 or bh < 60 or bw > 600 or bh > 200:
            continue
        rects.append((x, y, bw, bh))

    rects = _deduplicate_rects(rects)

    # Classify by size
    mantisses = []
    exposants = []
    for (x, y, bw, bh) in rects:
        if (MANTISSE_SIZE["min_w"] <= bw <= MANTISSE_SIZE["max_w"] and
                MANTISSE_SIZE["min_h"] <= bh <= MANTISSE_SIZE["max_h"]):
            mantisses.append((x, y, bw, bh))
        elif (EXPOSANT_SIZE["min_w"] <= bw <= EXPOSANT_SIZE["max_w"] and
              EXPOSANT_SIZE["min_h"] <= bh <= EXPOSANT_SIZE["max_h"]):
            exposants.append((x, y, bw, bh))

    # Group: for each mantisse find its exposant (above) and unite (right).
    # Unit boxes have nearly the same size as mantisse boxes, so they are first
    # detected as "mantisses". Mark right-hand boxes as units to avoid creating
    # an extra numeric answer row and shifting all following question numbers.
    mantisses.sort(key=lambda b: b[1])
    unit_boxes: set[tuple[int, int, int, int]] = set()
    for mx, my, mw, mh in mantisses:
        for ux, uy, uw, uh in mantisses:
            if ux <= mx + mw:
                continue
            if abs(uy - my) < 55 and 80 <= (ux - (mx + mw)) <= 520:
                unit_boxes.add((ux, uy, uw, uh))

    zones = []

    for mx, my, mw, mh in mantisses:
        if (mx, my, mw, mh) in unit_boxes:
            continue
        exp_crop = None
        for ex, ey, ew, eh in exposants:
            if ey < my and (my - ey) < 250 and abs(ex - (mx + mw // 2)) < mw:
                exp_crop = _safe_crop(image, (ex + 4, ey + 4, ex + ew - 4, ey + eh - 4))
                break

        unite_crop = None
        for ux, uy, uw, uh in sorted(unit_boxes, key=lambda b: b[0]):
            if ux > mx + mw and abs(uy - my) < 55:
                unite_crop = _safe_crop(image, (ux + 4, uy + 4, ux + uw - 4, uy + uh - 4))
                break

        mant_crop = _safe_crop(image, (mx + 4, my + 4, mx + mw - 4, my + mh - 4))
        zones.append({
            "mantisse": mant_crop,
            "exposant": exp_crop,
            "unite": unite_crop,
            "y": my,
        })

    return zones


def _deduplicate_rects(rects: list, threshold: int = 20) -> list:
    if not rects:
        return []
    rects = sorted(rects, key=lambda r: r[2] * r[3], reverse=True)
    kept = []
    for r in rects:
        duplicate = False
        for k in kept:
            if (abs(r[0] - k[0]) < threshold and abs(r[1] - k[1]) < threshold and
                    abs(r[2] - k[2]) < threshold and abs(r[3] - k[3]) < threshold):
                duplicate = True
                break
        if not duplicate:
            kept.append(r)
    return kept


def _safe_image(image: Image.Image) -> Image.Image:
    if isinstance(image, Image.Image) and image.width > 0 and image.height > 0:
        return image.convert("RGB")
    return Image.new("RGB", (2482, 3510), "white")


def _safe_crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    width, height = image.size
    x0, y0, x1, y1 = box
    x0 = max(0, min(width, int(x0)))
    x1 = max(0, min(width, int(x1)))
    y0 = max(0, min(height, int(y0)))
    y1 = max(0, min(height, int(y1)))
    if x1 <= x0 or y1 <= y0:
        return Image.new("RGB", (1, 1), "white")
    return image.crop((x0, y0, x1, y1))
