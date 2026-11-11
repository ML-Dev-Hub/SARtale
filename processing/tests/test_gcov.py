import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np
import pytest
from pyproj import Transformer

from gcov_fixture import CENTER_LONLAT, EPSG, N, STEP, write_gcov
from sartale.gcov import apply_mask, check_identity, mask_histogram, read_layer

FULL_BBOX = (71.4, 33.9, 72.1, 34.4)
BBOX_INSIDE_FIXTURE = (71.74, 34.14, 71.76, 34.16)
BBOX_OUTSIDE = (10.0, 10.0, 10.1, 10.1)


def _write(path, descending_y):
    return write_gcov(path, descending_y=descending_y)


@pytest.fixture(params=[False, True], ids=["y-asc", "y-desc"])
def gcov_file(tmp_path, request):
    return _write(tmp_path / "g.h5", request.param)


def test_read_layer_clips_to_bbox(gcov_file):
    full = read_layer(gcov_file, "HHHH", FULL_BBOX)
    layer = read_layer(gcov_file, "HHHH", BBOX_INSIDE_FIXTURE)
    assert layer.power.shape == (layer.y.size, layer.x.size)
    assert 0 < layer.power.size < full.power.size
    assert layer.looks.shape == layer.power.shape and layer.mask.shape == layer.power.shape
    cx, cy = Transformer.from_crs(4326, EPSG, always_xy=True).transform(*CENTER_LONLAT)
    assert abs(layer.x.mean() - cx) < 3 * STEP and abs(layer.y.mean() - cy) < 3 * STEP


def test_read_layer_masks_invalid_values(gcov_file):
    assert np.isnan(read_layer(gcov_file, "HHHH", FULL_BBOX).power[0, 0])


def test_read_layer_keeps_epsg(gcov_file):
    assert read_layer(gcov_file, "HVHV", FULL_BBOX).epsg == 32642


def test_read_layer_rejects_missing_term(gcov_file):
    with pytest.raises(KeyError, match="VVVV"):
        read_layer(gcov_file, "VVVV", FULL_BBOX)


def test_read_layer_rejects_bbox_outside_grid(gcov_file):
    with pytest.raises(ValueError, match="outside"):
        read_layer(gcov_file, "HHHH", BBOX_OUTSIDE)


# --- mask --------------------------------------------------------------------------

def _mask_with(fill_rows=(), zero_rows=(), subswath=1):
    mask = np.full((N, N), subswath, "u1")
    for r in fill_rows:
        mask[r] = 255
    for r in zero_rows:
        mask[r] = 0
    return mask


def test_read_layer_masks_fill_255(tmp_path):
    path = write_gcov(tmp_path / "g.h5", mask=_mask_with(fill_rows=[5]))
    layer = read_layer(path, "HHHH", FULL_BBOX)
    assert np.isnan(layer.power[5]).all()
    assert np.isfinite(layer.power[6]).all()


def test_read_layer_masks_zero_when_real_subswaths_are_present(tmp_path):
    path = write_gcov(tmp_path / "g.h5", mask=_mask_with(zero_rows=[7], fill_rows=[8], subswath=2))
    layer = read_layer(path, "HHHH", FULL_BBOX)
    assert np.isnan(layer.power[7]).all() and np.isnan(layer.power[8]).all()
    assert np.isfinite(layer.power[9]).all()


def test_production_zero_is_invalid_even_when_the_clip_holds_no_subswath_number(tmp_path):
    """C01: a production crop that lies wholly in mask-0 (partially focused) coverage has no valid sample."""
    mask = np.zeros((N, N), "u1")
    mask[10] = 255
    path = write_gcov(tmp_path / "g.h5", mask=mask, release_id="P05023")
    layer = read_layer(path, "HHHH", FULL_BBOX)
    assert np.isnan(layer.power).all()


