# SARtale Hackathon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status note:** on 1 Nov 2026 the team chose to start building before the event and accepted the eligibility risk. Disclose this as the rules require. Real-data steps still wait for Earthdata credentials.

**Execution method (chosen by the team):** Subagent-driven, using superpowers:subagent-driven-development, from Task 1 once the event starts.

**Goal:** Build and submit a public web app that shows one monsoon season in the Peshawar Valley through NISAR HH/HV radar, with honest evidence labels, by team SARcastic Scientists.

**Architecture:** A Python pipeline turns NISAR GCOV files into Cloud Optimized GeoTIFFs, WebP map overlays and JSON. A static TypeScript and MapLibre app loads those files, so no server is needed. Every number on screen traces back to a manifest of granule IDs.

**Tech Stack:** Python 3.12 (conda-forge), h5py, numpy, rasterio, GDAL, pytest, networkx, osmnx; Vite, TypeScript, MapLibre GL JS, uPlot, Vitest.

**Spec:** [docs/SARtale-hackathon-plan.md](../../SARtale-hackathon-plan.md)

## Global Constraints

- Team: 2 people on team SARcastic Scientists, Islamabad Local Event, virtual and in-person, `Asia/Karachi`.
- Hacking starts 11:00 PKT Sat 14 Nov. **Pitch materials due 17:00 PKT Sun 15 Nov**, live pitch 18:30 PKT, **global portal submission by 23:59 PKT Sun 15 Nov**.
- Primary stack: `084_A_019`, mode `4005`, polarization `DHDH`, source `A`, full frame only, Frequency A, 10 m pixels.
- Data version: one CRID only, `P05023` unless Task 2 finds another. Never mix CRIDs, tracks, modes or BETA data in one series.
- Permanent gap: `2026-07-27T22:03:25Z` to `2026-08-10T00:55:27Z`.
- Study box: 71.4-72.1°E, 33.9-34.4°N.
- Order of operations: mask, then average in **linear power**, then convert to dB.
- Every NISAR layer shows "Provisional". Every claim shows date, source and evidence type.
- Banned claims in app copy: "detected flood", "flood detected", "damage", "damaged", "isolated", "risk score", "early warning".
- Licence: Apache-2.0. List every non-NASA dataset and library with its licence.
- Keep `docs/SI_USE.md` updated throughout; the submission must describe all SI tool use.
- Keep raw and working data on `I:\SARtale\data\`, which is git-ignored. `C:` has only 43 GB free.

## Review Focus

1. **A site has no valid pixels on one date.** The curve shows a gap, and the JSON holds `null`, never `NaN`. Test: `test_sample_site_all_masked_returns_none` in Task 5, plus `test_series_gap_stays_null` in Task 8.
2. **A newer CRID or date appears mid-event.** The pipeline fails loudly rather than mixing versions. Test: `test_select_stack_rejects_mixed_crid` in Task 2.
3. **A date file differs in grid or is a partial frame.** The stack refuses it. Tests: `test_assert_same_grid_rejects_shift` in Task 4 and `test_select_stack_excludes_partial_frame` in Task 2.
4. **A judge opens the site on a phone or a slow link, or an overlay fails to load.** The app shows a message and still works. Test: `test_missing_overlay_reports_error` in Task 7.
5. **Someone selects a date inside the data gap.** The app says "no observation", never "no change". Test: `test_gap_is_labelled_no_observation` in Task 9.

---

## File Structure

```text
SARtale/
  LICENSE, README.md, .gitignore, environment.yml
  docs/SI_USE.md, docs/DATA_SOURCES.md
  processing/
    sartale/
      config.py        constants from Global Constraints
      catalog.py       parse names, search CMR, select stack, write manifest
      radiometry.py    masking, linear averaging, dB, log-ratio
      gcov.py          read HDF5 layers into a Layer object
      products.py      grid checks, stretch, composite, COG and WebP output
      sites.py         site curves and stable-control report
      references.py    OPERA and HLS comparisons
      network.py       road closure analysis (Tier 2)
      run_pipeline.py  command-line entry point
    tests/
  app/
    index.html, package.json, vite.config.ts
    src/main.ts, map.ts, timeline.ts, sites.ts, gap.ts, lifelines.ts, types.ts, content.ts
    src/content/story.json, sites.json
    public/data/       manifest.json, frames/*.webp, sites.json, overlays/*.geojson
  data/                git-ignored
```

### Data contract between pipeline and app

`app/public/data/manifest.json`, defined in `app/src/types.ts` and written by `run_pipeline.py`:

```json
{
  "stack": "084_A_019",
  "crid": "P05023",
  "maturity": "Provisional",
  "bounds": [71.4, 33.9, 72.1, 34.4],
  "dates": [
    {
      "date": "2026-07-02",
      "granule": "<full granule ID>",
      "frames": { "HH": "frames/2026-07-02_HH.webp", "HV": "frames/2026-07-02_HV.webp" }
    }
  ],
  "composite": "frames/composite_HH.webp",
  "stretch_db": { "HH": [-22.0, -4.0], "HV": [-30.0, -10.0] },
  "gap": { "start": "2026-07-27T22:03:25Z", "end": "2026-08-10T00:55:27Z" }
}
```

The stretch values above are examples only. The pipeline computes the real ones.

`app/public/data/sites.json` is a list of:

```json
{
  "id": "stable-urban",
  "name": "Example site",
  "lon": 71.56,
  "lat": 34.01,
  "role": "stable-control",
  "series": [{ "date": "2026-07-02", "hh_db": -7.1, "hv_db": null, "valid_fraction": 0.0 }]
}
```

### Who does what, and when

Assign Person A (data and science) and Person B (app and story) in Task 0. Times are Pakistan time (PKT).

| PKT | Person A: data and science | Person B: app and story | Gate |
|---|---|---|---|
| Fri 13 Nov | Read challenge resources | Read submission and judging guides | Changes noted |
| Sat 09:00-11:00 | Check-in, opening, mentor briefing | Same | Mentors know the project |
| Sat 11:00-13:30 | Rerun catalogue search; start downloads | Check real manifest in the app; open project page | **Gate 1:** data is downloading |
| Sat 13:30-18:30 | Read one file; fix reader if the layout differs; inspect pixels | Replace demo data as frames arrive | **Gate 2:** first real NISAR image on the map |
| Sat 18:30-Sun 00:00 | Four dates, overlays, composite, three sites | Site cards from real curves | **Gate 3:** four-date series in the app |
| Sun 00:00-09:00 | Stable control, OPERA and HLS checks; sleep in turns | Real copy; sleep in turns | **Gate 4:** Tier 1 works end to end |
| Sun 09:15-13:00 | Tier 2 only if Tier 1 is solid | Pitch deck; demo recording | **Gate 5:** features stop at 13:00 |
| Sun 13:00-16:00 | Clean rerun; recheck numbers | Pitch rehearsal; offline and phone test | Freeze |
| Sun 16:00 | Submit pitch deck and materials | Same | About 1 hour early |
| Sun 18:30-19:30 | Live pitch to local judges | Same | |
| Sun 21:30 | Final portal submission | Same | **Well before 23:59 PKT** |

---

### Task 0: Pre-event checklist (no project code)

**Files:**
- None in the repo.

- [ ] **Step 1: Confirm both members are fully registered**

Check that both people are registered for the Islamabad event itself, not waitlisted. The team page moving to Islamabad does not prove this for each person. Expected: both see Islamabad as their confirmed event.

- [ ] **Step 2: Contact the Islamabad Local Lead**

The Local Lead is Abdullah Zafar; the contact route is on the event page. Send your own short message asking three things, and keep the reply:

1. "Will we attend in person or virtually, and what do we need to do for either?"
2. "Our team moved from Seoul to Islamabad. Are we correctly registered?"
3. "We started work before 14 Nov. What must we disclose, and does it affect eligibility?"

- [ ] **Step 3: Assign Person A and Person B, and update the team page**

The team page currently says "interactive map or early-warning tool". Change "early-warning tool" so it does not conflict with the plan's rule that SARtale is not a warning service.

- [ ] **Step 4: Decide whether to recruit**

The team page is open to new members and the limit is 6. A third person who can handle design or story would help most. Do not wait on this.

- [ ] **Step 5: Set up general tools**

Create Earthdata Login accounts, accept the ASF terms, and test sign-in. Install Miniforge, Node 22 or later, and Git. Measure the download speed of the machine that will hold the data.

- [ ] **Step 6: Read the releases**

On 13 Nov read the challenge Resources tab, the Project Submission Guide and the Judging and Awards Guide. Note any changes, and apply them when the event starts.

---

### Task 1: Project setup and radiometry core

**Files:**
- Create: `.gitignore`, `LICENSE`, `environment.yml`, `docs/SI_USE.md`, `processing/sartale/config.py`, `processing/sartale/radiometry.py`
- Test: `processing/tests/test_radiometry.py`

**Interfaces:**
- Produces: `mask_power(power: np.ndarray, fill: float | None = None) -> np.ndarray`, `multilook_linear(power: np.ndarray, factor: int, min_valid: float = 0.5) -> np.ndarray`, `to_db(power: np.ndarray) -> np.ndarray`, `log_ratio_db(later: np.ndarray, earlier: np.ndarray) -> np.ndarray`, and constants in `config.py`: `STACK_ID`, `MODE`, `POLE`, `BBOX`, `GAP_START`, `GAP_END`, `POLS = ("HHHH", "HVHV")`.

- [ ] **Step 1: Run `git init`, create the environment and the config**

`environment.yml` uses conda-forge: python=3.12, numpy, h5py, rasterio, gdal, pyproj, pillow, pytest, requests, networkx, osmnx. Git-ignore `data/` and `app/public/data/raw/`. Copy the Global Constraints values into `config.py`.

- [ ] **Step 2: Write the failing tests**

```python
def test_mask_power_removes_invalid():
    out = mask_power(np.array([1.0, 0.0, -1.0, np.nan, np.inf, 9.0]), fill=9.0)
    assert out[0] == 1.0 and np.isnan(out[1:]).all()

def test_multilook_averages_linear_power_not_db():
    out = multilook_linear(np.array([[1.0, 100.0], [1.0, 100.0]]), factor=2)
    assert out.shape == (1, 1)
    assert to_db(out)[0, 0] == pytest.approx(17.03, abs=0.01)  # dB averaging would give 10.0

def test_multilook_blanks_cell_below_min_valid():
    a = np.array([[1.0, np.nan], [np.nan, np.nan]])
    assert np.isnan(multilook_linear(a, factor=2, min_valid=0.5)[0, 0])

def test_multilook_trims_partial_edge_cells():
    assert multilook_linear(np.ones((5, 7)), factor=2).shape == (2, 3)

def test_log_ratio_is_10_db_for_tenfold_power():
    assert log_ratio_db(np.array([10.0]), np.array([1.0]))[0] == pytest.approx(10.0)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest processing/tests/test_radiometry.py -v`
Expected: FAIL with an import error.

- [ ] **Step 4: Implement the four functions in `radiometry.py`**

`multilook_linear` uses `np.nanmean` over non-overlapping blocks, trims edges that do not fill a block, and returns NaN where the valid fraction is below `min_valid`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest processing/tests/test_radiometry.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: add project setup and radiometry core"
```

### Task 2: Catalogue search and manifest

**Files:**
- Create: `processing/sartale/catalog.py`, `processing/sartale/run_pipeline.py`
- Test: `processing/tests/test_catalog.py`

**Interfaces:**
- Consumes: constants from `config.py`.
- Produces: `parse_granule(name: str) -> Granule` (dataclass with `cycle: int, track: int, direction: str, frame: int, mode: str, pole: str, source: str, start: datetime, crid: str, accuracy: str, coverage: str, name: str`), `search_cmr() -> list[Granule]`, `select_stack(granules: list[Granule], stack_id: str, mode: str, pole: str) -> list[Granule]`, `write_manifest(granules: list[Granule], path: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
NAME = "NISAR_L2_PR_GCOV_023_063_D_071_2005_QPDH_A_20260618T135450_20260618T135525_P05023_N_F_J_001"

def test_parse_granule_reads_all_fields():
    g = parse_granule(NAME)
    assert (g.cycle, g.track, g.direction, g.frame) == (23, 63, "D", 71)
    assert (g.mode, g.pole, g.source, g.crid) == ("2005", "QPDH", "A", "P05023")
    assert (g.accuracy, g.coverage) == ("N", "F")

def test_select_stack_keeps_only_requested_stack(sample): ...
    # Assert: only track 84, direction A, frame 19, mode 4005, pole DHDH remain, sorted by date

def test_select_stack_excludes_partial_frame(sample): ...
    # Assert: a granule with coverage "P" is dropped

def test_select_stack_rejects_mixed_crid(sample):
    with pytest.raises(ValueError, match="CRID"):
        select_stack(mixed, "084_A_019", "4005", "DHDH")

def test_select_stack_excludes_dates_in_gap(sample): ...
    # Assert: a granule dated 2026-08-01 is dropped
```

Build `sample` from valid names by changing fields in `NAME`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest processing/tests/test_catalog.py -v`
Expected: FAIL with an import error.

- [ ] **Step 3: Implement `catalog.py`**

`search_cmr` calls `https://cmr.earthdata.nasa.gov/search/granules.umm_json` with `short_name=NISAR_L2_GCOV_PROVISIONAL_V1`, the study bounding box, and `page_size=200`. Add a `search --out <path>` command to `run_pipeline.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest processing/tests/test_catalog.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the live search and save the manifest**

Run: `python -m sartale.run_pipeline search --out data/manifest_h0.json`
Expected: at least the 9 dates in the spec, all `P05023`. If the CRID differs, stop and update `config.py` deliberately.

- [ ] **Step 6: Pick four Tier 1 dates and start downloads**

Default: 2 Jul, 19 Aug, 12 Sep, 18 Oct. Avoid accuracy `F` granules (14 Jul) in Tier 1, because `F` means forecast orbit data. Each file is about 7.3 GB. Try Harmony extraction of `HHHH` and `HVHV` first; if it fails within 20 minutes, download whole files to `I:\SARtale\data\gcov\`.

- [ ] **Step 7: Commit**

```bash
git add processing
git commit -m "feat: add catalogue search and stack selection"
```

### Task 3: GCOV reader

**Files:**
- Create: `processing/sartale/gcov.py`
- Test: `processing/tests/test_gcov.py`

**Interfaces:**
- Consumes: `mask_power` from Task 1.
- Produces: `Layer` dataclass (`power: np.ndarray, x: np.ndarray, y: np.ndarray, epsg: int, looks: np.ndarray | None, mask: np.ndarray | None`), `read_layer(path: Path, term: str, bbox_lonlat: tuple[float, float, float, float]) -> Layer`.

- [ ] **Step 1: Inspect one real file before writing code**

Run: `python -c "import h5py,sys; h5py.File(sys.argv[1]).visit(print)" data/gcov/<file>.h5`
Expected: `science/LSAR/GCOV/grids/frequencyA/HHHH`, `HVHV`, `numberOfLooks` and `mask` exist. Note the names of the coordinate and projection datasets. If they differ from the test fixture, change the fixture to match the real file.

- [ ] **Step 2: Write the failing tests**

Use a `tmp_path` fixture that creates a small HDF5 file with the same structure as the real one.

```python
def test_read_layer_clips_to_bbox(gcov_file):
    layer = read_layer(gcov_file, "HHHH", BBOX_INSIDE_FIXTURE)
    assert layer.power.shape == EXPECTED_SHAPE

def test_read_layer_masks_invalid_values(gcov_file):
    assert np.isnan(read_layer(gcov_file, "HHHH", FULL_BBOX).power[0, 0])

def test_read_layer_keeps_epsg(gcov_file):
    assert read_layer(gcov_file, "HVHV", FULL_BBOX).epsg == 32642

def test_read_layer_rejects_missing_term(gcov_file):
    with pytest.raises(KeyError, match="VVVV"):
        read_layer(gcov_file, "VVVV", FULL_BBOX)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest processing/tests/test_gcov.py -v`
Expected: FAIL with an import error.

- [ ] **Step 4: Implement `read_layer`**

Convert the bounding box to the file's UTM zone with pyproj. Read only the needed slice through h5py. Apply `mask_power` to the data, then keep `looks` and `mask` as returned layers.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest processing/tests/test_gcov.py -v`
Expected: 4 passed.

- [ ] **Step 6: Check one real date by eye**

Render one HH date to PNG. Expected: rivers dark, city bright, no obvious interference stripes. Overlay the OSM river line. If there is a visible offset, record it in `docs/DATA_SOURCES.md`.

- [ ] **Step 7: Commit**

```bash
git add processing
git commit -m "feat: read GCOV layers for the study area"
```

### Task 4: Stack products

**Files:**
- Create: `processing/sartale/products.py`
- Modify: `processing/sartale/run_pipeline.py`
- Test: `processing/tests/test_products.py`

**Interfaces:**
- Consumes: `Layer` from Task 3; `multilook_linear`, `to_db` from Task 1.
- Produces: `assert_same_grid(layers: list[Layer]) -> None`, `shared_stretch(stack_db: np.ndarray, low: float = 2, high: float = 98) -> tuple[float, float]`, `render_frame(db: np.ndarray, stretch: tuple[float, float]) -> np.ndarray` (uint8), `seasonal_composite(early: np.ndarray, mid: np.ndarray, late: np.ndarray, stretch: tuple[float, float]) -> np.ndarray` (uint8 RGBA), `write_cog(array, layer, path) -> None`, `write_webp_3857(array, layer, path) -> tuple[float, float, float, float]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_assert_same_grid_rejects_shift(layer):
    with pytest.raises(ValueError, match="grid"):
        assert_same_grid([layer, shifted(layer, dx=10)])

def test_stretch_is_shared_across_dates():
    lo, hi = shared_stretch(np.array([[[-30.0, -20.0]], [[-10.0, 0.0]]]))
    assert lo < -20 and hi > -10

def test_composite_of_identical_dates_is_grey():
    db = np.array([[-20.0, -10.0]])
    rgba = seasonal_composite(db, db, db, (-30.0, 0.0))
    assert (rgba[..., 0] == rgba[..., 1]).all() and (rgba[..., 1] == rgba[..., 2]).all()

def test_nan_pixels_are_transparent():
    rgba = seasonal_composite(*[np.array([[np.nan]])] * 3, (-30.0, 0.0))
    assert rgba[0, 0, 3] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest processing/tests/test_products.py -v`
Expected: FAIL with an import error.

- [ ] **Step 3: Implement `products.py`**

Multilook 10 m data by a factor of 3 to 30 m. `write_webp_3857` warps to EPSG:3857 with rasterio, because MapLibre image layers stretch linearly in Web Mercator, and returns the corner bounds. Use one stretch per polarization across all dates.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest processing/tests/test_products.py -v`
Expected: 4 passed.

- [ ] **Step 5: Add the `build` command and run it**

Run: `python -m sartale.run_pipeline build --dates 2026-07-02,2026-08-19,2026-09-12,2026-10-18`
Expected: `app/public/data/manifest.json`, one WebP per date and polarization, one composite, and COGs in `data/cog/`. Each WebP is under about 3 MB.

- [ ] **Step 6: Commit**

```bash
git add processing app/public/data/manifest.json
git commit -m "feat: build time-series overlays and manifest"
```

### Task 5: Site curves and stable control

**Files:**
- Create: `processing/sartale/sites.py`
- Modify: `processing/sartale/run_pipeline.py`
- Test: `processing/tests/test_sites.py`

**Interfaces:**
- Consumes: stacked layers from Task 4.
- Produces: `sample_site(power_stack: np.ndarray, layer: Layer, lon: float, lat: float, radius_m: float = 150) -> list[float | None]`, `stability_report(series_db: list[float | None]) -> dict` with keys `spread_db`, `n_valid`.

- [ ] **Step 1: Write the failing tests**

```python
def test_sample_site_averages_in_linear_power(stack, layer):
    assert sample_site(stack, layer, LON, LAT)[0] == pytest.approx(17.03, abs=0.01)

def test_sample_site_all_masked_returns_none(masked_stack, layer):
    assert sample_site(masked_stack, layer, LON, LAT)[0] is None

def test_sample_site_outside_grid_raises(stack, layer):
    with pytest.raises(ValueError, match="outside"):
        sample_site(stack, layer, 0.0, 0.0)

def test_sites_json_has_no_nan(tmp_path):
    text = write_sites(SITES_WITH_NONE, tmp_path / "sites.json").read_text()
    assert "NaN" not in text and json.loads(text)[0]["series"][0]["hh_db"] is None

def test_stability_report_ignores_gaps():
    assert stability_report([-8.0, None, -6.0]) == {"spread_db": 2.0, "n_valid": 2}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest processing/tests/test_sites.py -v`
Expected: FAIL with an import error.

- [ ] **Step 3: Implement `sites.py`**

Average linear power within the radius, then convert to dB. Add `write_sites(sites, path)`, which writes JSON with `allow_nan=False`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest processing/tests/test_sites.py -v`
Expected: 5 passed.

- [ ] **Step 5: Pick and sample three sites plus one stable control**

Choose from the real composite: one river stretch, one farmland area, and one more that shows clear change. The control is a bright stable urban area. Run: `python -m sartale.run_pipeline sites`.

Expected: `app/public/data/sites.json`, with the control's `spread_db` written into `docs/DATA_SOURCES.md`. If the control swings widely on one date, inspect that date before interpreting anything.

- [ ] **Step 6: Commit**

```bash
git add processing app/public/data/sites.json docs/DATA_SOURCES.md
git commit -m "feat: sample site curves and stable control"
```

### Task 6: Same-season reference checks

**Files:**
- Create: `processing/sartale/references.py`
- Test: `processing/tests/test_references.py`

**Interfaces:**
- Consumes: `Layer` from Task 3.
- Produces: `nearest_date(target: date, candidates: list[date]) -> tuple[date, int]`, `water_agreement(radar_low: np.ndarray, dswx: np.ndarray, water_values: set[int], invalid_values: set[int]) -> dict` with keys `agreement`, `n_compared`.

- [ ] **Step 1: Write the failing tests**

```python
def test_nearest_date_reports_day_gap():
    assert nearest_date(date(2026, 7, 2), [date(2026, 6, 28), date(2026, 7, 3)]) == (date(2026, 7, 3), 1)

def test_water_agreement_skips_invalid_classes():
    radar = np.array([True, True, False, True])
    dswx = np.array([1, 0, 0, 255])
    out = water_agreement(radar, dswx, water_values={1}, invalid_values={255})
    assert out == {"agreement": pytest.approx(2 / 3), "n_compared": 3}

def test_water_agreement_with_nothing_comparable_returns_none():
    out = water_agreement(np.array([True]), np.array([255]), {1}, {255})
    assert out == {"agreement": None, "n_compared": 0}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest processing/tests/test_references.py -v`
Expected: FAIL with an import error.

- [ ] **Step 3: Implement `references.py`**

Take class values from the OPERA DSWx product documentation and put them in `config.py`. Do not hard-code them from memory.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest processing/tests/test_references.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the checks at the Tier 1 sites**

Download DSWx-S1 for the nearest date to each Tier 1 date, and an HLS vegetation value where cloud-free. Write results, including the day difference, into `docs/DATA_SOURCES.md`. Report numbers without a pass mark.

- [ ] **Step 6: Commit**

```bash
git add processing docs/DATA_SOURCES.md
git commit -m "feat: compare radar with same-season references"
```

### Task 7: App shell and The Dance

**Files:**
- Create: `app/` Vite project; `app/src/types.ts`, `map.ts`, `timeline.ts`, `main.ts`
- Test: `app/src/timeline.test.ts`, `app/src/map.test.ts`

**Interfaces:**
- Consumes: `manifest.json` contract.
- Produces: `Manifest` and `Site` types; `loadManifest(url: string): Promise<Manifest>`, `frameUrl(m: Manifest, date: string, pol: "HH" | "HV"): string`, `orderedDates(m: Manifest): string[]`, `setFrame(map, m, date, pol): Promise<void>`.

- [ ] **Step 1: Scaffold and write the failing tests**

Scaffold with `npm create vite@latest app -- --template vanilla-ts`, then install `maplibre-gl`, `uplot` and `vitest`. Use the `frontend-design` skill for visual direction at this step. Vite's `base` must be `./` so the build also works from a subfolder.

```ts
test("frameUrl returns the file for a date and polarization", () => {
  expect(frameUrl(m, "2026-07-02", "HV")).toBe("data/frames/2026-07-02_HV.webp");
});
test("orderedDates sorts oldest first", () => {
  expect(orderedDates(unsorted)[0]).toBe("2026-07-02");
});
test("test_missing_overlay_reports_error", async () => {
  await expect(setFrame(mapThatFailsToLoad, m, "2026-07-02", "HH")).rejects.toThrow("overlay");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix app test -- --run`
Expected: FAIL because the functions are missing.

- [ ] **Step 3: Implement the map view**

Use an empty MapLibre style with one image source for the current frame, plus local GeoJSON for rivers, main roads and place labels, so there is no outside tile dependency. Add a date slider, play button, HH/HV toggle, before/after swipe and a composite toggle. Show a visible message if `setFrame` rejects. Show a "Provisional NISAR data" label on the map at all times.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix app test -- --run`
Expected: all pass.

- [ ] **Step 5: Check in the browser, including a narrow phone width**

Run: `npm --prefix app run dev`
Expected: the date slider changes the real radar image in under a second, and the layout is usable at 390 px wide.

- [ ] **Step 6: Commit**

```bash
git add app
git commit -m "feat: add map view with date and polarization controls"
```

### Task 8: Site Stories and copy rules

**Files:**
- Create: `app/src/sites.ts`, `app/src/content.ts`, `app/src/content/story.json`, `app/src/content/sites.json`
- Test: `app/src/sites.test.ts`, `app/src/content.test.ts`

**Interfaces:**
- Consumes: `Manifest`, `Site` from Task 7.
- Produces: `toChartSeries(site: Site): { x: number[]; hh: (number | null)[]; hv: (number | null)[] }`, `findBannedClaims(text: string): string[]`.

- [ ] **Step 1: Write the failing tests**

```ts
test("test_series_gap_stays_null", () => {
  expect(toChartSeries(siteWithGap).hv[1]).toBeNull();
});
test("findBannedClaims catches banned wording in any case", () => {
  expect(findBannedClaims("Flood Detected near the bridge")).toEqual(["flood detected"]);
});
test("all app copy is free of banned claims", () => {
  expect(findBannedClaims(JSON.stringify([story, sites]))).toEqual([]);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix app test -- --run`
Expected: FAIL because the functions are missing.

- [ ] **Step 3: Implement the site cards**

Each card has an HH/HV uPlot chart that keeps gaps visible, the dates, a one-line observation, one stated hypothesis using "may indicate", what would test it, a limits line, and an evidence badge: Observed, Reference agrees, Hypothesis, or Not observed. Write the copy only after seeing the real curves.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix app test -- --run`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app
git commit -m "feat: add site stories with evidence labels"
```

### Task 9: What NISAR Missed

**Files:**
- Create: `app/src/gap.ts`
- Test: `app/src/gap.test.ts`

**Interfaces:**
- Consumes: `Manifest` from Task 7.
- Produces: `coverageSegments(m: Manifest, from: string, to: string): Segment[]` where `Segment = { date: string; state: "observed" | "no-observation" }`, `stateLabel(state: Segment["state"]): string`.

- [ ] **Step 1: Write the failing tests**

```ts
test("test_gap_is_labelled_no_observation", () => {
  expect(stateLabel("no-observation")).toBe("No observation");
});
test("a date inside the gap is not observed", () => {
  const s = coverageSegments(m, "2026-08-01", "2026-08-01");
  expect(s[0].state).toBe("no-observation");
});
test("an acquisition date is observed", () => {
  expect(coverageSegments(m, "2026-07-26", "2026-07-26")[0].state).toBe("observed");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --prefix app test -- --run`
Expected: FAIL because the functions are missing.

- [ ] **Step 3: Implement the timeline and text**

Show all nine track 84 dates, even if only four are loaded, and the gap. Before writing the flood text, check PDMA reports and FFD bulletins for event timing. State only what the check supports.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm --prefix app test -- --run`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app
git commit -m "feat: show what NISAR did not observe"
```

### Task 10: Tier 1 submission package

**Files:**
- Create: `README.md`, `docs/DATA_SOURCES.md` (complete it), `docs/SI_USE.md` (complete it)
- Modify: `app/src/content/story.json`

- [ ] **Step 1: Finish the six-beat story and judging check**

Check the app against the criteria below, which the Seoul site listed. Confirm them in NASA's 13 Nov Judging Guide:

| Criterion | Evidence in the project |
|---|---|
| Impact | The decision or check a local planner could make |
| Creativity | Radar season as a "dance", the composite, "what NISAR missed" |
| Validity | Stable control, same-season checks, stated limits |
| Relevance | Uses NISAR, surface change, polarizations, physical drivers |
| Presentation | A clear story and a working demo |

- [ ] **Step 2: Write the documentation**

`README.md`: what it does, how to run it, how to reproduce it. `DATA_SOURCES.md`: granule IDs, every dataset, licence, and access date. `SI_USE.md`: every tool used and what for.

- [ ] **Step 3: Build and test offline**

Run: `npm --prefix app run build`, then `npx vite preview` from `app/`.
Expected: the whole story works with the network turned off.

- [ ] **Step 4: Deploy from your own account and test the public URL**

Create the public repo and deploy the built app, for example to GitHub Pages. Expected: the site opens in a private browser window on a phone and on a laptop.

- [ ] **Step 5: Save a safe draft on the project page**

Enter the title, description, repo and app link so a Tier 1 submission is possible at any time.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "docs: complete Tier 1 submission package"
```

### Task 11: Tier 2 additions (only if Tier 1 is solid by Sun 05:00)

**Files:**
- Create: `processing/sartale/network.py`, `app/src/lifelines.ts`
- Test: `processing/tests/test_network.py`

**Interfaces:**
- Produces: `closure_impact(graph: nx.MultiDiGraph, closed_edges: list[tuple], origins: list[int], destinations: list[int]) -> list[dict]` with each dict holding `origin`, `status`, `baseline_km`, `scenario_km`.

- [ ] **Step 1: Add the remaining dates**

Add 26 Jul, then the others. Exclude any that fail a visual check. Rerun `build` and `sites`. Expected: tests stay green and the control's spread is updated. Do this before Lifelines.

- [ ] **Step 2: Write the failing network tests**

```python
def test_closure_with_alternative_is_longer(toy_graph):
    assert closure_impact(toy_graph, [BRIDGE], [A], [H])[0]["status"] == "longer"

def test_closure_without_alternative_is_scenario_disconnected(toy_graph):
    assert closure_impact(toy_graph, [BOTH_ROADS], [A], [H])[0]["status"] == "scenario-disconnected"

def test_no_closure_is_unchanged(toy_graph):
    r = closure_impact(toy_graph, [], [A], [H])[0]
    assert r["status"] == "unchanged" and r["scenario_km"] == r["baseline_km"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest processing/tests/test_network.py -v`
Expected: FAIL with an import error.

- [ ] **Step 4: Implement `closure_impact`**

Use `networkx.shortest_path_length` with edge length. Copy the graph; do not change the original.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest processing/tests/test_network.py -v`
Expected: 3 passed.

- [ ] **Step 6: Add one evidence-linked scenario**

Pick a crossing next to a river stretch where NISAR shows change. Check one route by hand against the map. If no link to the NISAR findings exists, skip Lifelines and say nothing about it.

- [ ] **Step 7: Commit**

```bash
git add processing app
git commit -m "feat: add evidence-linked road closure scenario"
```

### Task 12: Final submission

**Files:**
- Modify: `README.md`, `docs/SI_USE.md`

- [ ] **Step 1: Freeze and rerun from clean**

Delete generated outputs, then run the pipeline from the manifest. Expected: the same dates, and matching numbers in `sites.json`.

- [ ] **Step 2: Run all tests**

Run: `pytest processing/tests -v` and `npm --prefix app test -- --run`
Expected: all pass.

- [ ] **Step 3: Recheck the official list**

Go through the 13 Nov Project Submission Guide item by item. Check the demo format, licence, data list, SI statement, no personal data, and a "not an official warning service" statement.

- [ ] **Step 4: Submit pitch materials by 16:00 PKT, then the global portal by 21:30 PKT**

Local pitch materials are due at 17:00 and the portal closes at 23:59. Expected: the project page shows the project as submitted. Take a screenshot.

- [ ] **Step 5: Commit and tag**

```bash
git add .
git commit -m "chore: final submission"
git tag submission
git push --tags
```
