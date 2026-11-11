import numpy as np
import pytest
from pyproj import Transformer

from sartale.lakes import Lake
from sartale.lakewater import dark_mask, lake_zone, pass_water, screen_passes, shadow_prone

EPSG = 32643
X = 500000.0 + 10.0 * np.arange(100)
Y = 3800000.0 - 10.0 * np.arange(100)  # north-up, descending
YY, XX = np.mgrid[0:100, 0:100]
LAKE = (YY - 50) ** 2 + (XX - 50) ** 2 <= 15 ** 2
STRIP = np.zeros((100, 100), bool)
STRIP[5:15, 10:90] = True


def scene():
    hh = np.full((100, 100), -7.0)
    hv = np.full((100, 100), -14.0)
    hh[LAKE], hv[LAKE] = -13.0, -20.0
    hh[STRIP], hv[STRIP] = -22.0, -28.0
    return hh, hv


def centre_lake():
    lon, lat = Transformer.from_crs(EPSG, 4326, always_xy=True).transform(X[50], Y[50])
    return Lake("t", "T", lon, lat, "test", None, "watch", None, None)


def test_dark_mask_finds_lake_not_land():
    hh, hv = scene()
    dark, valid = dark_mask(hh, hv)
    assert dark[LAKE].all() and dark[STRIP].all()
    assert not dark[~LAKE & ~STRIP].any() and valid.all()


def test_dark_mask_nan_is_invalid_not_dark():
    hh, hv = scene()
    hh[50, 50] = np.nan
    dark, valid = dark_mask(hh, hv)
    assert not valid[50, 50] and not dark[50, 50]
    assert dark[50, 51]


def test_shadow_prone_is_one_direction_only():
    hh, hv = scene()
    a_dark, _ = dark_mask(hh, hv)
    hh2, hv2 = hh.copy(), hv.copy()
    hh2[STRIP], hv2[STRIP] = -7.0, -14.0
    d_dark, _ = dark_mask(hh2, hv2)
    sp = shadow_prone({"156A": a_dark, "063D": d_dark}, {"156A": "A", "063D": "D"})
    assert sp[STRIP].all() and not sp[LAKE].any()


def test_shadow_prone_none_with_single_direction():
    hh, hv = scene()
    dark, _ = dark_mask(hh, hv)
    assert shadow_prone({"156A": dark, "157A": dark}, {"156A": "A", "157A": "A"}) is None


def test_pass_water_area_excludes_shadow():
    hh, hv = scene()
    zone = np.ones((100, 100), bool)
    sp = STRIP.copy()
    out = pass_water(hh, hv, zone, sp, pixel_m=10.0)
    assert out["area_km2"] == pytest.approx(LAKE.sum() * 100 / 1e6)


def test_pass_water_observable_share_counts_shadow_and_nan_as_unobservable():
    hh, hv = scene()
    zone = np.zeros((100, 100), bool)
    zone[0:20, 0:20] = True  # 400 pixels
    sp = np.zeros((100, 100), bool)
    sp[0:5, 0:20] = True  # 100 pixels
    hh[10:15, 0:20] = np.nan  # 100 pixels
    out = pass_water(hh, hv, zone, sp, pixel_m=10.0)
    assert out["observable_share"] == pytest.approx(0.5)
    assert out["valid"] == 200


def test_pass_water_no_shadow_and_empty_zone():
    hh, hv = scene()
    out = pass_water(hh, hv, np.ones((100, 100), bool), None, pixel_m=10.0)
    assert out["area_km2"] == pytest.approx((LAKE | STRIP).sum() * 100 / 1e6)
    empty = pass_water(hh, hv, np.zeros((100, 100), bool), None, pixel_m=10.0)
    assert empty["observable_share"] == 0.0 and empty["area_km2"] == 0.0


def test_screen_passes_drops_bright_outlier():
    land = np.full((20, 20), -7.0)
    ex = screen_passes({"a": land, "b": land + 0.5, "c": land + 25.0, "d": land - 0.4})
    assert list(ex) == ["c"] and "dB" in ex["c"]


def test_screen_passes_ignores_nan_pixels():
    land = np.full((20, 20), -7.0)
    nanny = land.copy()
    nanny[:10] = np.nan
    assert screen_passes({"a": land, "b": nanny, "c": land}) == {}


def test_lake_zone_point_circle():
    zone = lake_zone((100, 100), X, Y, EPSG, centre_lake(), half_km=0.3)
    assert zone[50, 50] and not zone[50, 90] and not zone[10, 50]
    assert zone.sum() == pytest.approx(np.pi * 30 ** 2, rel=0.05)


def test_lake_zone_polygon_buffered_200m():
    to_ll = Transformer.from_crs(EPSG, 4326, always_xy=True)
    corners = [(X[40], Y[40]), (X[60], Y[40]), (X[60], Y[60]), (X[40], Y[60]), (X[40], Y[40])]
    ring = [to_ll.transform(cx, cy) for cx, cy in corners]
    zone = lake_zone((100, 100), X, Y, EPSG, centre_lake(), outline_polygon=ring)
    assert zone[50, 50] and zone[50, 41]
    assert zone[50, 75]  # ~15 px = 150 m beyond the edge, inside the 200 m buffer
    assert not zone[50, 90]  # ~300 m beyond
    assert not zone[5, 5]


def test_despeckle_constant_field_unchanged():
    from sartale.lakewater import despeckle
    assert np.allclose(despeckle(np.full((9, 9), 0.2)), 0.2)


def test_despeckle_fills_single_nan():
    from sartale.lakewater import despeckle
    p = np.full((9, 9), 0.2)
    p[4, 4] = np.nan
    out = despeckle(p)
    assert np.isfinite(out[4, 4]) and out[4, 4] == pytest.approx(0.2)


def test_despeckle_all_nan_neighbourhood_stays_nan():
    from sartale.lakewater import despeckle
    p = np.full((9, 9), 0.2)
    p[2:7, 2:7] = np.nan
    assert np.isnan(despeckle(p)[4, 4])



def test_lake_zone_circle_uses_the_lakes_own_radius():
    from dataclasses import replace

    lake = centre_lake()  # 1 km by default: wider than the 1 km-across test grid, so every pixel
    assert lake_zone((100, 100), X, Y, EPSG, lake).all()
    small = replace(lake, zone_radius_km=0.3)  # 300 m: about pi * 30^2 pixels of 10 m
    zone = lake_zone((100, 100), X, Y, EPSG, small)
    assert zone[50, 50] and not zone[50, 85] and zone.sum() == pytest.approx(np.pi * 30 ** 2, rel=0.03)
    assert lake_zone((100, 100), X, Y, EPSG, small, half_km=0.1).sum() == pytest.approx(np.pi * 10 ** 2, rel=0.08)
