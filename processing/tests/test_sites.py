import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from pyproj import Transformer

from gcov_fixture import CENTER_LONLAT, EPSG, write_gcov
from sartale.gcov import Layer
from sartale.run_pipeline import main
from sartale.sites import sample_site, sample_site_stats, stability_report, write_sites

N = 20
PX = 30.0
X0, Y0 = 500000.0, 3800000.0
TO_LONLAT = Transformer.from_crs(EPSG, 4326, always_xy=True)
# Site sits exactly between columns 9 and 10, on the row-9 centre line.
LON, LAT = TO_LONLAT.transform(X0 + 9.5 * PX, Y0 + 9 * PX)


def _layer(descending_y=False):
    x = X0 + np.arange(N) * PX
    y = Y0 + np.arange(N) * PX
    if descending_y:
        y = y[::-1]
    return Layer(np.ones((N, N)), x, y, EPSG, None, None)


@pytest.fixture
def layer():
    return _layer()


@pytest.fixture
def stack():
    # Left of the site 1.0, right of it 100.0 -> equal numbers in the radius.
    a = np.ones((2, N, N))
    a[:, :, 10:] = 100.0
    a[1] *= 0.5
    return a


@pytest.fixture
def masked_stack(stack):
    m = stack.copy()
    m[0] = np.nan
    return m


def test_sample_site_averages_in_linear_power(stack, layer):
    # mean of 1 and 100 is 50.5 -> 17.03 dB (the dB mean would be 10.0)
    assert sample_site(stack, layer, LON, LAT)[0] == pytest.approx(17.03, abs=0.01)


def test_sample_site_returns_one_value_per_date(stack, layer):
    out = sample_site(stack, layer, LON, LAT)
    assert len(out) == 2
    assert out[1] == pytest.approx(10 * np.log10(25.25), abs=0.01)


def test_sample_site_all_masked_returns_none(masked_stack, layer):
    out = sample_site(masked_stack, layer, LON, LAT)
    assert out[0] is None and out[1] is not None


def test_sample_site_outside_grid_raises(stack, layer):
    with pytest.raises(ValueError, match="outside"):
        sample_site(stack, layer, 0.0, 0.0)


def test_sample_site_descending_y_gives_same_answer(stack):
    flipped = _layer(descending_y=True)
    assert sample_site(stack, flipped, LON, LAT)[0] == pytest.approx(17.03, abs=0.01)


def test_sample_site_ignores_invalid_pixels_and_reports_fraction(stack, layer):
    s = stack.copy()
    s[0, :, 10:] = np.nan  # right half invalid on date 0
    db, frac = sample_site_stats(s, layer, LON, LAT)
    assert db[0] == pytest.approx(0.0, abs=1e-9)  # only the 1.0 pixels remain
    assert frac[0] == pytest.approx(0.5) and frac[1] == pytest.approx(1.0)


def test_sample_site_small_radius_uses_pixel_under_site(stack, layer):
    # radius smaller than the pixel spacing still returns the nearest pixel
    assert sample_site(stack, layer, LON, LAT, radius_m=1.0)[0] is not None


def test_sites_json_has_no_nan(tmp_path):
    sites = [{"id": "a", "name": "A", "lon": 71.7, "lat": 34.1, "role": "river",
              "series": [{"date": "2026-07-02", "hh_db": None, "hv_db": -20.0,
                          "valid_fraction": 0.0}]}]
    text = write_sites(sites, tmp_path / "sites.json").read_text()
    assert "NaN" not in text and json.loads(text)[0]["series"][0]["hh_db"] is None


def test_write_sites_rejects_nan(tmp_path):
    bad = [{"id": "a", "series": [{"hh_db": float("nan")}]}]
    with pytest.raises(ValueError):
        write_sites(bad, tmp_path / "sites.json")


def test_stability_report_ignores_gaps():
    assert stability_report([-8.0, None, -6.0]) == {"spread_db": 2.0, "n_valid": 2}


def test_stability_report_no_valid_values():
    assert stability_report([None, None]) == {"spread_db": None, "n_valid": 0}


# --- CLI end to end on a synthetic stack -----------------------------------------

DATES = ["2026-07-02", "2026-08-19", "2026-09-12"]
NAME_FMT = ("NISAR_L2_PR_GCOV_{cycle:03d}_084_A_019_4005_DHDH_A_{ymd}T220325_{ymd}T220400_"
            "P05023_N_F_J_001")


