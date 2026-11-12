"""Screen capture of the configured regions."""

from __future__ import annotations

from collections.abc import Iterable

import cv2
import mss
import numpy as np

from .config import Config, ConfigError


def _monitor(sct: mss.MSS, index: int) -> dict[str, int]:
    monitors = sct.monitors
    if not 1 <= index < len(monitors):
        raise ConfigError(
            f"[capture] monitor = {index}, but this PC has {len(monitors) - 1} monitor(s)"
        )
    return monitors[index]


class Grabber:
    """Captures named regions of the game monitor. Create one per worker thread."""

    def __init__(self, config: Config, names: Iterable[str]):
        self._sct = mss.MSS()
        monitor = _monitor(self._sct, config.monitor)
        self._boxes = {}
        for name in names:
            r = config.region(name)
            self._boxes[name] = {
                "left": monitor["left"] + r.x,
                "top": monitor["top"] + r.y,
                "width": r.w,
                "height": r.h,
            }

    def grab(self, name: str) -> np.ndarray:
        """BGR pixels of one region."""
        return cv2.cvtColor(np.asarray(self._sct.grab(self._boxes[name])), cv2.COLOR_BGRA2BGR)

    def close(self) -> None:
        self._sct.close()


def screenshot(monitor_index: int) -> tuple[np.ndarray, int]:
    """Whole-monitor BGR screenshot, plus the monitor width in capture coordinates."""
    with mss.MSS() as sct:
        monitor = _monitor(sct, monitor_index)
        image = cv2.cvtColor(np.asarray(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
        return image, monitor["width"]


def monitor_width(monitor_index: int) -> int:
    with mss.MSS() as sct:
        return _monitor(sct, monitor_index)["width"]
