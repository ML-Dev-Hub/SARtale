"""The DEM layover and shadow mask of the window statistics (sartale.demmask)."""
import numpy as np
import pytest

from sartale import demmask
from sartale.demmask import cast_shadow, grid_key, layover_shadow, local_incidence, stat_masks

PX = 10.0


def test_a_flat_dem_is_seen_at_the_nominal_incidence_and_has_no_layover_or_shadow():
    dem = np.full((50, 50), 3000.0)
    assert np.allclose(local_incidence(dem, PX, 255.0, 40.0), 40.0)
    assert not layover_shadow(dem, PX, 10, 255.0, 40.0).any()


def test_a_slope_facing_the_radar_steeper_than_the_incidence_is_layover():
    # looking west (azimuth 270): the radar is to the east, so a slope rising to the west faces it
    cols = np.arange(60)[None, :] * np.ones((60, 1))
    steep = 3000.0 - cols * PX * np.tan(np.radians(60))  # rises westward at 60 degrees, steeper than 40
    li = local_incidence(steep, PX, 270.0, 40.0)
    assert np.allclose(li[5:-5, 5:-5], 40.0 - 60.0)
    assert layover_shadow(steep, PX, 5, 270.0, 40.0).all()
    gentle = 3000.0 - cols * PX * np.tan(np.radians(20))  # 20 degrees: seen, at a smaller angle
    assert np.allclose(local_incidence(gentle, PX, 270.0, 40.0)[5:-5, 5:-5], 20.0)
    assert not layover_shadow(gentle, PX, 5, 270.0, 40.0).any()


def test_terrain_between_a_pixel_and_the_radar_casts_shadow_behind_it():
    dem = np.zeros((40, 80))
    dem[:, 40] = 200.0  # a 200 m wall; looking west the radar is east of it, so it shadows the ground west of it
    sh = cast_shadow(dem, PX, 270.0, 40.0, max_m=500.0)
    # behind the wall the ray at 40 degrees from the vertical clears 200 m after 200 x tan(40) = 168 m
    assert sh[:, 25:40].all() and not sh[:, :20].any() and not sh[:, 41:].any()
    # looking east the radar is west of the wall: the shadow falls on the other side
    sh_e = cast_shadow(dem, PX, 90.0, 40.0, max_m=500.0)
    assert sh_e[:, 41:56].all() and not sh_e[:, :40].any()


def test_stat_masks_read_a_kept_dem_and_keep_the_masks_with_it(tmp_path, monkeypatch):
    monkeypatch.setenv(demmask.OFFLINE_ENV, "1")
    xs = 500000.0 + PX * np.arange(30)
    ys = 4000000.0 - PX * np.arange(20)
    assert stat_masks(tmp_path, xs, ys, 32643, {"A", "D"}) is None  # offline and nothing kept: no mask
    margin = int(round(3000.0 / PX))
    dem = np.zeros((20 + 2 * margin, 30 + 2 * margin), np.float32)
    path = tmp_path / "dem" / f"glo30_{grid_key(xs, ys, 32643)}.npz"
    path.parent.mkdir()
    np.savez_compressed(path, dem=dem)
    masks = stat_masks(tmp_path, xs, ys, 32643, {"A", "D"})
    assert set(masks) == {"A", "D"} and masks["A"].shape == (20, 30) and not masks["A"].any()
    with np.load(path) as z:
        assert {"dem", "mask_A_255_40_300", "mask_D_105_40_300"} <= set(z.files)


def test_stat_masks_never_raise_when_the_dem_cannot_be_read(tmp_path, monkeypatch):
    monkeypatch.delenv(demmask.OFFLINE_ENV, raising=False)

    def broken(*a, **k):
        raise ConnectionError("no network")
    monkeypatch.setattr(demmask, "read_dem", broken)
    said = []
    xs = 500000.0 + PX * np.arange(30)
    ys = 4000000.0 - PX * np.arange(20)
    assert stat_masks(tmp_path, xs, ys, 32643, {"A"}, log=said.append) is None
    assert "Copernicus DEM not read" in said[0]


def test_the_grid_key_changes_with_the_grid():
    xs = 500000.0 + PX * np.arange(30)
    ys = 4000000.0 - PX * np.arange(20)
    assert grid_key(xs, ys, 32643) == grid_key(xs.copy(), ys.copy(), 32643)
    assert grid_key(xs + PX, ys, 32643) != grid_key(xs, ys, 32643)
    assert grid_key(xs, ys, 32642) != grid_key(xs, ys, 32643)


@pytest.mark.parametrize("direction,az", [("A", 255.0), ("D", 105.0)])
def test_the_look_azimuths_are_the_fitted_ones(direction, az):
    from sartale import config
    assert config.DEM_LOOK_AZIMUTH_DEG[direction] == az and config.DEM_INCIDENCE_DEG == 40.0
