# SARtale Lake Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Execution method (chosen by the team):** Subagent-driven.

**Goal:** Turn SARtale into a NISAR glacial-lake watch for Gilgit-Baltistan and upper Khyber Pakhtunkhwa. Each lake gets a status, its evidence, and a printable brief, and the Peshawar valley story becomes one closing chapter.

**Architecture:**
- A Python pipeline reads small windows around each lake from remote NISAR GCOV files over HTTPS range requests. It caches the windows on `I:\SARtale\data\lakes\`, screens bad passes, applies the two-view water rule, and writes `app/public/data/lakes.json` plus per-lake images.
- The existing static TypeScript app gains a Lake Watch view, a lake brief, and a reordered story.
- No server is involved.

**Tech Stack:** Python 3.12 (conda env `sartale`): h5py, numpy, rasterio, pyproj, requests, pytest. Vite, TypeScript, MapLibre GL JS, uPlot, Vitest.

**Spec:** [docs/superpowers/specs/2026-11-02-glacial-lake-watch-design.md](../specs/2026-11-02-glacial-lake-watch-design.md)

**Branch:** create `build/lake-watch` from `build/sartale`.

**Out of scope for this plan:**
- Recording the 30-second video and building the deck. Task 11 writes their script and outline; producing them is a follow-up once the app is final.
- Deploying the app and making the repo public. Those are the team's actions.

## Global Constraints

**Data**
- NISAR product `NISAR_L2_GCOV_PROVISIONAL_V1`. Mode `4005`, polarisation `DHDH`, Frequency A, terms `HHHH` and `HVHV`, one CRID per track (`P05023` unless the catalogue shows only another).
- Calibrated data starts `2026-06-17`. Never use passes before that date or BETA products.
- Read windows remotely. Never download whole GCOV files for this plan.
- Never read, print or log the Earthdata credentials or `~/.netrc`. `requests` picks up the netrc by itself.
- Raw window caches live in `I:\SARtale\data\lakes\` (git-ignored). Only derived app data goes into git (Ruling R1).

**Lake method**
- Water rule constants:
  - `DROP_DB = 4.0`: dark means HH and HV are both at least 4 dB below the window median.
  - `BRIGHT_PASS_DB = 3.0`: a pass whose window-median HH is more than 3 dB from its track's median is excluded.
  - `MIN_LOOKS = 3` valid same-track passes are needed for a trend.
  - `MIN_OBSERVABLE = 0.5` of the lake zone must be observable.
  - `NOISE_FLOOR_KM2 = 0.005`.
  - `CHANGE_FACTOR = 2.0`.
- Status strings, exactly: `Growing`, `Stable`, `Shrinking`, `Not seen this pass`, `Not observable`, `Not enough NISAR looks yet`.
- Cloud window for the headline count: `2026-06-17` to `2026-08-04` inclusive, between SUPARCO's 16 Jun image and its "05 August 2026" update.

**Wording and copy**
- Every lake records the source of its coordinates, and the source of its outline if one is used. A point-only lake is labelled "water area in the search window".
- App copy may not contain: "early warning", "breach warning", "predict", "safe", "no risk", "detected flood", "flood detected", "damage", "risk score". Extend `BANNED_CLAIMS` in `app/src/content.ts` with the new words.
- Every number shown carries its date, its look count and its noise.
- The app is an indicative screening tool on provisional data. Every lake view and brief says so, and says that official warnings come from PMD and NDMA.

**Repo**
- Licence Apache-2.0. Add every new data source to `docs/DATA_SOURCES.md` and every SI tool to `docs/SI_USE.md`.
- Commits carry no `Co-Authored-By` trailer.

## Rulings made while planning

- **R1 — What gets committed.** The spec says to commit the window arrays. At about 2 MB per lake-pass, 12 lakes × 25 passes would add roughly 600 MB to git. Instead, raw windows stay in `data/lakes/`, and the derived products the demo needs (`lakes.json`, per-lake images) are committed. These are all the demo reads, so event-day independence holds. If this is wrong, the cost is re-fetching about 10 GB of windows.
- **R2 — Per-pass status versus the two-view rule.**
  - The two-view rule runs on each track's season-median images. It yields `shadow_prone` pixels: dark in one view's median but not in the other.
  - Per-pass water is "dark in this pass, inside the lake zone, not shadow-prone, valid".
  - This keeps the spec's two requirements together: a persistent mask from the medians, and a status from individual passes.

## Review Focus

1. **A lake zone sits mostly in radar shadow on every track.** The status says `Not observable`, never `Stable` or a zero area. Test: `test_status_not_observable_when_hidden` in Task 4.
2. **A pass is badly calibrated (+25 dB, as on 7 Jul, track 156).** It is excluded and listed with a reason, and never read as growth. Test: `test_screen_passes_drops_bright_outlier` in Task 3.
3. **A track mixes CRIDs or modes.** Selection fails loudly. Test: `test_select_lake_passes_rejects_mixed_crid` in Task 1.
4. **The connection drops mid-fetch.** The read is retried, and no half-written cache file is left behind. Test: `test_fetch_leaves_no_partial_cache` in Task 2.
5. **`lakes.json` is missing or fails to parse.** The app still opens, Lake Watch says "No lake data in this build", and the Peshawar chapter works. Test: `test_missing_lakes_file_shows_message` in Task 7.

---

## File Structure

```text
processing/
  lakes_in.json              lake register: id, name, lon, lat, coord_source, outline, role, downstream
  sartale/lakes.py           load and validate the register; lake window bbox
  sartale/lake_catalog.py    CMR search per lake, parse passes, select same-mode/CRID passes, coverage report
  sartale/remote.py          RangeFile with retries; read_window; fetch_lake_passes (cache writer)
  sartale/lakewater.py       pass screening, dark mask, two-view shadow-prone mask, per-pass water area
  sartale/lakestatus.py      per-track series, noise, status, cloud-window look count
  sartale/lakebuild.py       build lakes.json and per-lake images from caches
  sartale/lakecheck.py       Sentinel-2 MNDWI comparison (area error, IoU)
  run_pipeline.py            new subcommands: lakes-search, lakes-fetch, lakes-build, lakes-check
  tests/test_lakes.py, test_lake_catalog.py, test_remote.py, test_lakewater.py,
  tests/test_lakestatus.py, test_lakebuild.py, test_lakecheck.py
