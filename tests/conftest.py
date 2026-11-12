from pathlib import Path

import pytest


class FakeVoice:
    def __init__(self):
        self.said: list[tuple[str, bool]] = []
        self.shouted: list[str] = []

    def say(self, text: str, urgent: bool = False, shout: bool = False) -> None:
        self.said.append((text, urgent))
        if shout:
            self.shouted.append(text)


@pytest.fixture
def voice() -> FakeVoice:
    return FakeVoice()


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch):
    """Never launch a real Ollama from tests; build.ps1 runs them on the PC that has it installed."""
    monkeypatch.setattr("ffhelper.coach.find_ollama", lambda: None)


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
