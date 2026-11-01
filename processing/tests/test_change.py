import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
import rasterio
from PIL import Image
from pyproj import Transformer

from sartale import config
from sartale.change import (
    DATE_NOTES,
    EXCLUDED_REASON,
    MIN_VALID_DATES,
    SCALE_FLOOR_DB,
    add_change_scores,
    build_change,
    change_score,
    control_threshold,
    normalise_scene_drift,
    render_change_frame,
    robust_baseline,
    scene_offsets,
    score_plan,
    season_scores,
    stable_pixels,
)
from sartale.gcov import Layer
from sartale.products import FORECAST_FLAG, INTERFERENCE_DATE, INTERFERENCE_FLAG, write_cog
from sartale.run_pipeline import main

DATES = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
         "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18"]
SCORED = DATES[1:]
BASELINE = DATES[2:]


def _stack(values_hh, values_hv=None):
    """(dates, pols, 1, 1) from one curve per polarization."""
    hv = values_hh if values_hv is None else values_hv
    return np.array([values_hh, hv], dtype=np.float32).T[:, :, None, None]


def _use(n, off=()):
    use = np.ones(n, bool)
    use[list(off)] = False
    return use


# --- robust_baseline --------------------------------------------------------------

def test_baseline_median_and_scale_of_a_known_curve():
    # median 2; absolute deviations 2, 1, 0, 1, 2 have median 1; 1.4826 x 1 is the scale
    stack = _stack([0.0, 1.0, 2.0, 3.0, 4.0])
    median, scale = robust_baseline(stack, _use(5))
    assert median.shape == scale.shape == (2, 1, 1)
    assert median[0, 0, 0] == pytest.approx(2.0)
    assert scale[0, 0, 0] == pytest.approx(1.4826)


