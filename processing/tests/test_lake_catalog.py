import pytest

from sartale import lake_catalog
from sartale.lake_catalog import Pass, coverage_report, pass_from_umm, search_lake_passes, select_lake_passes
from sartale.lakes import Lake

LAKE = Lake(id="x", name="X", lon=74.0, lat=36.0, coord_source="s", outline=None, role="watch",
            downstream=None, downstream_source=None)


def name(track="156", d="A", frame="020", mode="4005", start="20260625T010203", crid="P05023"):
    return f"NISAR_L2_PR_GCOV_023_{track}_{d}_{frame}_{mode}_DHDH_A_{start}_{start}_{crid}_N_F_J_001"


def umm(n=None, url=True):
    n = n or name()
    urls = [{"URL": f"https://x/{n}.h5"}, {"URL": f"https://x/{n}.h5.md5"}] if url else [{"URL": f"https://x/{n}.xml"}]
    return {"umm": {"GranuleUR": n, "RelatedUrls": urls}}


def make_pass(track="156", d="A", crid="P05023", mode="4005", date="2026-06-25"):
    s = date.replace("-", "") + "T010203"
    return pass_from_umm(umm(name(track, d, mode=mode, start=s, crid=crid)))


def test_parse_pass_from_granule():
    p = pass_from_umm(umm())
    assert (p.track, p.direction, p.frame, p.mode, p.crid, p.date) == ("156", "A", "020", "4005", "P05023", "2026-06-25")
    assert p.key == "156A" and p.url.endswith(".h5")


def test_pass_keeps_leading_zeros_of_track():
    assert make_pass(track="063", d="D").key == "063D"


def test_pass_from_umm_without_h5_is_none():
    assert pass_from_umm(umm(url=False)) is None


def test_select_lake_passes_keeps_mode_4005_after_jun17():
    keep = [make_pass(date="2026-06-17"), make_pass(date="2026-06-25")]
    drop = [make_pass(mode="2005"), make_pass(date="2026-06-10")]
    out = select_lake_passes(drop + keep)
    assert [p.date for p in out["156A"]] == ["2026-06-17", "2026-06-25"]


def test_select_lake_passes_rejects_mixed_crid():
    with pytest.raises(ValueError, match="CRID"):
        select_lake_passes([make_pass(crid="P05023"), make_pass(crid="P05024", date="2026-07-07")])


def test_select_lake_passes_allows_other_crid_on_other_track():
    out = select_lake_passes([make_pass(crid="P05023"), make_pass(track="063", d="D", crid="P05024")])
    assert set(out) == {"156A", "063D"}


def test_coverage_report_marks_enough_looks():
    p1, p2, p3 = (make_pass(date=f"2026-07-0{i}") for i in (1, 2, 3))
    p4 = make_pass(track="063", d="D")
    rep = coverage_report([LAKE], {"x": {"156A": [p1, p2, p3], "063D": [p4]}})
    assert rep[0]["tracks"] == {"156A": 3, "063D": 1} and rep[0]["enough_looks"] is True


def test_coverage_report_keeps_lake_without_enough_looks():
    p = make_pass(track="063", d="D")
    other = Lake(**{**LAKE.__dict__, "id": "y"})
    rep = coverage_report([LAKE, other], {"x": {"063D": [p, p]}})
    assert [r["enough_looks"] for r in rep] == [False, False]
    assert rep[1]["tracks"] == {}


class FakeSession:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        page = self.pages[params["page_num"] - 1]
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"items": page}})()


def test_search_lake_passes_queries_the_point_and_pages_until_short(monkeypatch):
    monkeypatch.setattr(lake_catalog, "PAGE_SIZE", 2)
    a, b, c = (umm(name(start=f"2026070{i}T010203")) for i in (1, 2, 3))
    s = FakeSession([[a, b], [c]])
    out = search_lake_passes(LAKE, session=s)
    assert [p.date for p in out] == ["2026-07-01", "2026-07-02", "2026-07-03"]
    assert len(s.calls) == 2
    assert s.calls[0]["point"] == "74.0,36.0" and s.calls[0]["short_name"] == "NISAR_L2_GCOV_PROVISIONAL_V1"


def test_search_lake_passes_lists_each_granule_once(monkeypatch):
    s = FakeSession([[umm(), umm()]])
    assert len(search_lake_passes(LAKE, session=s)) == 1


def test_search_lake_passes_skips_items_without_h5():
    assert search_lake_passes(LAKE, session=FakeSession([[umm(url=False)]])) == []
