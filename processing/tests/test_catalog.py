import pytest

from sartale.catalog import parse_granule, select_stack

NAME = "NISAR_L2_PR_GCOV_023_063_D_071_2005_QPDH_A_20260618T135450_20260618T135525_P05023_N_F_J_001"


def make(cycle="020", track="084", direction="A", frame="019", mode="4005",
         pole="DHDH", start="20260702T010203", crid="P05023", acc="N", cov="F"):
    return (f"NISAR_L2_PR_GCOV_{cycle}_{track}_{direction}_{frame}_{mode}_{pole}_A_"
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


def test_select_stack_rejects_mixed_crid(sample):
    with pytest.raises(ValueError, match="CRID"):
        stack(sample + [make(start="20260915T010203", crid="P05024")])


def test_select_stack_excludes_dates_in_gap(sample):
    out = stack(sample + [make(start="20260801T010203")])
    assert len(out) == 2


def test_select_stack_keeps_forecast_accuracy(sample):
    out = stack(sample + [make(start="20260714T010203", acc="F")])
    assert len(out) == 3 and out[1].accuracy == "F"