def test_baseline_uses_only_the_dates_in_use():
    stack = _stack([0.0, 0.0, 0.0, 0.0, 0.0, 50.0])
    median, _ = robust_baseline(stack, _use(6, off=[5]))
    assert median[0, 0, 0] == 0
    many = _stack([50.0, 50.0, 50.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert robust_baseline(many, _use(8, off=[0, 1, 2]))[0][0, 0, 0] == 0


def test_floor_stops_a_tiny_scale_from_exploding_scores():
    stack = _stack([1.0, 1.0, 1.0, 1.0, 1.0, 1.001])
    _, scale = robust_baseline(stack, _use(6, off=[5]))
    assert scale[0, 0, 0] == SCALE_FLOOR_DB == 1.0
    baseline = robust_baseline(stack, _use(6, off=[5]))
    assert change_score(stack[5:], baseline)[0, 0, 0] == pytest.approx(0.001, abs=1e-5)
    # without a floor this 0.1 dB step over a zero spread would be infinite
    step = _stack([1.0, 1.0, 1.0, 1.0, 1.0, 1.1])
    assert change_score(step[5:], robust_baseline(step, _use(6, off=[5])))[0, 0, 0] == pytest.approx(0.1, abs=1e-5)


def test_baseline_ignores_nan_dates_at_a_pixel():
    stack = _stack([0.0, 2.0, np.nan, 4.0, 6.0, 8.0])
    median, _ = robust_baseline(stack, _use(6))
    assert median[0, 0, 0] == pytest.approx(4.0)


def test_a_pixel_with_fewer_than_four_valid_dates_has_no_baseline_and_no_score():
    assert MIN_VALID_DATES == 4
    stack = _stack([0.0, 1.0, 2.0, np.nan, np.nan, np.nan])
    median, scale = robust_baseline(stack, _use(6))
    assert np.isnan(median).all() and np.isnan(scale).all()
    assert np.isnan(season_scores(stack, _use(6))).all()
    enough = _stack([0.0, 1.0, 2.0, 3.0, np.nan, np.nan])
    assert np.isfinite(robust_baseline(enough, _use(6))[0]).all()


def test_baseline_refuses_a_use_of_the_wrong_length():
    with pytest.raises(ValueError, match="use"):
        robust_baseline(_stack([0.0, 1.0, 2.0, 3.0]), _use(5))


# --- change_score -----------------------------------------------------------------

def test_a_stable_pixel_scores_low():
    rng = np.random.default_rng(1)
    stack = _stack(0.3 * rng.standard_normal(8), 0.3 * rng.standard_normal(8))
    assert np.nanmax(season_scores(stack, _use(8))) < 1.5


def test_a_step_change_scores_high_on_its_date_only():
    curve = [0.1, -0.1, 0.0, 0.2, -6.0, 0.1, -0.2, 0.0]
    scores = season_scores(_stack(curve), _use(8))
    assert scores[4, 0, 0] > 4
    assert np.delete(scores[:, 0, 0], 4).max() < 1


def test_score_is_the_larger_of_the_two_polarizations():
    stack = _stack([0.0] * 6 + [2.0], [0.0] * 6 + [-5.0])
    baseline = robust_baseline(stack, _use(7, off=[6]))
    assert change_score(stack[6:], baseline)[0, 0, 0] == pytest.approx(5.0)


def test_nan_stays_nan_in_either_polarization():
    stack = _stack([0.0, 0.1, -0.1, np.nan, 0.2, 0.0], [0.0, 0.1, np.nan, 0.0, 0.1, 0.2])
    scores = season_scores(stack, _use(6))
    assert np.isnan(scores[3, 0, 0]) and np.isnan(scores[2, 0, 0])
    assert np.isfinite(scores[0, 0, 0])


def test_season_scores_leave_the_scored_date_out_of_its_own_baseline():
    # Median 2 and scale 1.4826 come from the five other dates. Counted in its own baseline it would read about 44.
    scores = season_scores(_stack([0.0, 1.0, 2.0, 3.0, 4.0, 100.0]), _use(6))
    assert scores[5, 0, 0] == pytest.approx(98 / 1.4826)


def test_a_date_outside_the_baseline_is_scored_but_changes_no_other_score():
    curve = [0.0, 0.3, -0.2, 0.1, 0.2, -0.1]
    wild = _stack([30.0] + curve)
    calm = _stack([0.0] + curve)
    use = _use(7, off=[0])
    a, b = season_scores(wild, use), season_scores(calm, use)
    assert a[0, 0, 0] > 10
    np.testing.assert_array_equal(a[1:], b[1:])


# --- scene drift ------------------------------------------------------------------

def _noisy_scene(seed=2, dates=8, shape=(40, 40)):
    rng = np.random.default_rng(seed)
    return (rng.normal(-8, 3, (1, 2, *shape)) + rng.normal(0, 0.2, (dates, 2, *shape))).astype(np.float32)


def test_stable_pixels_are_those_with_low_spread_in_both_polarizations():
    stack = _noisy_scene()
    stack[:, 0, 0, 0] += np.array([3, -3, 3, -3, 3, -3, 3, -3], dtype=np.float32)  # HH moves
    stack[:, 1, 0, 1] += np.array([3, -3, 3, -3, 3, -3, 3, -3], dtype=np.float32)  # HV moves
    mask = stable_pixels(stack, _use(8), quantile=0.5)
    assert mask.shape == (40, 40)
    assert not mask[0, 0] and not mask[0, 1]
    assert 0.2 < mask.mean() < 0.5


def test_stable_pixels_skip_masked_pixels():
    stack = _noisy_scene()
    stack[:, :, 3, 3] = np.nan
    assert not stable_pixels(stack, _use(8))[3, 3]


def test_scene_offsets_record_a_whole_scene_shift_per_date_and_polarization():
    stack = _noisy_scene()
    stack[2, 0] -= 1.0
    stack[5, 1] += 0.5
    offsets = scene_offsets(stack, np.ones((40, 40), bool), _use(8))
    assert offsets.shape == (8, 2)
    assert offsets[2, 0] == pytest.approx(-1.0, abs=0.1)
    assert offsets[5, 1] == pytest.approx(0.5, abs=0.1)
    assert np.delete(offsets[:, 0], 2) == pytest.approx(np.zeros(7), abs=0.1)


def test_scene_offset_of_a_date_outside_the_baseline_is_measured_against_the_baseline():
    stack = _noisy_scene()
    stack[0] -= 1.0
    offsets = scene_offsets(stack, np.ones((40, 40), bool), _use(8, off=[0]))
    assert offsets[0, 0] == pytest.approx(-1.0, abs=0.1)
    assert offsets[3, 0] == pytest.approx(0.0, abs=0.1)


def test_a_scene_wide_one_db_offset_scores_low_after_normalisation():
    stack = _noisy_scene()
    stack[3] -= 1.0
    use = _use(8)
    assert np.nanmedian(season_scores(stack, use)[3]) > 0.9  # the floor is 1 dB, so 1 dB reads about 1
    fixed = normalise_scene_drift(stack, np.ones((40, 40), bool), use)
    assert np.nanmedian(season_scores(fixed, use)[3]) < 0.4


def test_normalisation_keeps_nan_and_does_not_touch_the_input():
    stack = _noisy_scene()
    stack[:, :, 1, 1] = np.nan
    before = stack.copy()
    out = normalise_scene_drift(stack, ~np.isnan(stack[0, 0]), _use(8))
    assert np.isnan(out[:, :, 1, 1]).all()
    np.testing.assert_array_equal(stack, before)


def test_an_empty_stable_mask_is_refused():
    with pytest.raises(ValueError, match="stable"):
        scene_offsets(_noisy_scene(), np.zeros((40, 40), bool), _use(8))


# --- threshold --------------------------------------------------------------------

def test_threshold_is_the_control_99th_percentile_rounded_up_to_a_half():
    assert control_threshold(np.arange(0, 1001, dtype=np.float32) / 300) == 3.5  # p99 is 3.3
    assert control_threshold(np.arange(0, 1001, dtype=np.float32) / 280) == 4.0  # p99 is 3.54


def test_threshold_ignores_nan_and_refuses_no_data():
    values = np.concatenate([np.arange(0, 1001, dtype=np.float32) / 300, [np.nan] * 50])
    assert control_threshold(values) == 3.5
    with pytest.raises(ValueError, match="control"):
        control_threshold(np.array([np.nan]))


# --- which dates --------------------------------------------------------------------

def _entries(dates=DATES):
    out = []
    for d in dates:
        e = {"date": d, "granule": f"g{d}", "frames": {"HH": f"frames/{d}_HH.webp", "HV": f"frames/{d}_HV.webp"}}
        if d == INTERFERENCE_DATE:
            e["flag"] = INTERFERENCE_FLAG
        if d == "2026-07-14":
            e["flag"] = FORECAST_FLAG
        out.append(e)
    return out


def test_2_july_never_enters_a_baseline_and_is_not_scored():
    plan = score_plan(_entries())
    assert INTERFERENCE_DATE not in plan["baseline"]
    assert INTERFERENCE_DATE not in plan["scored"]
    assert plan["excluded"] == [{"date": INTERFERENCE_DATE, "reason": EXCLUDED_REASON}]


def test_the_forecast_orbit_date_is_scored_but_stays_out_of_the_baseline():
    plan = score_plan(_entries())
    assert "2026-07-14" in plan["scored"]
    assert plan["baseline"] == BASELINE


# --- frames -----------------------------------------------------------------------

def test_change_frame_is_transparent_below_threshold_and_for_nan():
    score = np.array([[1.0, 3.49, np.nan, 3.5, 5.0, 7.0, 20.0]])
    rgba = render_change_frame(score, 3.5, 7.0)
    assert rgba.shape == (1, 7, 4) and rgba.dtype == np.uint8
    assert (rgba[0, :3] == 0).all()
    assert (rgba[0, 3:, 3] > 0).all()


def test_change_frame_uses_one_shared_scale():
    a = render_change_frame(np.array([[4.0, 7.0]]), 3.5, 7.0)
    b = render_change_frame(np.array([[4.0, 4.0, 30.0]]), 3.5, 7.0)
    np.testing.assert_array_equal(a[0, 0], b[0, 0])
    np.testing.assert_array_equal(a[0, 1], b[0, 2])  # saturates at the shared top


# --- build ------------------------------------------------------------------------

N = 60
LON0, LAT0 = 72.0, 34.2
TO_UTM = Transformer.from_crs(4326, 32643, always_xy=True)
X0, Y0 = TO_UTM.transform(LON0, LAT0)


def _grid():
    x = X0 + (np.arange(N) - N / 2) * 30.0
    y = Y0 + (N / 2 - np.arange(N)) * 30.0
    return Layer(np.zeros((N, N)), x, y, 32643, None, None)


def _fixture(tmp_path, wild_2_july=False):
    """Eight quiet dates, a 9 dB drop in one block on 19 Aug, a NaN corner, and a 2 Jul that may be wild."""
    cog, out = tmp_path / "cog", tmp_path / "out"
    out.mkdir(parents=True)
    rng = np.random.default_rng(3)
    grid = _grid()
    for d in DATES:
        for pol in ("HH", "HV"):
            base = -6.0 if pol == "HH" else -13.0
            a = base + rng.normal(0, 0.4, (N, N)).astype(np.float32)
            if d == "2026-08-19":
                a[40:50, 40:50] -= 9.0
            if d == INTERFERENCE_DATE and wild_2_july:
                a += 25.0
            a[:3, :3] = np.nan
            write_cog(a, grid, cog / f"{d}_{pol}.tif")
    manifest = {"stack": "084_A_019", "crid": "P05023", "maturity": "Provisional",
                "bounds": list(config.WINDOW), "dates": _entries(), "analysis_m": 30}
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    sites_in = [{"id": "ctl", "name": "Control", "lon": LON0, "lat": LAT0, "role": "Stable urban control"},
                {"id": "chg", "name": "Block", "lon": 0.0, "lat": 0.0, "role": "Shore"}]
    to_ll = Transformer.from_crs(32643, 4326, always_xy=True)
    sites_in[1]["lon"], sites_in[1]["lat"] = to_ll.transform(grid.x[45], grid.y[45])
    return cog, out, sites_in


def test_build_change_writes_scores_frames_and_the_manifest_record(tmp_path):
    cog, out, sites_in = _fixture(tmp_path)
    change = build_change(cog, out, sites_in)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["change"] == change
    assert change["baseline_dates"] == BASELINE
    assert change["excluded"] == [{"date": INTERFERENCE_DATE, "reason": EXCLUDED_REASON}]
    assert list(change["frames"]) == SCORED
    assert set(change["removed_offsets_db"]) == set(SCORED)
    assert set(change["removed_offsets_db"]["2026-08-19"]) == {"HH", "HV"}
    assert change["library"] == "numpy" and change["version"] == np.__version__
    assert change["threshold"] > 0 and change["scale_max"] == 2 * change["threshold"]
    assert change["date_notes"] == DATE_NOTES
    assert m["maturity"] == "Provisional"
    for d in SCORED:
        assert (out / change["frames"][d]).is_file() and (cog / f"change_{d}.tif").is_file()
        with Image.open(out / change["frames"][d]) as img:
            assert img.mode == "RGBA"
    assert not (cog / f"change_{INTERFERENCE_DATE}.tif").exists()
    assert not (out / f"frames/change_{INTERFERENCE_DATE}.webp").exists()
    with rasterio.open(cog / "change_2026-08-19.tif") as src:
        score = src.read(1)
    assert src.crs.to_epsg() == 32643
    assert np.nanmedian(score[40:50, 40:50]) > 2 * change["threshold"]
    assert np.isnan(score[0, 0])


def test_2_july_cannot_change_any_output_of_build_change(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    cog_a, out_a, sites_in = _fixture(a)
    cog_b, out_b, _ = _fixture(b, wild_2_july=True)
    assert build_change(cog_a, out_a, sites_in) == build_change(cog_b, out_b, sites_in)
    with rasterio.open(cog_a / "change_2026-10-18.tif") as x, rasterio.open(cog_b / "change_2026-10-18.tif") as y:
        np.testing.assert_array_equal(x.read(1), y.read(1))


def test_build_change_refuses_a_site_list_without_controls(tmp_path):
    cog, out, sites_in = _fixture(tmp_path)
    with pytest.raises(ValueError, match="control"):
        build_change(cog, out, [s for s in sites_in if s["id"] != "ctl"])


def test_build_change_with_too_few_dates_leaves_no_layer(tmp_path, capsys):
    cog, out, sites_in = _fixture(tmp_path)
    path = out / "manifest.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    m["dates"] = m["dates"][:4]
    m["change"] = {"stale": True}
    path.write_text(json.dumps(m), encoding="utf-8")
    assert build_change(cog, out, sites_in) is None
    assert "change" not in json.loads(path.read_text(encoding="utf-8"))
    assert "not enough dates" in capsys.readouterr().out


def test_site_scores_are_null_on_excluded_dates_and_for_a_build_without_the_layer(tmp_path):
    cog, out, sites_in = _fixture(tmp_path)
    build_change(cog, out, sites_in)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    sites = [{**s, "series": [{"date": d} for d in DATES]} for s in sites_in]
    add_change_scores(sites, m, cog)
    by_date = {p["date"]: p["change_score"] for p in sites[1]["series"]}
    assert by_date[INTERFERENCE_DATE] is None
    assert by_date["2026-08-19"] > m["change"]["threshold"]
    assert by_date["2026-10-18"] < m["change"]["threshold"]
    assert all(v == round(v, 2) for v in by_date.values() if v is not None)
    bare = [{**s, "series": [{"date": d} for d in DATES]} for s in sites_in]
    add_change_scores(bare, {}, cog)
    assert all(p["change_score"] is None for s in bare for p in s["series"])


def test_site_score_is_null_where_nothing_is_valid(tmp_path):
    cog, out, sites_in = _fixture(tmp_path)
    build_change(cog, out, sites_in)
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    grid = _grid()
    lon, lat = Transformer.from_crs(32643, 4326, always_xy=True).transform(grid.x[0], grid.y[0])
    sites = [{"id": "x", "lon": lon, "lat": lat, "series": [{"date": "2026-08-19"}]}]
    add_change_scores(sites, m, cog, radius_m=20.0)
    assert sites[0]["series"][0]["change_score"] is None


def test_change_command_updates_the_manifest_and_the_sites_file_and_only_those(tmp_path, capsys):
    cog, out, sites_in = _fixture(tmp_path)
    sites_path = tmp_path / "sites_in.json"
    sites_path.write_text(json.dumps(sites_in), encoding="utf-8")
    (out / "frames").mkdir()
    keep = out / "frames" / "2026-07-26_HH.webp"
    keep.write_bytes(b"not re-encoded")
    site_rows = [{**s, "stack": "084_A_019", "crid": "P05023",
                  "series": [{"date": d, "hh_db": -6.0, "hv_db": -13.0, "valid_fraction": 1.0} for d in DATES]}
                 for s in sites_in]
    (out / "sites.json").write_text(json.dumps(site_rows), encoding="utf-8")
    main(["change", "--cog-dir", str(cog), "--out-dir", str(out), "--sites-in", str(sites_path)])
    assert keep.read_bytes() == b"not re-encoded"
    written = json.loads((out / "sites.json").read_text(encoding="utf-8"))
    assert all("change_score" in p for s in written for p in s["series"])
    assert written[0]["series"][1]["hh_db"] == -6.0
    printed = capsys.readouterr().out
    assert "threshold" in printed and "baseline" in printed
