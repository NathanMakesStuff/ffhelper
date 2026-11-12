"""Typed settings loaded from config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """A problem the user can fix by editing config.toml or re-running calibrate."""


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    w: int
    h: int

    @property
    def is_set(self) -> bool:
        return self.w > 0 and self.h > 0


@dataclass(frozen=True)
class RadarConfig:
    enabled: bool = True
    region: str = "castbar"
    mechanics: Path = Path("mechanics")
    reads_per_second: float = 10.0
    match_cutoff: float = 0.75
    rearm_after: float = 0.5


@dataclass(frozen=True)
class CoachConfig:
    enabled: bool = True
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5vl:7b"
    interval: float = 3.0
    regions: tuple[str, ...] = ("hotbars", "buffs", "job_gauge")
    job: str = ""
    notes: str = ""
    repeat_after: float = 15.0


@dataclass(frozen=True)
class VoiceConfig:
    rate: int = 2


@dataclass(frozen=True)
class Config:
    path: Path
    monitor: int
    regions: dict[str, Region]
    radar: RadarConfig
    coach: CoachConfig
    voice: VoiceConfig

    def region(self, name: str) -> Region:
        region = self.regions.get(name)
        if region is None or not region.is_set:
            raise ConfigError(
                f"Screen region '{name}' is not set in {self.path.name}. Run: ffhelper calibrate"
            )
        return region


def _section(cls: type, data: dict[str, Any], name: str) -> Any:
    values = data.get(name, {})
    unknown = set(values) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f"Unknown setting(s) in [{name}]: {', '.join(sorted(unknown))}")
    return cls(**values)


def _regions(raw: dict[str, Any]) -> dict[str, Region]:
    regions = {}
    for name, value in raw.items():
        if not (
            isinstance(value, list)
            and len(value) == 4
            and all(isinstance(v, int) and v >= 0 for v in value)
        ):
            raise ConfigError(f"[regions] {name} must be [x, y, width, height] using whole numbers")
        regions[name] = Region(*value)
    return regions


def load_config(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path.name} is not valid TOML: {e}") from None

    radar = _section(RadarConfig, data, "radar")
    coach = _section(CoachConfig, data, "coach")
    return Config(
        path=path,
        monitor=int(data.get("capture", {}).get("monitor", 1)),
        regions=_regions(data.get("regions", {})),
        radar=replace(radar, mechanics=path.parent / radar.mechanics),
        coach=replace(coach, regions=tuple(coach.regions)),
        voice=_section(VoiceConfig, data, "voice"),
    )
