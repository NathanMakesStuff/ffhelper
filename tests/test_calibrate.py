import shutil

import numpy as np

from ffhelper.calibrate import crop, save_regions, to_region
from ffhelper.config import Region, load_config


def test_box_drawn_in_any_direction_maps_to_capture_coordinates():
    # Retina: 2 image pixels per point, preview shown at 25% of the image.
    assert to_region((190, 100, 10, 10), scale=2 * 0.25) == [20, 20, 360, 180]


def test_crop_uses_screenshot_pixels():
    image = np.arange(40 * 60 * 3, dtype=np.uint32).reshape(40, 60, 3)
    assert np.array_equal(crop(image, [10, 5, 4, 3], pixel_scale=2), image[10:16, 20:28])


def test_save_updates_regions_and_keeps_comments(tmp_path, project_root):
    path = tmp_path / "config.toml"
    shutil.copy(project_root / "config.example.toml", path)
    save_regions(path, {"castbar": [1, 2, 300, 40], "Presence of Mind": [5, 5, 40, 40]})
    config = load_config(path)
    assert config.regions["castbar"] == Region(1, 2, 300, 40)
    assert config.regions["Presence of Mind"] == Region(5, 5, 40, 40)
    assert config.regions["buffs"] == Region(0, 0, 0, 0)
    assert "# Plain-English priorities" in path.read_text()


def test_save_adds_missing_regions_table(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[voice]\nrate = 0\n")
    save_regions(path, {"castbar": [5, 6, 7, 8]})
    assert load_config(path).regions == {"castbar": Region(5, 6, 7, 8)}
