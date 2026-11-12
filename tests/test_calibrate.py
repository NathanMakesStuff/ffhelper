import shutil

from ffhelper.calibrate import save_regions, to_region
from ffhelper.config import Region, load_config


def test_box_drawn_in_any_direction_maps_to_capture_coordinates():
    # Retina: 2 image pixels per point, preview shown at 25% of the image.
    assert to_region((190, 100, 10, 10), scale=2 * 0.25) == [20, 20, 360, 180]


def test_save_updates_regions_and_keeps_comments(tmp_path, project_root):
    path = tmp_path / "config.toml"
    shutil.copy(project_root / "config.example.toml", path)
    save_regions(path, {"castbar": [1, 2, 300, 40]})
    config = load_config(path)
    assert config.regions["castbar"] == Region(1, 2, 300, 40)
    assert config.regions["hotbars"] == Region(0, 0, 0, 0)
    assert "# Plain-English priorities" in path.read_text()


def test_save_adds_missing_regions_table(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[voice]\nrate = 0\n")
    save_regions(path, {"castbar": [5, 6, 7, 8]})
    assert load_config(path).regions == {"castbar": Region(5, 6, 7, 8)}
