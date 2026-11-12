import threading
from pathlib import Path

import pytest

from ffhelper.config import CoachConfig, Config, RadarConfig, Region, VoiceConfig
from ffhelper.mechanics import Mechanic, MechanicsBook
from ffhelper.radar import Radar, run_radar

BOOK = MechanicsBook([Mechanic("Akh Morn", "Stack"), Mechanic("Exaflare", "Move")])


def feed(radar, reads):
    for now, lines in reads:
        radar.observe(lines, now)


def test_one_callout_per_cast_despite_flicker_and_typos(voice):
    radar = Radar(BOOK, voice, rearm_after=0.5)
    feed(radar, [(0.0, ["Akh Morn"]), (0.1, ["Akh Morn"]), (0.2, []), (0.3, ["Akh Mom"]), (0.4, ["Akh Morn"])])
    assert voice.said == [("Stack", True)]


def test_same_cast_is_called_again_after_the_bar_clears(voice):
    radar = Radar(BOOK, voice, rearm_after=0.5)
    feed(radar, [(0.0, ["Akh Morn"]), (0.1, []), (0.7, []), (0.8, ["Akh Morn"])])
    assert voice.said == [("Stack", True), ("Stack", True)]


def test_new_cast_is_called_immediately(voice):
    radar = Radar(BOOK, voice, rearm_after=0.5)
    feed(radar, [(0.0, ["Akh Morn"]), (0.1, ["Exaflare"])])
    assert [text for text, _ in voice.said] == ["Stack", "Move"]


def test_unknown_casts_are_ignored(voice):
    radar = Radar(BOOK, voice, rearm_after=0.5)
    feed(radar, [(0.0, ["Auto-attack"]), (0.1, ["Nidhogg"])])
    assert voice.said == []


def test_run_loop_reads_until_stopped(monkeypatch, voice):
    stop = threading.Event()
    reads = iter([["Akh Morn"], ["Akh Morn"], [], ["Exaflare"]])

    class FakeGrabber:
        def __init__(self, config, names):
            assert names == ["castbar"]

        def grab(self, name):
            return None

        def close(self):
            pass

    class FakeReader:
        def read(self, image):
            line = next(reads, None)
            if line is None:
                stop.set()
                return []
            return line

    monkeypatch.setattr("ffhelper.capture.Grabber", FakeGrabber)
    monkeypatch.setattr("ffhelper.ocr.TextReader", FakeReader)
    config = Config(
        path=Path("config.toml"),
        monitor=1,
        regions={"castbar": Region(10, 10, 300, 40)},
        radar=RadarConfig(reads_per_second=200),
        coach=CoachConfig(),
        voice=VoiceConfig(),
    )
    run_radar(config, BOOK, voice, stop)
    assert voice.said == [("Stack", True), ("Move", True)]


@pytest.mark.parametrize("rearm_after", [0.0, 0.5])
def test_rearm_window_is_respected(voice, rearm_after):
    radar = Radar(BOOK, voice, rearm_after=rearm_after)
    feed(radar, [(0.0, ["Akh Morn"]), (0.2, []), (0.3, ["Akh Morn"])])
    assert len(voice.said) == (2 if rearm_after == 0.0 else 1)
