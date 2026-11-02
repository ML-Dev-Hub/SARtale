"""Second per-track pass screen (ruling R-F1), the manual exclusion list, and the pictured pass (M4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest

from sartale import config
from sartale.lakebuild import build_lakes, pictured_pass, screen_all, season_dark
from sartale.lakewater import robust_z, screen_outliers
from test_lakebuild import built, lake, make_lake, write_pass  # noqa: F401 - `built` is a fixture


def test_robust_z_uses_the_floor_for_a_flat_track():
    z = robust_z({"a": 0.10, "b": 0.10, "c": 0.10, "d": 0.13}, floor=0.01)
    assert z["a"] == 0 and z["d"] == pytest.approx(3.0)


def test_screen_outliers_drops_a_dark_share_jump_with_a_reason():
    share = {"p1": 0.170, "p2": 0.175, "p3": 0.168, "p4": 0.172, "bad": 0.306}
    hv = {k: -13.0 for k in share}
    out = screen_outliers(share, hv)
    assert list(out) == ["bad"]
    assert "dark share" in out["bad"] and "robust z" in out["bad"]


def test_screen_outliers_drops_an_hv_shift_and_keeps_small_wobbles():
    share = {k: 0.15 for k in ("p1", "p2", "p3", "p4", "p5")}
    hv = {"p1": -14.0, "p2": -14.2, "p3": -13.9, "p4": -14.1, "p5": -10.0}
    out = screen_outliers(share, hv)
    assert list(out) == ["p5"] and "HV" in out["p5"]
    # 2.5 dB is under 3.5 x the 1 dB floor: kept (seasonal early-summer HV dips are this size)
    assert screen_outliers(share, {**hv, "p5": -11.5}) == {}


def test_screen_outliers_needs_enough_passes():
    assert screen_outliers({"a": 0.1, "b": 0.1, "c": 0.9}, {"a": -13.0, "b": -13.0, "c": -13.0}) == {}


def _pass(pid, hh_db, hv_db):
    date, key = pid.split("_")
    return {"id": pid, "key": key, "date": date, "hh_db": hh_db, "hv_db": hv_db}


def _scene(dark_frac, rng):
    """A 40x40 dB scene whose left `dark_frac` of columns is 10 dB darker (HH and HV)."""
    hh = -7.0 + rng.normal(0, 0.3, (40, 40))
    hh[:, : int(40 * dark_frac)] -= 10
    return hh, hh - 7


def test_screen_all_excludes_a_dark_share_outlier_and_keeps_it_out_of_the_season_median():
    rng = np.random.default_rng(1)
    good = [_pass(f"2026-0{m}-01_156A", *_scene(0.2, rng)) for m in range(6, 10)]
    bad = [_pass(f"2026-09-0{d}_156A", *_scene(0.35, rng)) for d in (5, 6, 7)]  # median HH barely moves
    # Only one bad pass on a track of good ones: the screen catches it.
    one = {"156A": good + bad[:1]}
    excluded = screen_all(one, manual={})
    assert list(excluded) == ["2026-09-05_156A"] and "dark share" in excluded["2026-09-05_156A"]
    # Excluded passes never reach the season median: with three bad passes of seven they would
    # (median of a column dark in 3/7 passes is not dark), so check against an explicit exclusion
    # of all three, where including them would flip columns 8..13 to dark.
    three = {"156A": good[:2] + bad}
    with_bad = season_dark(three, {})["156A"]
    without = season_dark(three, {p["id"]: "test" for p in bad})["156A"]
    assert with_bad[:, 8:14].mean() > 0.9
    assert without[:, 8:14].mean() < 0.05


def test_screen_all_applies_the_manual_list_with_its_reason():
    rng = np.random.default_rng(2)
    ps = [_pass(f"2026-0{m}-0{m}_156A", *_scene(0.2, rng)) for m in range(5, 10)]
    out = screen_all({"156A": ps}, manual={"2026-07-07_156A": "hand reason"})
    assert out == {"2026-07-07_156A": "hand reason"}


def test_config_lists_the_5_sep_pass():
    assert config.MANUAL_EXCLUSIONS["2026-09-05_156A"] == "anomalous over Hunza lakes; spec §5"


def test_build_puts_manual_exclusion_in_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MANUAL_EXCLUSIONS", {"2026-07-12_156A": "anomalous over Hunza lakes; spec §5"})
    cache, out = tmp_path / "c", tmp_path / "o"
    a = make_lake("alpha")
    for d in ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24"]:
        write_pass(cache, a, d, "156A")
    lk = build_lakes([a], cache, out, "t")["lakes"][0]
    assert lk["excluded"] == [{"pass": "2026-07-12_156A", "reason": "anomalous over Hunza lakes; spec §5"}]
    assert next(p for p in lk["series"] if p["date"] == "2026-07-12")["area_km2"] is None


def _pt(d, t, share=0.9, ex=None):
    return {"date": d, "track": t, "area_km2": None if ex else 0.1, "observable_share": share, "excluded": ex}


def test_pictured_pass_is_the_status_tracks_latest_valid_pass():
    series = [_pt("2026-10-01", "156A"), _pt("2026-10-13", "156A", share=0.2), _pt("2026-10-20", "156A", ex="bad"),
              _pt("2026-10-23", "055A")]
    assert pictured_pass(series, "156A") == "2026-10-01_156A"
    assert pictured_pass(series, None) == "2026-10-23_055A"
    assert pictured_pass([_pt("2026-10-01", "156A", share=0.1)], "156A") is None


def test_build_picture_date_matches_the_status(built):  # noqa: F811
    doc, _ = built
    alpha = lake(doc, "alpha")
    assert alpha["images"]["date"] == alpha["status"]["latest_date"]
    assert alpha["images"]["track"] == alpha["status"]["track"]
