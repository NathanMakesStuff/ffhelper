"""Cooldowns read straight off the hotbar: an icon counts as ready when it matches a picture of it taken while ready."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

READY_FOR = 3.0  # seconds an icon must keep matching before the coach may nag about it
_MARGIN = 0.15  # icon edges hold proc glows, borders and charge counts, so they're ignored
_MIN_BRIGHTNESS = 0.9  # a cooldown darkens the whole icon
_PIXEL_CHANGE = 32
_MAX_CHANGED = 0.05  # the recast sweep and countdown number change part of it


def reference_path(config_path: Path, name: str) -> Path:
    return config_path.parent / "skills" / (re.sub(r'[\\/:*?"<>|]', "_", name) + ".png")


def save_reference(config_path: Path, name: str, icon: np.ndarray) -> Path:
    path = reference_path(config_path, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, png = cv2.imencode(".png", icon)
    if not ok:
        raise ValueError(f"Could not encode the {name} icon")
    path.write_bytes(png.tobytes())  # cv2.imwrite can't handle non-ASCII Windows paths
    return path


def _core(icon: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY).astype(np.int16)
    height, width = gray.shape
    dy, dx = round(height * _MARGIN), round(width * _MARGIN)
    return gray[dy : height - dy, dx : width - dx]


def compare(icon: np.ndarray, reference: np.ndarray) -> tuple[float, float]:
    """(brightness relative to the ready picture, fraction of pixels that changed)."""
    if icon.shape != reference.shape:
        icon = cv2.resize(icon, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_AREA)
    live, ready = _core(icon), _core(reference)
    brightness = float(live.mean()) / max(float(ready.mean()), 1.0)
    changed = np.count_nonzero(np.abs(live - ready) > _PIXEL_CHANGE) / live.size
    return brightness, float(changed)


class SkillWatch:
    """Tracks how long each watched ability has looked ready."""

    def __init__(self, references: Mapping[str, np.ndarray]):
        self.references = dict(references)
        self._ready_since: dict[str, float] = {}

    @classmethod
    def load(cls, config_path: Path, names: Iterable[str]) -> SkillWatch:
        references = {}
        for name in names:
            path = reference_path(config_path, name)
            icon = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR) if path.is_file() else None
            if icon is None:
                log.warning("No picture of %s while ready, so it isn't tracked. Run: ffhelper calibrate", name)
            else:
                references[name] = icon
        return cls(references)

    def update(self, icons: Mapping[str, np.ndarray], now: float) -> list[str]:
        """Watched abilities that have looked ready for at least READY_FOR seconds."""
        waiting = []
        for name, reference in self.references.items():
            brightness, changed = compare(icons[name], reference)
            log.debug("[skills] %s: brightness %.2f, changed %.0f%%", name, brightness, changed * 100)
            if brightness >= _MIN_BRIGHTNESS and changed <= _MAX_CHANGED:
                if now - self._ready_since.setdefault(name, now) >= READY_FOR:
                    waiting.append(name)
            else:
                self._ready_since.pop(name, None)
        return waiting