app/
  public/data/lakes.json, public/data/lakes/<id>/*.webp
  src/lakes.ts               Lake types, loadLakes, status labels and priority order
  src/lakeWatchView.ts       list, detail panel, per-track area chart, locator
  src/lakeLocator.ts         MapLibre locator (thin adapter, untested like maplibreAdapter.ts)
  src/lakeBrief.ts           one-page brief HTML and print action
  src/content/story.json     reordered story beats
  src/app.ts, main.ts        view wiring
docs/admin-meeting.md        questions and an answer log for the Islamabad meeting
docs/demo-script.md          30-second demo and deck outline
```

---

### Task 1: Lake register, catalogue search and coverage

**Files:**
- Create: `processing/lakes_in.json`, `processing/sartale/lakes.py`, `processing/sartale/lake_catalog.py`
- Test: `processing/tests/test_lakes.py`, `processing/tests/test_lake_catalog.py`
- Modify: `processing/sartale/run_pipeline.py` (subcommand `lakes-search`)

**Interfaces:**
- Produces:
  - `Lake` dataclass with fields `id: str`, `name: str`, `lon: float`, `lat: float`, `coord_source: str`, `outline: str | None` (path or URL of a published polygon), `role: Literal["watch", "control", "story"]`, `downstream: str | None`, `downstream_source: str | None`.
  - `load_lakes(path: Path) -> list[Lake]`
  - `lake_bbox(lake: Lake, half_km: float = 3.0) -> tuple[float, float, float, float]` (lon_min, lat_min, lon_max, lat_max)
  - `Pass` dataclass with fields `granule: str`, `url: str`, `date: str` (YYYY-MM-DD), `start: str` (ISO), `track: str` (e.g. `"156"`), `direction: Literal["A", "D"]`, `frame: str`, `mode: str`, `crid: str`, plus property `key -> f"{track}{direction}"`.
  - `pass_from_umm(item: dict) -> Pass | None`: one CMR `umm_json` item; returns `None` if the item has no `.h5` URL
  - `search_lake_passes(lake: Lake, session=None) -> list[Pass]`
  - `select_lake_passes(passes: list[Pass]) -> dict[str, list[Pass]]`, keyed by track key
  - `coverage_report(lakes: list[Lake], passes: dict[str, dict[str, list[Pass]]]) -> list[dict]`

- [ ] **Step 0: Confirm the baseline.** Run `conda run -n sartale python -m pytest processing -q` and `npm --prefix app test -- --run`. Expected: all pass. Record any failure in the ledger and fix it before going on (spec §7.5).

- [ ] **Step 1: Write `processing/lakes_in.json`** from these published points. Copy `coord_source` verbatim.

  | id | name | lat | lon | role | coord_source |
  |---|---|---|---|---|---|
  | `attabad` | Attabad Lake (landslide-dammed control) | 36.33 | 74.86 | control | "SARtale spike 2 Nov 2026: lake visible in NISAR passes" |
  | `shisper` | Shisper / Mochowar ice-dammed lake | 36.358 | 74.583 | story | "Centre of the lake map frame 36°21′–36°22′N, 74°34′–74°36′E, Muhammad et al. 2021, Fig. 2" |
  | `passu` | Passu terminal lake | 36.457 | 74.879 | watch | "Event table, doi:10.1016/j.rcar.2025.03.005" |
  | `khurdopin` | Khurdopin ice-dammed lake | 36.34 | 75.47 | watch | "Shrestha et al. 2023, ESSD 15:3941, Table 3" |
  | `ghulkin` | Ghulkin / Yaz-Sam lakes | 36.42 | 74.88 | watch | "Shrestha et al. 2023, ESSD 15:3941, Table 3" |
  | `karambar` | Karambar glacier-dammed lake | 36.62 | 74.08 | watch | "Shrestha et al. 2023, ESSD 15:3941, Table 3" |
  | `batura` | Unnamed Batura-associated lake | 36.51 | 74.85 | watch | "Shrestha et al. 2023, ESSD 15:3941, Table 3" |

  Then add up to 5 more GB/KP lakes, preferring KP (Chitral, Swat). Take them from the HMAGLOFDB lake table (https://github.com/fidelsteiner/HMAGLOFDB): only lake-location coordinates (not impact coordinates), inside 71–77.8°E and 34.5–37.1°N, with a recorded event since 2000. Set `coord_source` to "HMAGLOFDB, lake coordinate, event <date>". Set `downstream` only where a cited source names the settlement or asset, with `downstream_source` pointing to it; otherwise leave both `null`. The Shisper downstream entry is "Hassanabad village and the Karakoram Highway bridge", with source "Radio Pakistan, 7 May 2022".

- [ ] **Step 2: Write the failing tests.**

```python
def test_load_lakes_requires_coord_source(tmp_path):
    p = tmp_path / "l.json"
    p.write_text('[{"id":"x","name":"X","lon":74.0,"lat":36.0,"coord_source":"","role":"watch"}]')
    with pytest.raises(ValueError, match="coord_source"):
        load_lakes(p)

def test_load_lakes_rejects_duplicate_ids_and_bad_role(tmp_path): ...  # both raise ValueError

def test_lake_bbox_is_centred_and_sized():
    lon0, lat0, lon1, lat1 = lake_bbox(Lake(id="a", name="A", lon=74.86, lat=36.33, coord_source="s", outline=None, role="watch", downstream=None, downstream_source=None), half_km=3.0)
    assert lon0 < 74.86 < lon1 and lat0 < 36.33 < lat1
    assert (lat1 - lat0) * 111.32 == pytest.approx(6.0, rel=0.02)

def test_parse_pass_from_granule():
    p = pass_from_umm(UMM_FIXTURE)  # granule NISAR_L2_PR_GCOV_023_156_A_020_4005_DHDH_A_20260625T..._P05023_N_F_J_001
    assert (p.track, p.direction, p.frame, p.mode, p.crid, p.date) == ("156", "A", "020", "4005", "P05023", "2026-06-25")

def test_select_lake_passes_keeps_mode_4005_after_jun17(): ...  # drops 2005-mode and a 2026-06-10 pass

def test_select_lake_passes_rejects_mixed_crid():
    with pytest.raises(ValueError, match="CRID"):
        select_lake_passes([pass_with(crid="P05023"), pass_with(crid="P05024")])  # same track key

def test_coverage_report_marks_enough_looks():
    rep = coverage_report([lake], {"x": {"156A": [p1, p2, p3], "063D": [p4]}})
    assert rep[0]["tracks"] == {"156A": 3, "063D": 1} and rep[0]["enough_looks"] is True
```

- [ ] **Step 3: Run them.** `conda run -n sartale python -m pytest processing/tests/test_lakes.py processing/tests/test_lake_catalog.py -q`. Expected: FAIL (module not found).

- [ ] **Step 4: Implement** `lakes.py` and `lake_catalog.py`. `search_lake_passes` queries `https://cmr.earthdata.nasa.gov/search/granules.umm_json` with `short_name=NISAR_L2_GCOV_PROVISIONAL_V1`, `point=lon,lat`, `page_size=2000`, and pages until a short page. It takes the `.h5` URL from `RelatedUrls`. It parses the granule name the same way as `catalog.parse_granule`: reuse that if its fields fit, otherwise split on `_` with fields cycle, track, direction, frame, mode.

  Add `lakes-search` to `run_pipeline.py`. It writes `data/lakes/passes.json` and prints the coverage report, one line per lake.

- [ ] **Step 5: Run the tests.** Expected: PASS. Then run `conda run -n sartale python processing/sartale/run_pipeline.py lakes-search` on the real catalogue. Paste the coverage lines into the task report. Lakes without `enough_looks` stay in the register (spec §7.2).

- [ ] **Step 6: Commit.** `git commit -m "feat: add the lake register, per-lake NISAR pass search and coverage report"`

---

### Task 2: Remote window reader and cache

**Files:**
- Create: `processing/sartale/remote.py`
- Test: `processing/tests/test_remote.py` (reuse `processing/tests/gcov_fixture.py` to make a small HDF5 file)
- Modify: `run_pipeline.py` (subcommand `lakes-fetch`)

**Interfaces:**
- Consumes: `Pass`, `Lake`, `lake_bbox` (Task 1); `gcov.read_layer(path_or_fileobj, term, bbox)` (it already accepts a file-like object through `h5py.File`).
- Produces:
  - `RangeFile(session, url, block=1 << 20, retries=3)`: a seekable, read-only `io.RawIOBase`. Attributes `size`, `fetched`, `requests`.
  - `read_window(session, url, bbox) -> dict` with keys `hh`, `hv`, `looks`, `mask`, `x`, `y`, `epsg`.
  - `cache_path(cache_dir: Path, lake_id: str, p: Pass) -> Path`, which returns `cache_dir/lake_id/f"{p.date}_{p.key}_{p.crid}.npz"`.
  - `fetch_lake_passes(lake: Lake, passes: list[Pass], cache_dir: Path, session=None) -> list[Path]`: skips files already cached, writes `*.npz.part` and then renames it.

The reference implementation is `docs/research_notes/Glacial lake watch/spike/remote_read.py`. Port it, adding retries and the atomic write.

- [ ] **Step 1: Write the failing tests.** Use a fake session that serves byte ranges from a local fixture file, honours the `Range` header, and returns `Content-Range`.

```python
def test_rangefile_reads_same_bytes_as_local(fixture_h5): ...  # RangeFile(...).read() equals the file bytes
def test_read_window_matches_local_read_layer(fixture_h5): ...  # arrays equal gcov.read_layer on the local path
def test_rangefile_retries_after_disconnect(fixture_h5): ...    # session raises ConnectionError once, read succeeds, requests counted
def test_fetch_leaves_no_partial_cache(tmp_path, fixture_h5):
    # session fails on every attempt: fetch raises, and no *.npz or *.npz.part remains for that pass
def test_fetch_skips_cached(tmp_path, fixture_h5): ...          # second call makes zero range requests
```

- [ ] **Step 2: Run them.** `conda run -n sartale python -m pytest processing/tests/test_remote.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement `remote.py`.** Resolve the signed URL once with a `Range: bytes=0-0` GET and keep `r.url`. Retry with 1 s, 2 s and 4 s waits; after a retry, re-resolve the URL if the response was 403. Add `lakes-fetch`, which fetches every selected pass for every lake into `I:\SARtale\data\lakes\` and prints MB fetched per lake.

- [ ] **Step 4: Run the tests** (expected: PASS), then run `lakes-fetch` for real. Record the total MB and the elapsed time in the report.

- [ ] **Step 5: Commit.** `git commit -m "feat: read lake windows from remote NISAR files with retries and an atomic cache"`

---

### Task 3: Pass screening and the two-view water rule

**Files:**
- Create: `processing/sartale/lakewater.py`
- Test: `processing/tests/test_lakewater.py`

**Interfaces:**
- Consumes: cached window dicts (Task 2); `radiometry.to_db`.
- Produces:
  - `screen_passes(hh_db_by_pass: dict[str, np.ndarray]) -> dict[str, str]`. Input: pass id → HH dB window, for one track. Output: excluded pass id → reason, e.g. `"window median HH 24.6 dB from the track median"`.
  - `dark_mask(hh_db: np.ndarray, hv_db: np.ndarray, drop_db: float = DROP_DB) -> tuple[np.ndarray, np.ndarray]`. Returns `(dark, valid)`. NaN pixels are `valid=False, dark=False`.
  - `shadow_prone(median_dark_by_track: dict[str, np.ndarray], directions: dict[str, str]) -> np.ndarray | None`. Pixels dark in some view's median but not dark in any view of the opposite direction. Returns `None` when only one direction exists; the caller then labels the lake "single viewing direction".
  - `lake_zone(shape, x, y, epsg, lake: Lake, outline_polygon=None, half_km=1.0) -> np.ndarray`. The rasterised outline buffered by 200 m, or a circle of radius `half_km` around the point.
  - `pass_water(hh_db, hv_db, zone, shadow, pixel_m) -> dict` with keys `area_km2`, `observable_share`, `valid`.

- [ ] **Step 1: Write the failing tests.** Use synthetic 100×100 arrays: land at −7/−14 dB, a lake disc at −13/−20, a shadow strip at −22/−28 that is dark only in the "A" view.

```python
def test_dark_mask_finds_lake_not_land(): ...
def test_dark_mask_nan_is_invalid_not_dark(): ...
def test_shadow_prone_is_one_direction_only():
    sp = shadow_prone({"156A": a_dark, "063D": d_dark}, {"156A": "A", "063D": "D"})
    assert sp[strip].all() and not sp[lake].any()
def test_shadow_prone_none_with_single_direction(): ...
def test_pass_water_area_excludes_shadow():
    out = pass_water(hh, hv, zone, sp, pixel_m=10.0)
    assert out["area_km2"] == pytest.approx(lake_pixels * 100 / 1e6)
def test_pass_water_observable_share_counts_shadow_and_nan_as_unobservable(): ...
def test_screen_passes_drops_bright_outlier():
    ex = screen_passes({"a": land, "b": land + 0.5, "c": land + 25.0, "d": land - 0.4})
    assert list(ex) == ["c"] and "dB" in ex["c"]
```

- [ ] **Step 2: Run them** (expected: FAIL). **Step 3: Implement.** Use window medians via `np.nanmedian`. For `lake_zone`, rasterise with `rasterio.features.geometry_mask` after reprojecting the polygon with pyproj. **Step 4: Run them** (expected: PASS).

- [ ] **Step 5: Commit.** `git commit -m "feat: screen bad passes and find lake water with the two-view rule"`

---

### Task 4: Lake series and status

**Files:**
- Create: `processing/sartale/lakestatus.py`
- Test: `processing/tests/test_lakestatus.py`

**Interfaces:**
- Consumes: `pass_water` results per pass (Task 3).
- Produces:
  - `SeriesPoint = TypedDict(date: str, track: str, area_km2: float | None, observable_share: float, excluded: str | None)`
  - `track_noise_km2(areas: list[float]) -> float` = `max(1.4826 * median(|diff(areas)|), NOISE_FLOOR_KM2)`. A track with fewer than 3 areas gets `NOISE_FLOOR_KM2`.
  - `lake_status(series: list[SeriesPoint], latest_expected: dict[str, str] | None = None) -> dict` with keys `status`, `track`, `latest_date`, `looks`, `change_km2`, `noise_km2`, `reason`.
  - `cloud_window_looks(series, start="2026-06-17", end="2026-08-04") -> int`: valid, non-excluded points with `observable_share >= MIN_OBSERVABLE`.

The status rule is not determined by the signature, so here it is in full:

```text
valid = points with excluded is None and area_km2 is not None and observable_share >= MIN_OBSERVABLE
if no point has observable_share >= MIN_OBSERVABLE           -> "Not observable"
best track = the track whose latest valid point is newest (ties: more valid points)
if best track has < MIN_LOOKS valid points                   -> "Not enough NISAR looks yet"
if latest_expected given and the newest pass of any track is excluded or missing after the best
   track's latest valid date                                   -> "Not seen this pass" (reason names the pass)
ref = median of earlier valid areas on the best track; d = latest - ref; n = track_noise_km2(best track areas)
d >  CHANGE_FACTOR * n -> "Growing";  d < -CHANGE_FACTOR * n -> "Shrinking";  else -> "Stable"
```

- [ ] **Step 1: Write the failing tests**, one for each branch:
  - `test_status_growing`
  - `test_status_shrinking`
  - `test_status_stable_within_noise`
  - `test_status_not_observable_when_hidden` (every point has `observable_share = 0.3`)
  - `test_status_not_enough_looks`
  - `test_status_not_seen_when_latest_excluded`
  - `test_status_never_compares_across_tracks`: a big jump between `156A` and `063D` areas gives `Stable` when each track alone is flat
  - `test_noise_floor`
  - `test_cloud_window_counts_only_valid_points_in_dates`

- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** **Step 4: Run them** (PASS).

- [ ] **Step 5: Commit.** `git commit -m "feat: give each lake a same-track status with noise and a cloud-window look count"`

---

### Task 5: Build lakes.json and per-lake images

**Files:**
- Create: `processing/sartale/lakebuild.py`
- Test: `processing/tests/test_lakebuild.py`
- Modify: `run_pipeline.py` (subcommand `lakes-build`), `.gitignore` (allow `app/public/data/lakes/`)
- Output: `app/public/data/lakes.json`, `app/public/data/lakes/<id>/latest_hh.webp`, `.../water.webp`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `build_lakes(lakes: list[Lake], cache_dir: Path, out_dir: Path, built: str) -> dict`. The returned dict is written to `lakes.json`, version 1, in this shape:

```json
{"version": 1, "built": "2026-11-0xT..Z", "crid": "P05023", "cloud_window": ["2026-06-17", "2026-08-04"],
 "constants": {"drop_db": 4.0, "min_looks": 3, "min_observable": 0.5, "noise_floor_km2": 0.005, "change_factor": 2.0},
 "lakes": [{"id": "passu", "name": "...", "lon": 74.879, "lat": 36.457, "role": "watch",
            "coord_source": "...", "outline_source": null, "area_label": "water area in the search window",
            "downstream": null, "downstream_source": null,
            "status": {"status": "Stable", "track": "156A", "latest_date": "2026-10-23", "looks": 9,
                       "change_km2": 0.001, "noise_km2": 0.005, "reason": "..."},
            "cloud_window_looks": 5, "directions": ["A", "D"], "limits": ["single viewing direction"],
            "series": [{"date": "...", "track": "156A", "area_km2": 0.12, "observable_share": 0.8, "excluded": null}],
            "excluded": [{"pass": "2026-07-07_156A", "reason": "..."}],
            "images": {"latest_hh": "lakes/passu/latest_hh.webp", "water": "lakes/passu/water.webp"},
            "bounds": [lon_min, lat_min, lon_max, lat_max]}]}
```

- [ ] **Step 1: Write the failing tests** using two synthetic cached lakes in `tmp_path`:
  - `test_build_writes_schema_keys`
  - `test_build_json_has_no_nan`: dump with `allow_nan=False`
  - `test_build_labels_point_only_lake_area`: `area_label` equals "water area in the search window" when `outline` is null
  - `test_build_lists_excluded_passes_with_reason`
  - `test_build_images_exist_and_are_small`: each WebP is under 300 kB

- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** Write the WebPs with Pillow:
  - `latest_hh`: grey, using `products.shared_stretch` on the lake's own stack.
  - `water`: RGBA, with water blue `#2b8cff` at alpha 200, shadow-prone hatched grey at alpha 120, and everything else transparent.

  **Step 4: Run them** (PASS). Then run `lakes-build` on the real caches and paste one summary line per lake (status, looks, cloud-window looks) into the report.

- [ ] **Step 5: Attabad sanity check.** Attabad must come out as `Stable` or `Growing`/`Shrinking` within 2×noise, with area above 1 km² and `cloud_window_looks` at least 3. If not, stop and report: the rule is broken.

- [ ] **Step 6: Commit** the code, tests, `lakes.json` and images. `git commit -m "feat: build lakes.json and per-lake radar and water images"`

---

### Task 6: Optical cross-check against Sentinel-2

**Files:**
- Create: `processing/sartale/lakecheck.py`
- Test: `processing/tests/test_lakecheck.py`
- Modify: `run_pipeline.py` (subcommand `lakes-check`), `lakebuild.py` (merge the `checks` block into `lakes.json`)

**Interfaces:**
- Produces:
  - `mndwi_water(green: np.ndarray, swir: np.ndarray, threshold: float = 0.0) -> np.ndarray`
  - `compare_masks(radar: np.ndarray, optical: np.ndarray, pixel_m: float) -> dict` with keys `radar_km2`, `optical_km2`, `area_error_pct`, `iou`
  - `find_clear_scene(bbox, date, days=3, max_cloud=20) -> dict | None`. Searches the Earth Search STAC API at `https://earth-search.aws.element84.com/v1`, collection `sentinel-2-l2a`. No credentials.
  - `lakes.json` gains `checks: [{lake, nisar_date, s2_date, s2_id, radar_km2, optical_km2, area_error_pct, iou}]`.

- [ ] **Step 1: Write the failing tests:** `test_mndwi_water_threshold`, `test_compare_masks_identical_is_iou_1`, `test_compare_masks_half_overlap`, `test_area_error_sign` (radar larger gives a positive error).
- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** Read B03 and B11 windows from the COGs with rasterio, resample B11 to 10 m, and reproject to the NISAR window grid. **Step 4: Run them** (PASS).
- [ ] **Step 5: Real run** for Attabad plus the two other lakes with the most valid looks, each with a NISAR pass within 3 days of a clear scene. Report every result, including bad ones (spec §7.4). If no clear scene exists for a lake, record "no clear Sentinel-2 scene within 3 days".
- [ ] **Step 6: SUPARCO comparison (conditional).** Add one only if the administration supplies SUPARCO lake IDs with locations (`docs/admin-meeting.md`). Then add `suparco_area_km2` and `suparco_date` to the matching check rows, for 16 Jun and 5 Aug. Otherwise skip, and say so in How we know.
- [ ] **Step 7: Commit.** `git commit -m "feat: compare radar lake areas with Sentinel-2 water outlines"`

---

### Task 7: App lake data and types

**Files:**
- Create: `app/src/lakes.ts`, `app/src/lakes.test.ts`
- Modify: `app/src/main.ts` (load `data/lakes.json` next to the manifest), `app/src/fixtures.ts` (add `fixtureLakes`), `app/src/content.ts` (extend `BANNED_CLAIMS`)

**Interfaces:**
- Produces:
  - `type LakeStatusName = "Growing" | "Stable" | "Shrinking" | "Not seen this pass" | "Not observable" | "Not enough NISAR looks yet"`
  - `interface LakesFile` and `interface Lake`, mirroring the JSON in Task 5
  - `loadLakes(url: string): Promise<LakesFile | null>`, which resolves `null` on 404 or a parse error
  - `STATUS_ORDER: LakeStatusName[]` = Growing, Shrinking, Not seen this pass, Stable, Not enough NISAR looks yet, Not observable
  - `sortLakes(lakes: Lake[]): Lake[]`: status order, then newest `latest_date`; controls last
  - `statusSentence(lake: Lake): string`, e.g. "Growing: +0.031 km² since earlier 156A passes (noise ±0.005 km²), 9 looks, latest 23 Oct 2026"

- [ ] **Step 1: Write the failing tests:**
  - `test_loadLakes_returns_null_on_404`
  - `test_loadLakes_returns_null_on_bad_json`
  - `test_sortLakes_puts_growing_first_and_controls_last`
  - `test_statusSentence_includes_date_looks_and_noise`
  - `test_statusSentence_point_only_lake_says_search_window`
  - `test_missing_lakes_file_shows_message`: mount the app with `lakes: null`, open Lake Watch, and expect the text "No lake data in this build"; the Peshawar views still open
- [ ] **Step 2: Run them.** `npm --prefix app test -- --run lakes` (FAIL). **Step 3: Implement.** **Step 4: Run them** (PASS).
- [ ] **Step 5: Commit.** `git commit -m "feat: load lake data in the app with a status order and plain status sentences"`

---

### Task 8: Lake Watch view

**Files:**
- Create: `app/src/lakeWatchView.ts`, `app/src/lakeWatchView.test.ts`, `app/src/lakeLocator.ts`
- Modify: `app/src/app.ts` (new `View` value `"lakes"`, button "Lake Watch" first in the nav, section `data-role="lakes-view"`), `app/src/styles.css`

**Interfaces:**
- Consumes: `Lake`, `sortLakes`, `statusSentence` (Task 7); `ChartFactory` (`sitesView.ts`); `findBannedClaims` (`content.ts`).
- Produces:
  - `createLakeWatchView(root: HTMLElement, opts: { lakes: LakesFile | null; createChart?: ChartFactory; createLocator?: LocatorFactory; onBrief?: (lake: Lake) => void }): { select(id: string): void; destroy(): void }`
  - `type LocatorFactory = (el: HTMLElement, lakes: Lake[], onPick: (id: string) => void) => { highlight(id: string): void; destroy(): void }`

**Layout:**
- The headline line reads: "Between SUPARCO's 16 Jun image and its 5 Aug update, NISAR made {N} valid looks across {k} lakes." Take N and k from the sum of `cloud_window_looks`, and link the line to the SUPARCO quote shown in the story.
- The lake list is sorted, and each row shows status chip, name, statusSentence and coord source.
- The detail panel shows:
  - the two images, stacked with an opacity toggle
  - a chart of area per track, with excluded passes marked
  - the limits
  - the excluded passes and their reasons
  - "Coordinates: {coord_source}"
  - a "Print lake brief" button
- The locator marks each lake's position.

- [ ] **Step 1: Write the failing tests:**
  - `test_lake_list_order_matches_sortLakes`
  - `test_headline_sums_cloud_window_looks`
  - `test_select_shows_coord_source_and_limits`
  - `test_not_observable_lake_has_no_area_number`: for `Not observable`, show the reason, never "0 km²"
  - `test_view_text_has_no_banned_claims`
  - `test_keyboard_select_with_enter`
- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** `lakeLocator.ts` uses MapLibre with the same base style as `maplibreAdapter.ts`, mounted lazily the way `lazyHost.ts` does it. **Step 4: Run them** (PASS) and run the whole app suite.
- [ ] **Step 5: Check by eye.** Run the dev server and take screenshots at desktop width (1440×900) and phone width (390×844) with headless Chrome (see `video/capture.py`). Attach them to the report.
- [ ] **Step 6: Commit.** `git commit -m "feat: add the Lake Watch view with status list, lake detail and locator"`

---

### Task 9: Printable lake brief

**Files:**
- Create: `app/src/lakeBrief.ts`, `app/src/lakeBrief.test.ts`
- Modify: `app/src/styles.css` (an `@media print` block that shows only `.lake-brief`), `app/src/lakeWatchView.ts` (wire `onBrief`)

**Interfaces:**
- Produces:
  - `briefHtml(lake: Lake, file: LakesFile, generatedAt: Date): string`
  - `printBrief(lake, file, win = window): void`, which inserts the brief and calls `win.print()`

**Brief contents, in order:**
1. Lake name and coordinates with their source.
2. Status sentence.
3. Table of the latest 6 valid passes: date, track, area, observable share.
4. Excluded passes with reasons.
5. Limits.
6. Downstream text with its source, or "Downstream exposure: not in this build".
7. The fixed footer: "Indicative screening from provisional NISAR data. Not an official warning; official warnings come from PMD and NDMA. Built {built}."

- [ ] **Step 1: Write the failing tests:**
  - `test_brief_has_footer_and_built_date`
  - `test_brief_lists_excluded_passes`
  - `test_brief_without_downstream_says_not_in_build`
  - `test_brief_has_no_banned_claims`
  - `test_printBrief_calls_print`
- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** **Step 4: Run them** (PASS).
- [ ] **Step 5: Commit.** `git commit -m "feat: print a one-page brief for each lake"`

---

### Task 10: Story order, start screen and How we know

**Files:**
- Modify: `app/src/content/story.json`, `app/src/content/evidence.json`, `app/src/app.ts` (start screen copy and nav grouping), `app/src/appStory.test.ts`, `app/src/evidenceView.ts` (lake tokens)

**What changes:**
- **Story beats, in order (spec §5):**
  1. The cloud gap. Quote SUPARCO verbatim: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes." Cite space4climate.gov.pk, 2 Jul 2026.
  2. How radar sees lakes: dark water, and why shadow is dark from only one side.
  3. Lake Watch.
  4. One lake in depth: the lake with the most valid looks among `role: "watch"`, chosen at build time from `lakes.json`, not hard-coded.
  5. Downstream: Peshawar, as one beat that opens the existing Dance view.
  6. Limits and next steps with the administration.
- **Nav:** Lake Watch, then Story, then a "Downstream: Peshawar" group holding the existing The Dance, Site Stories and What NISAR Missed, then How we know.
- **How we know:** add a Lake method section that fills the constants from `lakes.json` through tokens, plus the Sentinel-2 check results and the not-validated list (frozen lakes, lakes under 0.05 km², wind-roughened water).

- [ ] **Step 1: Update the failing tests first:**
  - `appStory.test.ts`: beat order, the SUPARCO quote present verbatim, beat 4 choosing the watch lake with most looks from fixture data
  - `content.test.ts`: no banned claims in story.json or evidence.json
- [ ] **Step 2: Run them** (FAIL). **Step 3: Implement.** **Step 4: Run the full suite:** `npm --prefix app test -- --run` and `npm --prefix app run build` (both PASS).
- [ ] **Step 5: Check by eye** at desktop and phone widths, as in Task 8. The start screen must state who it is for and what it shows within the first screen.
- [ ] **Step 6: Commit.** `git commit -m "feat: lead with the lake story, keep Peshawar as the downstream chapter"`

---

### Task 11: Docs, meeting log and demo script

**Files:**
- Create: `docs/admin-meeting.md`, `docs/demo-script.md`
- Modify: `README.md`, `docs/DATA_SOURCES.md`, `docs/SI_USE.md`

**What each file contains:**
- `admin-meeting.md`: the 7 questions from spec §6, plus a table with columns Date, Office, Person (with permission to name), Question, Verbatim answer, Can we quote (y/n). Rule at the top: "The app and pitch may cite only what is written here."
- `demo-script.md`:
  - A 30-second script, app-first: 0–5 s the cloud gap quote; 5–20 s Lake Watch, the headline count and one lake; 20–30 s the brief, then "built on NISAR, open source".
  - A deck outline of no more than 7 slides: problem, user, why NISAR, the two-view rule, Lake Watch, validation and limits, ask.
- `DATA_SOURCES.md`: add NISAR GCOV via HTTPS range reads, HMAGLOFDB, the Shrestha et al. 2023 inventory, the Shisper polygons (if used), SUPARCO space4climate, Sentinel-2 L2A via Earth Search, and Radio Pakistan. Give each its licence or terms.
- `SI_USE.md`: add Codex (research and review), ElevenLabs (narration), and Claude (code and docs).
- `README.md`: lead with the Lake Watch pitch line from spec §1, then how to run the pipeline subcommands.

- [ ] **Step 1: Write the files.** **Step 2:** run `npm --prefix app test -- --run content` so the banned-claim check also covers the README. If the README is not covered yet, extend `content.test.ts` to read `../README.md`.
- [ ] **Step 3: Commit.** `git commit -m "docs: add the admin meeting log, the 30-second demo script and the new data sources"`

---

### Task 12: Whole-branch check

- [ ] **Step 1:** `conda run -n sartale python -m pytest processing -q` and `npm --prefix app test -- --run` and `npm --prefix app run build`. All pass.
- [ ] **Step 2:** In a fresh browser profile, open the built app from `npm --prefix app run preview`. Click every view, print one brief to PDF, and confirm there are no console errors. Attach the screenshots and the PDF to the report.
- [ ] **Step 3:** Hand over to the final whole-branch review (subagent-driven-development).
