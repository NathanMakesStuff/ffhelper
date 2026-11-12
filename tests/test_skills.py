import numpy as np

from ffhelper.skills import READY_FOR, SkillWatch, compare, reference_path, save_reference

READY = np.random.default_rng(0).integers(60, 230, (40, 40, 3), dtype=np.uint8)


def dimmed(icon, columns=slice(None)):
    out = icon.copy()
    out[:, columns] = out[:, columns] // 2
    return out


def is_ready(icon):
    watch = SkillWatch({"icon": READY})
    watch.update({"icon": icon}, 0.0)
    return watch.update({"icon": icon}, READY_FOR) == ["icon"]


def test_matching_icon_is_ready():
    assert is_ready(READY)


def test_cooldown_overlay_and_recast_sweep_are_not_ready():
    assert not is_ready(dimmed(READY))
    assert not is_ready(dimmed(READY, slice(10, 22)))  # sweep still covering part of the icon


def test_glow_on_the_edges_is_ignored():
    glowing = READY.copy()
    glowing[:4], glowing[-4:], glowing[:, :4], glowing[:, -4:] = 255, 255, 255, 255
    assert is_ready(glowing)


def test_icon_captured_at_a_different_size_is_scaled_to_match():
    double = np.repeat(np.repeat(READY, 2, axis=0), 2, axis=1)
    assert compare(double, READY) == (1.0, 0.0)


def test_nags_only_once_the_icon_has_stayed_ready():
    watch = SkillWatch({"Assize": READY})
    assert watch.update({"Assize": READY}, 0.0) == []
    assert watch.update({"Assize": READY}, READY_FOR) == ["Assize"]
    assert watch.update({"Assize": dimmed(READY)}, READY_FOR + 1) == []
    assert watch.update({"Assize": READY}, READY_FOR + 2) == []  # used again, so the wait restarts


def test_ready_pictures_are_saved_and_loaded(tmp_path, caplog):
    config_path = tmp_path / "config.toml"
    save_reference(config_path, "Presence of Mind", READY)
    watch = SkillWatch.load(config_path, ["Presence of Mind", "Assize"])
    assert list(watch.references) == ["Presence of Mind"]
    assert np.array_equal(watch.references["Presence of Mind"], READY)
    assert "No picture of Assize" in caplog.text
    assert reference_path(config_path, 'Odd: "name"').name == "Odd_ _name_.png"
