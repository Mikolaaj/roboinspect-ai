import numpy as np
import pytest
from PIL import Image

from roboinspect.mapping import grid_image, write_aligned_map


def test_grid_preserves_unknown_and_flips_ros_rows():
    result = np.array(grid_image([-1, 0, 100, 100, 0, -1], 3, 2))
    assert result.tolist() == [[0, 254, 205], [205, 254, 0]]


def test_alignment_translates_origin_without_changing_observations(tmp_path):
    info = write_aligned_map(tmp_path / "map", [-1, 0, 100, 0], 2, 2, 0.05, (-2.0, -3.0, 0.0))
    assert info["origin"] == [-13.0, -10.0, 0.0]
    assert info["image"] == "map.pgm"
    assert np.array(Image.open(tmp_path / "map.pgm")).tolist() == [[0, 254], [205, 254]]


@pytest.mark.parametrize(
    "data,width,height", [([101], 1, 1), ([-2], 1, 1), ([], 0, 1), ([0], 2, 2)]
)
def test_invalid_grid_rejected(data, width, height):
    with pytest.raises(ValueError):
        grid_image(data, width, height)


def test_reference_slam_map_preserves_sector_goal_coordinates():
    import json
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    source = root / "maps/slam/hangar_slam.yaml"
    info = yaml.safe_load(source.read_text())
    grid = Image.open(source.parent / info["image"])
    goals = json.loads((root / "config/navigation-goals.json").read_text())["poses"]
    for name in ("A", "B", "C", "BASE"):
        x, y, _ = goals[name]
        ox, oy, _ = info["origin"]
        column = int((x - ox) / info["resolution"])
        row = grid.height - 1 - int((y - oy) / info["resolution"])
        assert grid.getpixel((column, row)) == 254, name


def test_exported_unknown_remains_unknown_when_loaded_by_map_server(tmp_path):
    info = write_aligned_map(
        tmp_path / "map", [-1, 0, 100, 19, 20, 64], 3, 2, 0.05, (0.0, 0.0, 0.0)
    )
    pixels = np.flipud(np.array(Image.open(tmp_path / "map.pgm"))).reshape(-1)
    states = []
    for pixel in pixels:
        probability = (255 - int(pixel)) / 255
        states.append(
            100
            if probability > info["occupied_thresh"]
            else 0
            if probability < info["free_thresh"]
            else -1
        )
    assert states == [-1, 0, 100, 0, -1, -1]
