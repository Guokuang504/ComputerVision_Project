from __future__ import annotations

import json
import csv
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class DebugLogger:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.counts: Counter[str] = Counter()
        self.events: list[dict[str, Any]] = []

    def inc(self, key: str, amount: int = 1) -> None:
        self.counts[key] += amount

    def event(self, category: str, name: str, status: str, **payload: Any) -> None:
        self.inc(f"{category}_{status}")
        row = {"category": category, "name": name, "status": status}
        row.update({k: _json_safe(v) for k, v in payload.items()})
        self.events.append(row)

    def save_image(self, category: str, name: str, image: Any) -> str:
        folder = self.root / category
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / _safe_filename(name)
        try:
            if isinstance(image, Image.Image):
                image.convert("RGB").save(path)
            else:
                arr = np.asarray(image)
                if arr.size == 0:
                    return ""
                arr = np.nan_to_num(arr, nan=255.0, posinf=255.0, neginf=0.0)
                arr = np.clip(arr, 0, 255).astype(np.uint8)
                if arr.ndim == 2:
                    Image.fromarray(arr, mode="L").save(path)
                else:
                    Image.fromarray(arr[..., :3]).convert("RGB").save(path)
            return str(path)
        except Exception as exc:
            self.event(category, name, "debug_save_failed", error=str(exc))
            return ""

    def write_summary(self, path: str | Path) -> None:
        summary = {
            "counts": dict(sorted(self.counts.items())),
            "events": self.events,
        }
        Path(path).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_events_csv(self, category: str, path: str | Path) -> None:
        rows = [event for event in self.events if event.get("category") == category]
        if not rows:
            return
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(name))
    if not cleaned.lower().endswith((".png", ".jpg", ".jpeg")):
        cleaned += ".png"
    return cleaned


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    return str(value)
