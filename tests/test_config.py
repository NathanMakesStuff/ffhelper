import pytest

from ffhelper.config import ConfigError, Region, load_config


def test_example_config_loads(project_root):
    config = load_config(project_root / "config.example.toml")
    assert config.monitor == 1
    assert set(config.regions) == {"castbar", "hotbars", "buffs", "job_gauge"}
    assert config.radar.mechanics == project_root / "mechanics"
    assert config.coach.regions == ("hotbars", "buffs", "job_gauge")
    assert config.coach.job == "White Mage"


def test_uncalibrated_region_says_how_to_fix(project_root):
    config = load_config(project_root / "config.example.toml")
    with pytest.raises(ConfigError, match="ffhelper calibrate"):
        config.region("castbar")


def test_calibrated_region(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[regions]\ncastbar = [1, 2, 300, 40]\n")
    assert load_config(path).region("castbar") == Region(1, 2, 300, 40)


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ("[radar]\nspeed = 3\n", "speed"),
        ("[regions]\ncastbar = [1, 2, 3]\n", "castbar"),
        ("[regions\n", "not valid TOML"),
    ],
)
def test_bad_config_is_reported(tmp_path, toml, message):
    path = tmp_path / "config.toml"
    path.write_text(toml)
    with pytest.raises(ConfigError, match=message):
        load_config(path)
