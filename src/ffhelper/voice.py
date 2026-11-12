"""Spoken callouts. Urgent callouts cut off whatever is playing; tips wait their turn."""

from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable
from typing import Protocol
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)


class Speaker(Protocol):
    def start(self, text: str, shout: bool = False) -> None: ...
    def busy(self) -> bool: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


class SapiSpeaker:
    """Windows built-in speech (SAPI) over COM."""

    _ASYNC, _PURGE, _XML, _NOT_XML = 1, 2, 8, 16
    _SPEAKING = 2
    # SAPI can't really yell; higher and faster is as close as it gets.
    _SHOUT = '<pitch middle="5"><rate speed="2">{}</rate></pitch>'

    def __init__(self, rate: int):
        import pythoncom
        import win32com.client

        self._pythoncom = pythoncom
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        self._voice.Rate = max(-10, min(10, rate))

    def start(self, text: str, shout: bool = False) -> None:
        if shout:
            self._voice.Speak(self._SHOUT.format(escape(text)), self._ASYNC | self._XML)
        else:
            self._voice.Speak(text, self._ASYNC | self._NOT_XML)

    def busy(self) -> bool:
        return self._voice.Status.RunningState == self._SPEAKING

    def stop(self) -> None:
        self._voice.Speak("", self._ASYNC | self._PURGE)

    def close(self) -> None:
        self._voice.WaitUntilDone(3000)
        self._voice = None
        self._pythoncom.CoUninitialize()


class SaySpeaker:
    """macOS `say`, for trying things out away from the gaming PC."""

    def __init__(self, rate: int):
        self._words_per_minute = 175 + 15 * rate
        self._proc: subprocess.Popen[bytes] | None = None

    def start(self, text: str, shout: bool = False) -> None:
        words_per_minute = self._words_per_minute + (40 if shout else 0)
        self._proc = subprocess.Popen(["say", "-r", str(words_per_minute), "--", text])

    def busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        if self._proc is not None and self.busy():
            self._proc.terminate()

    def close(self) -> None:
        if self._proc is not None and self.busy():
            self._proc.wait(timeout=5)


class SilentSpeaker:
    def start(self, text: str, shout: bool = False) -> None:
        pass

    def busy(self) -> bool:
        return False

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


def default_speaker(rate: int) -> Speaker:
    if sys.platform == "win32":
        return SapiSpeaker(rate)
    if sys.platform == "darwin" and shutil.which("say"):
        return SaySpeaker(rate)
    log.warning("No text-to-speech on this platform; callouts will only be printed.")
    return SilentSpeaker()


class Voice:
    """Runs the speaker on its own thread so the capture loops never block on audio."""

    def __init__(self, rate: int = 0, speaker_factory: Callable[[int], Speaker] = default_speaker):
        self._queue: queue.Queue[tuple[str, bool, bool] | None] = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, args=(speaker_factory, rate), name="voice", daemon=True
        )
        self._thread.start()

    def say(self, text: str, urgent: bool = False, shout: bool = False) -> None:
        if text:
            self._queue.put((text, urgent, shout))

    def close(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=10)

    def _run(self, speaker_factory: Callable[[int], Speaker], rate: int) -> None:
        try:
            speaker = speaker_factory(rate)
        except Exception:
            log.exception("Text-to-speech failed to start; callouts will only be printed.")
            speaker = SilentSpeaker()
        pending: deque[tuple[str, bool]] = deque()
        while True:
            try:
                item = self._queue.get(timeout=0.05 if pending else None)
            except queue.Empty:
                item = ("", False, False)  # nothing new; just check whether a pending tip can start
            if item is None:
                break
            text, urgent, shout = item
            try:
                if urgent:
                    pending.clear()
                    speaker.stop()
                    speaker.start(text, shout)
                    continue
                if text:
                    pending.append((text, shout))
                if pending and not speaker.busy():
                    speaker.start(*pending.popleft())
            except Exception:
                log.exception("Text-to-speech error")
        speaker.close()
