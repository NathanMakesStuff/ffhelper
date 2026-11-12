"""Boss-cast callouts loaded from JSON and matched against OCR text."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .config import ConfigError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mechanic:
    cast: str
    say: str
    note: str = ""


def normalize(text: str) -> str:
    # OCR drops and adds spaces and punctuation freely, so only letters and digits are compared.
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _parse_file(path: Path) -> list[Mechanic]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}") from None
    mechanics = []
    for cast, entry in data.get("mechanics", {}).items():
        if isinstance(entry, str):
            entry = {"say": entry}
        if not isinstance(entry, dict) or not isinstance(entry.get("say"), str):
            raise ConfigError(f'{path.name}: "{cast}" needs a "say" text')
        mechanics.append(Mechanic(cast, entry["say"], entry.get("note", "")))
    return mechanics


class MechanicsBook:
    def __init__(self, mechanics: Iterable[Mechanic], cutoff: float = 0.75):
        self.cutoff = cutoff
        self._by_key: dict[str, Mechanic] = {}
        for mechanic in mechanics:
            key = normalize(mechanic.cast)
            if key in self._by_key:
                log.warning("Duplicate cast '%s' ignored", mechanic.cast)
            elif key:
                self._by_key[key] = mechanic

    def __len__(self) -> int:
        return len(self._by_key)

    @classmethod
    def load(cls, path: Path, cutoff: float = 0.75) -> MechanicsBook:
        """Load one JSON file, or every *.json file in a folder."""
        if path.is_dir():
            files = sorted(path.glob("*.json"))
        elif path.is_file():
            files = [path]
        else:
            raise ConfigError(f"Mechanics file or folder not found: {path}")
        return cls((m for f in files for m in _parse_file(f)), cutoff)

    def match(self, lines: Iterable[str]) -> tuple[Mechanic, float] | None:
        """Best-matching mechanic across the OCR lines, with its similarity score."""
        best: tuple[Mechanic, float] | None = None
        matcher = SequenceMatcher(autojunk=False)
        for line in lines:
            key = normalize(line)
            if not key:
                continue
            if key in self._by_key:
                return self._by_key[key], 1.0
            matcher.set_seq2(key)
            for candidate, mechanic in self._by_key.items():
                matcher.set_seq1(candidate)
                if matcher.real_quick_ratio() < self.cutoff or matcher.quick_ratio() < self.cutoff:
                    continue
                score = matcher.ratio()
                if score >= self.cutoff and (best is None or score > best[1]):
                    best = (mechanic, score)
        return best