def _app_manifest(tmp_path):
    gdir = tmp_path / "gcov"
    gdir.mkdir()
    entries = []
    for i, d in enumerate(DATES):
        name = NAME_FMT.format(cycle=10 + i, ymd=d.replace("-", ""))
        write_gcov(gdir / f"{name}.h5", seed=i, scale=10 ** (-i / 2),
                   granule_id=name, release_id="P05023")
        entries.append({"date": d, "granule": name, "frames": {}})
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps({"stack": "084_A_019", "crid": "P05023", "dates": entries}), encoding="utf-8")
    return gdir, mpath


def test_sites_command_writes_contract(tmp_path):
    gdir, mpath = _app_manifest(tmp_path)
    lon, lat = CENTER_LONLAT
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([
        {"id": "s1", "name": "Site one", "lon": lon, "lat": lat, "role": "river"},
        {"id": "ctl", "name": "Control", "lon": lon + 0.01, "lat": lat, "role": "control"},
    ]), encoding="utf-8")
    out = tmp_path / "sites.json"
    main(["sites", "--gcov-dir", str(gdir), "--manifest", str(mpath),
          "--sites-in", str(sites_in), "--out", str(out), "--radius-m", "400"])
    sites = json.loads(out.read_text(encoding="utf-8"))

    assert [s["id"] for s in sites] == ["s1", "ctl"]
    assert list(sites[0]) == ["id", "name", "lon", "lat", "role", "stack", "crid", "series"]
    assert all(s["stack"] == "084_A_019" and s["crid"] == "P05023" for s in sites)
    assert [p["date"] for p in sites[0]["series"]] == DATES
    for s in sites:
        for p in s["series"]:
            assert list(p) == ["date", "hh_db", "hv_db", "valid_fraction"]
            assert 0 < p["valid_fraction"] <= 1
            assert p["hh_db"] == round(p["hh_db"], 2)
    # fixture power falls by 10**(-i/2) per date, i.e. -5 dB each step
    hh = [p["hh_db"] for p in sites[0]["series"]]
    assert hh[0] - hh[1] == pytest.approx(5.0, abs=1.5)  # speckle-like noise; trend only
    assert hh[0] > hh[1] > hh[2]


def test_sites_command_site_outside_grid_fails(tmp_path):
    gdir, mpath = _app_manifest(tmp_path)
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([{"id": "x", "name": "X", "lon": 0.0, "lat": 0.0,
                                     "role": "river"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        main(["sites", "--gcov-dir", str(gdir), "--manifest", str(mpath),
              "--sites-in", str(sites_in), "--out", str(tmp_path / "o.json")])


def test_sites_command_rejects_incomplete_site(tmp_path):
    gdir, mpath = _app_manifest(tmp_path)
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([{"id": "x", "name": "X", "lon": 71.7}]), encoding="utf-8")
    with pytest.raises(ValueError, match="lat"):
        main(["sites", "--gcov-dir", str(gdir), "--manifest", str(mpath),
              "--sites-in", str(sites_in), "--out", str(tmp_path / "o.json")])


def test_sites_command_refuses_a_manifest_without_provenance(tmp_path):
    gdir, mpath = _app_manifest(tmp_path)
    doc = json.loads(mpath.read_text(encoding="utf-8"))
    del doc["stack"], doc["crid"]
    mpath.write_text(json.dumps(doc), encoding="utf-8")
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([{"id": "x", "name": "X", "lon": 71.7, "lat": 34.1, "role": "river"}]),
                        encoding="utf-8")
    with pytest.raises(ValueError, match="stack, crid"):
        main(["sites", "--gcov-dir", str(gdir), "--manifest", str(mpath),
              "--sites-in", str(sites_in), "--out", str(tmp_path / "o.json")])


def test_sites_command_refuses_a_renamed_file(tmp_path):
    gdir, mpath = _app_manifest(tmp_path)
    entries = json.loads(mpath.read_text(encoding="utf-8"))["dates"]
    name = entries[0]["granule"]
    write_gcov(gdir / f"{name}.h5", granule_id=entries[1]["granule"], release_id="P05023")
    sites_in = tmp_path / "sites_in.json"
    sites_in.write_text(json.dumps([{"id": "x", "name": "X", "lon": CENTER_LONLAT[0], "lat": CENTER_LONLAT[1],
                                     "role": "river"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest expects"):
        main(["sites", "--gcov-dir", str(gdir), "--manifest", str(mpath),
              "--sites-in", str(sites_in), "--out", str(tmp_path / "o.json")])
