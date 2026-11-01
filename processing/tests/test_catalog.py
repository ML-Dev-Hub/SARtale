import pytest

from sartale.catalog import parse_granule, select_stack

NAME = "NISAR_L2_PR_GCOV_023_063_D_071_2005_QPDH_A_20260618T135450_20260618T135525_P05023_N_F_J_001"


def make(cycle="020", track="084", direction="A", frame="019", mode="4005",
         pole="DHDH", start="20260702T010203", crid="P05023", acc="N", cov="F", src="A"):
    return (f"NISAR_L2_PR_GCOV_{cycle}_{track}_{direction}_{frame}_{mode}_{pole}_{src}_"
            f"{start}_{start}_{crid}_{acc}_{cov}_J_001")


@pytest.fixture
def sample():
    return [
        make(start="20260819T010203"),
        make(start="20260702T010203"),
        make(track="063", direction="D", frame="071"),
        make(mode="2005", pole="QPDH"),
        make(frame="020"),
    ]


def stack(names):
    return select_stack([parse_granule(n) for n in names], "084_A_019", "4005", "DHDH")


def test_parse_granule_reads_all_fields():
    g = parse_granule(NAME)
    assert (g.cycle, g.track, g.direction, g.frame) == (23, 63, "D", 71)
    assert (g.mode, g.pole, g.source, g.crid) == ("2005", "QPDH", "A", "P05023")
    assert (g.accuracy, g.coverage) == ("N", "F")


def test_select_stack_keeps_only_requested_stack(sample):
    out = stack(sample)
    assert [g.start.strftime("%Y%m%d") for g in out] == ["20260702", "20260819"]
    assert all((g.track, g.direction, g.frame, g.mode, g.pole) == (84, "A", 19, "4005", "DHDH") for g in out)


def test_select_stack_excludes_partial_frame(sample):
    out = stack(sample + [make(start="20260915T010203", cov="P")])
    assert len(out) == 2


def test_select_stack_excludes_other_crid_and_says_so(sample, capsys):
    other = make(start="20260915T010203", crid="P05024")
    out = stack(sample + [other])
    assert [g.start.strftime("%Y%m%d") for g in out] == ["20260702", "20260819"]
    assert all(g.crid == "P05023" for g in out)
    printed = capsys.readouterr().out
    assert "P05024" in printed and other in printed and "Excluded 1" in printed


def test_select_stack_raises_only_when_no_granule_has_the_crid(capsys):
    with pytest.raises(ValueError, match="P05023") as err:
        stack([make(start="20260819T010203", crid="P05024")])
    assert "P05024" in str(err.value)


def test_select_stack_raises_when_the_stack_is_empty():
    with pytest.raises(ValueError, match="No granule"):
        stack([make(track="063", direction="D", frame="071")])


def test_select_stack_lists_a_granule_found_twice_once(sample):
    out = stack(sample + sample)
    assert [g.start.strftime("%Y%m%d") for g in out] == ["20260702", "20260819"]


def test_select_stack_excludes_dates_in_gap(sample):
    out = stack(sample + [make(start="20260801T010203")])
    assert len(out) == 2


def test_select_stack_keeps_forecast_accuracy(sample):
    out = stack(sample + [make(start="20260714T010203", acc="F")])
    assert len(out) == 3 and out[1].accuracy == "F"


def test_select_stack_excludes_non_a_source(sample):
    out = stack(sample + [make(start="20260915T010203", src="B")])
    assert len(out) == 2
    assert all(g.source == "A" for g in out)


# --- search_cmr: paging, duplicates, size and MD5 -----------------------------------

def _item(name, size=1234, md5="a" * 32):
    return {"umm": {"GranuleUR": name, "DataGranule": {"ArchiveAndDistributionInformation": [
        {"Name": name + ".xml", "SizeInBytes": 9, "Checksum": {"Value": "x", "Algorithm": "MD5"}},
        {"Name": name + ".h5", "SizeInBytes": size, "Checksum": {"Value": md5, "Algorithm": "MD5"}},
    ]}}}


def test_search_cmr_pages_dedupes_and_keeps_size_and_md5(monkeypatch):
    import io
    import json

    from sartale import catalog

    names = [make(start=f"2026{m:02d}19T010203") for m in (7, 8, 9)]
    pages = [[_item(names[0]), _item(names[1])], [_item(names[1]), _item(names[2], size=77, md5="b" * 32)], []]
    monkeypatch.setattr(catalog, "PAGE_SIZE", 2)
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return io.StringIO(json.dumps({"items": pages[len(calls) - 1]}))

    monkeypatch.setattr(catalog.urllib.request, "urlopen", fake_urlopen)
    out = catalog.search_cmr()
    assert [g.name for g in out] == names  # the repeated granule on page 2 appears once
    assert len(calls) == 3
    assert (out[0].size, out[0].md5) == (1234, "a" * 32)
    assert (out[2].size, out[2].md5) == (77, "b" * 32)


def test_write_manifest_stores_size_and_md5(tmp_path):
    import json

    from sartale.catalog import write_manifest

    g = parse_granule(make(start="20260819T010203"))
    from dataclasses import replace
    write_manifest([replace(g, size=5, md5="c" * 32)], tmp_path / "m.json")
    entry = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["granules"][0]
    assert entry["size"] == 5 and entry["md5"] == "c" * 32
