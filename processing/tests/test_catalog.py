import pytest

from sartale.catalog import parse_granule

NAME = "NISAR_L2_PR_GCOV_023_063_D_071_2005_QPDH_A_20260618T135450_20260618T135525_P05023_N_F_J_001"


def test_parse_granule_reads_all_fields():
    g = parse_granule(NAME)
    assert (g.cycle, g.track, g.direction, g.frame) == (23, 63, "D", 71)
    assert (g.mode, g.pole, g.source, g.crid) == ("2005", "QPDH", "A", "P05023")
    assert (g.accuracy, g.coverage) == ("N", "F")


def test_parse_granule_accepts_the_h5_file_name():
    assert parse_granule(NAME + ".h5").name == NAME


def test_parse_granule_rejects_other_products():
    with pytest.raises(ValueError):
        parse_granule(NAME.replace("_GCOV_", "_GSLC_"))
