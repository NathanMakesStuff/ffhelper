import time
from types import SimpleNamespace

from ffhelper.voice import SapiSpeaker, Voice


class FakeSpeaker:
    def __init__(self):
        self.log = []
        self.speaking = False
        self.closed = False

    def start(self, text, shout=False):
        self.log.append(("shout" if shout else "start", text))
        self.speaking = True

    def busy(self):
        return self.speaking

    def stop(self):
        self.log.append(("stop",))
        self.speaking = False

    def close(self):
        self.closed = True


def wait_for(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_tips_queue_and_urgent_callouts_cut_in():
    speaker = FakeSpeaker()
    voice = Voice(speaker_factory=lambda rate: speaker)
    voice.say("tip one")
    voice.say("tip two")
    assert wait_for(lambda: ("start", "tip one") in speaker.log)
    time.sleep(0.15)
    assert ("start", "tip two") not in speaker.log  # still speaking tip one

    voice.say("Stack", urgent=True)
    assert wait_for(lambda: ("start", "Stack") in speaker.log)
    speaker.speaking = False
    time.sleep(0.15)
    voice.close()

    # The urgent callout interrupted tip one and dropped the stale tip two.
    assert speaker.log == [("start", "tip one"), ("stop",), ("start", "Stack")]
    assert speaker.closed


def test_pending_tip_plays_when_speaker_frees_up():
    speaker = FakeSpeaker()
    voice = Voice(speaker_factory=lambda rate: speaker)
    voice.say("tip one")
    voice.say("tip two")
    assert wait_for(lambda: ("start", "tip one") in speaker.log)
    speaker.speaking = False
    assert wait_for(lambda: ("start", "tip two") in speaker.log)
    voice.close()


def test_shouted_tips_reach_the_speaker_as_shouts():
    speaker = FakeSpeaker()
    voice = Voice(speaker_factory=lambda rate: speaker)
    voice.say("Press Assize, you walnut", shout=True)
    assert wait_for(lambda: ("shout", "Press Assize, you walnut") in speaker.log)
    voice.close()


def test_sapi_shouts_with_escaped_xml():
    spoken = []
    speaker = SapiSpeaker.__new__(SapiSpeaker)  # skips the Windows-only COM setup
    speaker._voice = SimpleNamespace(Speak=lambda text, flags: spoken.append((text, flags)))
    speaker.start("Stack")
    speaker.start("Press Assize, you <slow> & sorry walnut", shout=True)
    assert spoken == [
        ("Stack", 1 | 16),
        ('<pitch middle="5"><rate speed="2">Press Assize, you &lt;slow&gt; &amp; sorry walnut</rate></pitch>', 1 | 8),
    ]


def test_broken_speech_engine_falls_back_to_silence(caplog):
    def broken(rate):
        raise OSError("no audio device")

    voice = Voice(speaker_factory=broken)
    voice.say("Stack", urgent=True)
    voice.close()
    assert "failed to start" in caplog.text