def test_zero_rule_is_per_sample_whatever_the_clip(tmp_path):
    """The same mask-0 pixel is invalid in the whole file and in a clip that holds only zeros."""
    mask = np.zeros((N, N), "u1")
    mask[:10] = 3  # subswath numbers only in the far rows of the file
    path = write_gcov(tmp_path / "g.h5", mask=mask, release_id="P05036")
    full = read_layer(path, "HHHH", FULL_BBOX)
    assert np.isnan(full.power[50]).all()
    assert np.isfinite(full.power[5, 1:]).all()  # subswath 3 stays valid
    clip = read_layer(path, "HHHH", BBOX_INSIDE_FIXTURE)
    assert clip.mask.max() == 0
    assert np.isnan(clip.power).all()


def test_a_file_without_a_release_id_follows_the_production_rule(tmp_path):
    path = write_gcov(tmp_path / "g.h5", mask=np.zeros((N, N), "u1"))
    assert np.isnan(read_layer(path, "HHHH", FULL_BBOX).power).all()


def test_only_the_pre_launch_sample_convention_keeps_zero(tmp_path):
    """The 2008 samples (CRID D00404) hold only {0, 255} across the whole file, with 0 on every real sample."""
    mask = np.zeros((N, N), "u1")
    mask[10] = 255
    path = write_gcov(tmp_path / "g.h5", mask=mask, release_id="D00404")
    layer = read_layer(path, "HHHH", FULL_BBOX)
    assert np.isnan(layer.power[10]).all()
    assert np.isfinite(layer.power[11]).all()
    assert np.isfinite(layer.power[50]).all()


def test_apply_mask_rule_by_crid():
    power = np.ones((3, 3))
    zeros = np.zeros((3, 3), "u1")
    assert np.isnan(apply_mask(power, zeros)).all()
    assert np.isnan(apply_mask(power, zeros, "P05023")).all()
    assert np.isfinite(apply_mask(power, zeros, "D00404")).all()


def test_layer_keeps_the_raw_mask_for_the_histogram(tmp_path):
    path = write_gcov(tmp_path / "g.h5", mask=_mask_with(fill_rows=[0], zero_rows=[1]))
    layer = read_layer(path, "HHHH", FULL_BBOX)
    assert mask_histogram(layer.mask) == {0: N, 1: N * (N - 2), 255: N}


def test_mask_histogram_without_a_mask_is_empty():
    assert mask_histogram(None) == {}


def test_apply_mask_rejects_a_mask_of_another_shape():
    with pytest.raises(ValueError, match="shape"):
        apply_mask(np.ones((3, 3)), np.ones((2, 2), "u1"))


# --- identification ----------------------------------------------------------------

GRANULE = "NISAR_L2_PR_GCOV_026_084_A_019_4005_DHDH_A_20260726T002237_20260726T002312_P05023_N_F_J_001"


def test_check_identity_accepts_a_matching_file(tmp_path):
    path = write_gcov(tmp_path / "g.h5", granule_id=GRANULE, release_id="P05023")
    check_identity(path, GRANULE, "P05023")


def test_check_identity_rejects_a_renamed_file(tmp_path):
    path = write_gcov(tmp_path / "g.h5", granule_id=GRANULE.replace("20260726", "20260819"), release_id="P05023")
    with pytest.raises(ValueError, match="manifest expects"):
        check_identity(path, GRANULE, "P05023")


def test_check_identity_rejects_another_release(tmp_path):
    path = write_gcov(tmp_path / "g.h5", granule_id=GRANULE, release_id="P05024")
    with pytest.raises(ValueError, match="P05024"):
        check_identity(path, GRANULE, "P05023")


def test_check_identity_skips_release_when_the_field_is_absent(tmp_path):
    path = write_gcov(tmp_path / "g.h5", granule_id=GRANULE)
    check_identity(path, GRANULE, "P05023")


def test_check_identity_needs_a_granule_id(tmp_path):
    path = write_gcov(tmp_path / "g.h5")
    with pytest.raises(ValueError, match="granuleId"):
        check_identity(path, GRANULE, "P05023")


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"


@pytest.mark.skipif(not SAMPLE_DIR.is_dir() or not list(SAMPLE_DIR.glob("*.h5")), reason="public 2008 sample not present")
def test_identity_field_names_match_the_public_2008_sample():
    path = sorted(SAMPLE_DIR.glob("*.h5"))[0]
    check_identity(path, path.stem, "D00404")
