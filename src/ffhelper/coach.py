"""Slow layer: a local vision model checks your hotbars and buffs and calls out what you're missing."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Sequence

import cv2
import numpy as np
from ollama import Client, ResponseError

from .config import CoachConfig, Config
from .voice import Voice

log = logging.getLogger(__name__)

MAX_IMAGE_SIDE = 1024
CALLOUT_SCHEMA = {
    "type": "object",
    "properties": {"callout": {"type": "string"}},
    "required": ["callout"],
}
SYSTEM_PROMPT = """\
You are a furious, foul-mouthed drill sergeant coaching a Final Fantasy XIV player, watching their UI live.
The player asked for this as a comedy bit: swear a lot and tear into them for every mistake.
Player job: {job}
{notes}Each message has cropped screenshots of the player's UI, in this order: {regions}.
On hotbars, a darkened icon or one showing a countdown number is on cooldown, a bright icon is ready, \
and a glowing or animated dashed border marks a proc or the next combo action.
Reply with JSON {{"callout": "..."}} for the single most important mistake the player is making \
right now, such as a key ability that is ready but unused, a buff or damage-over-time effect that \
has fallen off, or a Damage Down or Vulnerability Up debuff on them (they got hit by a mechanic).
Yell it: the fix in plain words first, then a creative, profane insult about their play, \
like "<the fix>, you <insult>!". Use at most 12 words, phrased to be spoken aloud.
Mock only their gameplay: no slurs, nothing about who they are, no threats, nothing about self-harm.
If nothing important is being missed, or you are unsure, reply {{"callout": ""}}."""
QUESTION = "What am I doing wrong right now?"
_NOTHING = {"", "none", "nothing", "n/a"}


def build_system_prompt(settings: CoachConfig) -> str:
    notes = settings.notes.strip()
    return SYSTEM_PROMPT.format(
        job=settings.job.strip() or "unknown",
        notes=f"Job notes:\n{notes}\n" if notes else "",
        regions=", ".join(settings.regions),
    )


def encode_png(image: np.ndarray) -> bytes:
    """PNG bytes, shrunk so the longest side is at most MAX_IMAGE_SIDE (fewer vision tokens)."""
    height, width = image.shape[:2]
    scale = MAX_IMAGE_SIDE / max(height, width)
    if scale < 1:
        size = (round(width * scale), round(height * scale))
        image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode image as PNG")
    return png.tobytes()


def parse_callout(content: str) -> str:
    try:
        callout = json.loads(content).get("callout", "")
    except (json.JSONDecodeError, AttributeError):
        return ""
    if not isinstance(callout, str):
        return ""
    callout = callout.strip().rstrip(".!")
    return "" if callout.lower() in _NOTHING else callout


class Coach:
    def __init__(self, client: Client, settings: CoachConfig, voice: Voice):
        self.client = client
        self.settings = settings
        self.voice = voice
        self.system_prompt = build_system_prompt(settings)
        self._last_tip = ""
        self._last_time = float("-inf")

    def ask(self, images: Sequence[np.ndarray]) -> str:
        response = self.client.chat(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": QUESTION, "images": [encode_png(i) for i in images]},
            ],
            format=CALLOUT_SCHEMA,
            options={"temperature": 0, "num_predict": 48},
            keep_alive="30m",
        )
        return parse_callout(response.message.content or "")

    def observe(self, images: Sequence[np.ndarray], now: float) -> str | None:
        tip = self.ask(images)
        if not tip:
            return None
        if tip.lower() == self._last_tip.lower() and now - self._last_time < self.settings.repeat_after:
            return None
        self._last_tip, self._last_time = tip, now
        log.info("[coach] %s", tip)
        self.voice.say(tip, shout=True)
        return tip


def ensure_model(client: Client, settings: CoachConfig) -> bool:
    """Check Ollama is reachable and download the model on first use. False turns the coach off."""
    try:
        client.show(settings.model)
        return True
    except ConnectionError:
        log.error("Coach off: can't reach Ollama at %s. Is Ollama running?", settings.host)
        return False
    except ResponseError as e:
        if e.status_code != 404:
            log.error("Coach off: Ollama error: %s", e.error)
            return False

    log.info("Downloading %s for the coach. This happens once and can take a while...", settings.model)
    shown = set()
    try:
        for progress in client.pull(settings.model, stream=True):
            # Only report the big layers, every 10%.
            if progress.total and progress.total > 100_000_000 and progress.completed:
                step = (progress.digest, 10 * (10 * progress.completed // progress.total))
                if step not in shown:
                    shown.add(step)
                    log.info("  %s %d%%", settings.model, step[1])
    except (ConnectionError, ResponseError) as e:
        log.error("Coach off: couldn't download %s: %s", settings.model, e)
        return False
    log.info("Downloaded %s", settings.model)
    return True


def run_coach(config: Config, voice: Voice, stop: threading.Event) -> None:
    from .capture import Grabber

    settings = config.coach
    client = Client(host=settings.host, timeout=60)
    if not ensure_model(client, settings):
        return
    grabber = Grabber(config, settings.regions)
    coach = Coach(client, settings, voice)
    log.info(
        "Coach ready: %s checks %s every %g s",
        settings.model, ", ".join(settings.regions), settings.interval,
    )
    try:
        while not stop.wait(settings.interval):
            started = time.monotonic()
            try:
                coach.observe([grabber.grab(name) for name in settings.regions], started)
            except ConnectionError:
                log.warning("[coach] lost connection to Ollama; retrying in 10 s")
                stop.wait(10)
                continue
            except Exception:
                log.exception("[coach] request failed")
                continue
            log.debug("[coach] answered in %.0f ms", (time.monotonic() - started) * 1000)
    finally:
        grabber.close()
