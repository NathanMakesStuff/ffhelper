"""Fast layer: read the boss cast bar ~10 times a second and call out known mechanics."""

from __future__ import annotations

import logging
import threading
import time

from .config import Config
from .mechanics import Mechanic, MechanicsBook
from .voice import Voice

log = logging.getLogger(__name__)


class Radar:
    """Turns a stream of cast-bar reads into one spoken callout per cast."""

    def __init__(self, book: MechanicsBook, voice: Voice, rearm_after: float):
        self.book = book
        self.voice = voice
        self.rearm_after = rearm_after
        self._active: str | None = None
        self._last_seen = float("-inf")

    def observe(self, lines: list[str], now: float) -> Mechanic | None:
        hit = self.book.match(lines)
        if hit is None:
            # Re-arm only once the bar has been gone a while, so one bad read mid-cast can't repeat a callout.
            if now - self._last_seen >= self.rearm_after:
                self._active = None
            return None
        mechanic, score = hit
        log.debug("[radar] matched %s (%.2f)", mechanic.cast, score)
        self._last_seen = now
        if mechanic.cast == self._active:
            return None
        self._active = mechanic.cast
        log.info("[radar] %s -> %s", mechanic.cast, mechanic.say)
        self.voice.say(mechanic.say, urgent=True)
        return mechanic


def run_radar(config: Config, book: MechanicsBook, voice: Voice, stop: threading.Event) -> None:
    from .capture import Grabber
    from .ocr import TextReader

    settings = config.radar
    reader = TextReader()
    grabber = Grabber(config, [settings.region])
    radar = Radar(book, voice, settings.rearm_after)
    period = 1.0 / settings.reads_per_second
    log.info(
        "Radar ready: %d mechanics, reading '%s' %g times a second",
        len(book), settings.region, settings.reads_per_second,
    )
    try:
        while not stop.is_set():
            started = time.monotonic()
            try:
                lines = reader.read(grabber.grab(settings.region))
                radar.observe(lines, time.monotonic())
            except Exception:
                log.exception("[radar] read failed")
                stop.wait(1.0)
                continue
            elapsed = time.monotonic() - started
            if lines:
                log.debug("[radar] read %s in %.0f ms", lines, elapsed * 1000)
            stop.wait(max(0.0, period - elapsed))
    finally:
        grabber.close()
