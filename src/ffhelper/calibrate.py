"""Pick screen regions by dragging boxes on a screenshot, then save them to config.toml."""

from __future__ import annotations

import base64
import time
import tkinter as tk
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
import tomlkit

from .capture import monitor_width, screenshot
from .config import Config, ConfigError

HINTS = {
    "castbar": "the boss's cast bar, including the spell name",
    "hotbars": "your hotbars",
    "buffs": "your status effects (buffs and debuffs)",
    "job_gauge": "your job gauge",
}
MIN_BOX = 4  # preview pixels; anything smaller was a click, not a drag


def to_region(box: Sequence[float], scale: float) -> list[int]:
    """Preview box (x0, y0, x1, y1), drawn in any direction, to [x, y, w, h] in capture coordinates."""
    x0, x1 = sorted((box[0], box[2]))
    y0, y1 = sorted((box[1], box[3]))
    return [round(x0 / scale), round(y0 / scale), round((x1 - x0) / scale), round((y1 - y0) / scale)]


def save_regions(path: Path, regions: dict[str, list[int]]) -> None:
    """Update [regions] in place, keeping the rest of the file and its comments."""
    doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    if "regions" not in doc:
        doc["regions"] = tomlkit.table()
    for name, box in regions.items():
        doc["regions"][name] = box
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


class RegionPicker:
    """Drag a box for each region in turn. Enter = keep box, S = skip, Esc = quit without saving."""

    def __init__(
        self,
        image: np.ndarray,
        names: list[str],
        existing: dict[str, list[int]],
        pixel_scale: float,
    ):
        self.names = names
        self._picked: dict[str, list[int]] = {}
        self._cancelled = False
        self._index = 0
        self._start = (0.0, 0.0)
        self._box: int | None = None

        self.root = tk.Tk()
        self.root.title("FFHelper calibration")
        self.root.attributes("-topmost", True)
        height, width = image.shape[:2]
        fit = min(
            1.0,
            0.95 * self.root.winfo_screenwidth() / width,
            0.85 * self.root.winfo_screenheight() / height,
        )
        # Preview pixels per capture coordinate (mss reports Retina displays in points, not pixels).
        self.scale = pixel_scale * fit
        preview = cv2.resize(image, (round(width * fit), round(height * fit)), interpolation=cv2.INTER_AREA)
        _, png = cv2.imencode(".png", preview)
        self._photo = tk.PhotoImage(data=base64.b64encode(png.tobytes()).decode("ascii"))

        self.label = tk.Label(self.root, anchor="w", font=("TkDefaultFont", 13), padx=8, pady=6)
        self.label.pack(fill="x")
        self.canvas = tk.Canvas(
            self.root,
            width=preview.shape[1],
            height=preview.shape[0],
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        for name, (x, y, w, h) in existing.items():
            if w and h:
                self._mark(name, x * self.scale, y * self.scale, (x + w) * self.scale, (y + h) * self.scale, "gray75")

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.root.bind("<Return>", lambda _e: self._advance(keep=True))
        self.root.bind("<KeyPress-s>", lambda _e: self._advance(keep=False))
        self.root.bind("<Escape>", lambda _e: self._cancel())
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)
        self._show_prompt()

    def run(self) -> dict[str, list[int]] | None:
        """Picked regions by name, or None if cancelled."""
        self.root.focus_force()
        self.root.mainloop()
        return None if self._cancelled else self._picked

    def _mark(self, name: str, x0: float, y0: float, x1: float, y1: float, color: str) -> None:
        self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, dash=(4, 4))
        self.canvas.create_text(min(x0, x1) + 3, min(y0, y1) + 3, text=name, anchor="nw", fill=color)

    def _on_press(self, event: tk.Event) -> None:
        self._start = (event.x, event.y)
        if self._box is not None:
            self.canvas.delete(self._box)
        self._box = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#00ff66", width=2)

    def _on_drag(self, event: tk.Event) -> None:
        if self._box is not None:
            self.canvas.coords(self._box, *self._start, event.x, event.y)

    def _advance(self, keep: bool) -> None:
        name = self.names[self._index]
        if self._box is not None:
            x0, y0, x1, y1 = self.canvas.coords(self._box)
            self.canvas.delete(self._box)
            self._box = None
            if keep and abs(x1 - x0) >= MIN_BOX and abs(y1 - y0) >= MIN_BOX:
                self._picked[name] = to_region((x0, y0, x1, y1), self.scale)
                self._mark(name, x0, y0, x1, y1, "#ffaa00")
        self._index += 1
        if self._index == len(self.names):
            self.root.destroy()
        else:
            self._show_prompt()

    def _cancel(self) -> None:
        self._cancelled = True
        self.root.destroy()

    def _show_prompt(self) -> None:
        name = self.names[self._index]
        self.label.configure(
            text=f"{self._index + 1}/{len(self.names)}  Drag a box around {HINTS.get(name, name)}."
            "    Enter = keep box    S = skip    Esc = quit without saving"
        )


def calibrate(config: Config, delay: float, image_path: Path | None) -> None:
    if image_path is not None:
        image = cv2.imread(str(image_path))
        if image is None:
            raise ConfigError(f"Can't read image: {image_path}")
        width = monitor_width(config.monitor)
    else:
        print(f"Switch to the game now. Taking a screenshot in {delay:g} seconds...")
        time.sleep(delay)
        image, width = screenshot(config.monitor)

    names = list(config.regions) or list(HINTS)
    existing = {name: [r.x, r.y, r.w, r.h] for name, r in config.regions.items()}
    picked = RegionPicker(image, names, existing, image.shape[1] / width).run()
    if picked is None:
        print("Cancelled. Nothing saved.")
    elif not picked:
        print("No boxes drawn. Nothing changed.")
    else:
        save_regions(config.path, picked)
        for name, box in picked.items():
            print(f"  {name} = {box}")
        print(f"Saved to {config.path}")
