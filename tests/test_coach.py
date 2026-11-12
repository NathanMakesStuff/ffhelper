import json
import logging
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from ollama import ResponseError

from ffhelper.coach import CALLOUT_SCHEMA, Coach, encode_png, ensure_model, parse_callout
from ffhelper.config import CoachConfig

SETTINGS = CoachConfig(
    job="Dragoon",
    notes="Use Life Surge right before Heavens' Thrust.",
    regions=("hotbars", "buffs"),
    repeat_after=10,
)


def reply(text):
    return json.dumps({"callout": text})


class FakeClient:
    def __init__(self, replies=(), show_error=None, pulls=(), pull_error=None, down_for=0):
        self.replies = list(replies)
        self.show_error = show_error
        self.pulls = pulls
        self.pull_error = pull_error
        self.down_for = down_for  # how many requests fail as if Ollama weren't running
        self.calls = []
        self.pulled = []

    def _check_up(self):
        if self.down_for:
            self.down_for -= 1
            raise ConnectionError("refused")

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))

    def show(self, model):
        self._check_up()
        if self.show_error:
            raise self.show_error

    def list(self):
        self._check_up()

    def pull(self, model, stream):
        self.pulled.append(model)
        if self.pull_error:
            raise self.pull_error
        return iter(self.pulls)


def test_parse_callout():
    assert parse_callout(reply("Use Life Surge.")) == "Use Life Surge"
    assert parse_callout(reply("  ")) == ""
    assert parse_callout(reply("None")) == ""
    assert parse_callout("not json") == ""
    assert parse_callout("[1, 2]") == ""
    assert parse_callout(json.dumps({"callout": 3})) == ""


def test_request_carries_job_notes_images_and_schema(voice):
    client = FakeClient([reply("Use Life Surge")])
    Coach(client, SETTINGS, voice).observe([np.zeros((40, 300, 3), np.uint8)] * 2, now=0)
    call = client.calls[0]
    system, user = call["messages"]
    assert "Dragoon" in system["content"]
    assert "Life Surge right before" in system["content"]
    assert "hotbars, buffs" in system["content"]
    assert "no slurs" in system["content"]
    assert '"callout": ""' not in system["content"]  # it must always say something mean
    assert len(user["images"]) == 2
    assert user["images"][0].startswith(b"\x89PNG")
    assert call["format"] == CALLOUT_SCHEMA
    assert call["model"] == SETTINGS.model


def test_tips_are_spoken_but_not_repeated_too_soon(voice):
    client = FakeClient([reply("Use Life Surge"), reply("use life surge"), reply(""), reply("Use Life Surge")])
    coach = Coach(client, SETTINGS, voice)
    for now in (0, 3, 6, 12):
        coach.observe([np.zeros((10, 10, 3), np.uint8)], now)
    assert voice.said == [("Use Life Surge", False), ("Use Life Surge", False)]
    assert voice.shouted == ["Use Life Surge", "Use Life Surge"]


def test_large_crops_are_downscaled():
    png = encode_png(np.zeros((500, 3000, 3), np.uint8))
    decoded = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (171, 1024)


def test_model_is_downloaded_on_first_use(caplog):
    caplog.set_level(logging.INFO)
    progress = [
        SimpleNamespace(digest="model", total=4_000_000_000, completed=done)
        for done in (0, 2_000_000_000, 4_000_000_000)
    ]
    client = FakeClient(show_error=ResponseError("not found", 404), pulls=progress)
    assert ensure_model(client, SETTINGS)
    assert client.pulled == ["qwen2.5vl:7b"]
    assert "50%" in caplog.text
    assert "Downloaded qwen2.5vl:7b" in caplog.text


def test_installed_model_is_not_downloaded_again():
    client = FakeClient()
    assert ensure_model(client, SETTINGS)
    assert client.pulled == []


def test_coach_turns_off_without_ollama_or_model(caplog):
    assert not ensure_model(FakeClient(down_for=99), SETTINGS)
    assert "Ollama isn't installed" in caplog.text
    assert not ensure_model(FakeClient(down_for=99), replace(SETTINGS, host="http://gaming-pc:11434"))
    assert "Is Ollama running?" in caplog.text
    failed_pull = FakeClient(show_error=ResponseError("not found", 404), pull_error=ResponseError("no space", 500))
    assert not ensure_model(failed_pull, SETTINGS)
    assert "couldn't download" in caplog.text


@pytest.mark.parametrize("exits", [False, True])
def test_installed_ollama_is_started_when_not_running(monkeypatch, caplog, exits):
    started = []

    class FakeServer:
        def __init__(self, args, env, **kwargs):
            started.append((args, env["OLLAMA_HOST"]))

        def poll(self):
            return 1 if exits else None

    monkeypatch.setattr("ffhelper.coach.find_ollama", lambda: "ollama")
    monkeypatch.setattr("ffhelper.coach.subprocess.Popen", FakeServer)
    client = FakeClient(down_for=2)  # the first check and the first wait both find it down
    assert ensure_model(client, SETTINGS) is not exits
    assert started == [(["ollama", "serve"], "127.0.0.1:11434")]
    assert ("isn't answering" in caplog.text) is exits
