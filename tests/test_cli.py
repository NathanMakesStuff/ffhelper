import shutil
import sys
from pathlib import Path

from ffhelper.cli import create_config, default_config_path, main
from ffhelper.config import load_config


def test_first_run_creates_settings_and_callouts(tmp_path, project_root):
    path = tmp_path / "FFHelper" / "config.toml"
    create_config(path, defaults=project_root)
    assert load_config(path).coach.job == "White Mage"
    assert (tmp_path / "FFHelper" / "mechanics" / "fru.json").exists()


def test_installed_app_keeps_settings_in_appdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_config_path() == tmp_path / "FFHelper" / "config.toml"


def test_source_checkout_uses_working_folder(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert default_config_path() == Path("config.toml")


def test_run_refuses_until_calibrated(tmp_path, project_root, caplog):
    config = tmp_path / "config.toml"
    shutil.copy(project_root / "config.example.toml", config)
    assert main(["run", "--config", str(config)]) == 2
    assert "ffhelper calibrate" in caplog.text


def test_run_with_everything_disabled_explains_why(tmp_path, caplog):
    config = tmp_path / "config.toml"
    config.write_text("[radar]\nenabled = false\n[coach]\nenabled = false\n")
    assert main(["run", "-c", str(config)]) == 2
    assert "Nothing to do" in caplog.text


def test_run_fails_when_everything_stops(tmp_path, caplog):
    config = tmp_path / "config.toml"
    config.write_text(
        "[regions]\nhotbars = [0, 0, 9, 9]\nbuffs = [0, 0, 9, 9]\njob_gauge = [0, 0, 9, 9]\n"
        '[radar]\nenabled = false\n[coach]\nhost = "http://127.0.0.1:9"\n'
    )
    assert main(["run", "-c", str(config)]) == 1
    assert "can't reach Ollama" in caplog.text
    assert "Everything has stopped" in caplog.text
