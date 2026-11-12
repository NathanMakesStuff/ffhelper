import json

import pytest

from ffhelper.config import ConfigError
from ffhelper.mechanics import Mechanic, MechanicsBook, normalize

BOOK = MechanicsBook(
    [
        Mechanic("Akh Morn", "Stack and mitigate"),
        Mechanic("One-two Paw", "Left then right"),
        Mechanic("Two-one Paw", "Right then left"),
    ]
)


def test_normalize_ignores_case_spacing_and_punctuation():
    assert normalize("  One-Two  Paw! ") == "onetwopaw"


def test_ocr_spacing_still_counts_as_exact():
    mechanic, score = BOOK.match(["AkhMorn"])
    assert (mechanic.cast, score) == ("Akh Morn", 1.0)


def test_ocr_typos_match_fuzzily():
    mechanic, score = BOOK.match(["Akh Mom"])  # "rn" misread as "m"
    assert mechanic.cast == "Akh Morn"
    assert score < 1.0


def test_mirrored_names_are_not_confused():
    assert BOOK.match(["Two-one Paw"])[0].say == "Right then left"
    assert BOOK.match(["Tw0-one Paw"])[0].say == "Right then left"
    assert BOOK.match(["One-tw0 Paw"])[0].say == "Left then right"


def test_unrelated_text_is_ignored():
    assert BOOK.match(["Nidhogg", "", "Akh"]) is None


def test_any_line_can_match():
    assert BOOK.match(["Nidhogg", "Akh Morn"])[0].cast == "Akh Morn"


def test_load_folder_with_shorthand_entries(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"mechanics": {"Akh Morn": {"say": "Stack", "note": "Feint"}}}))
    (tmp_path / "b.json").write_text(json.dumps({"mechanics": {"Exaflare": "Move"}}))
    book = MechanicsBook.load(tmp_path)
    assert len(book) == 2
    assert book.match(["Akh Morn"])[0] == Mechanic("Akh Morn", "Stack", "Feint")
    assert book.match(["Exaflare"])[0].say == "Move"


def test_entry_without_say_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"mechanics": {"Akh Morn": {"note": "no say"}}}))
    with pytest.raises(ConfigError, match='"say"'):
        MechanicsBook.load(path)


def test_missing_path_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        MechanicsBook.load(tmp_path / "nope.json")


def test_bundled_fru_callouts_load(project_root):
    path = project_root / "mechanics" / "fru.json"
    casts = json.loads(path.read_text(encoding="utf-8"))["mechanics"]
    book = MechanicsBook.load(project_root / "mechanics")
    assert len(book) == len(casts)  # no two casts collapse to the same key
    for cast in casts:
        assert book.match([cast])[0].cast == cast
    assert book.match(["Spell-in-Waiting Refrain"])[0].cast == "Spell-in-Waiting: Refrain"
