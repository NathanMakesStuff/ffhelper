"""Runs the real OCR models on synthetic cast bars."""

import time

import cv2
import numpy as np
import pytest

from ffhelper.mechanics import Mechanic, MechanicsBook
from ffhelper.ocr import TextReader

BOOK = MechanicsBook([Mechanic("Akh Morn", "Stack"), Mechanic("Exaflare", "Move")])


def cast_bar(text: str) -> np.ndarray:
    """Outlined white text over a noisy background, with an orange progress bar underneath."""
    image = np.random.default_rng(0).integers(40, 160, (60, 420, 3), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (7, 7), 0)
    for color, thickness in (((0, 0, 0), 4), ((245, 245, 245), 1)):
        cv2.putText(image, text, (10, 26), cv2.FONT_HERSHEY_DUPLEX, 0.6, color, thickness, cv2.LINE_AA)
    cv2.rectangle(image, (8, 38), (412, 48), (30, 140, 230), -1)
    return image


@pytest.fixture(scope="module")
def reader() -> TextReader:
    return TextReader()


@pytest.mark.parametrize("cast", ["Akh Morn", "Exaflare"])
def test_cast_name_is_read_and_matched(reader, cast):
    assert BOOK.match(reader.read(cast_bar(cast)))[0].cast == cast


def test_empty_cast_bar_matches_nothing(reader):
    assert BOOK.match(reader.read(cast_bar(""))) is None


def test_read_is_fast_enough_for_ten_reads_a_second(reader):
    image = cast_bar("Akh Morn")
    started = time.perf_counter()
    for _ in range(10):
        reader.read(image)
    assert (time.perf_counter() - started) / 10 < 0.08
