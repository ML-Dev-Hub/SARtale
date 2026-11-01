<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale Pakistan logo" width="220" />
</p>

# SARtale

**An interactive story of one monsoon season, told through NISAR radar.** Built for the NASA Space Apps Challenge 2026, "Dancing with the SARs". Team **SARcastic Scientists** (Saeed Ahmad, Shaharyar Sajid), Islamabad Local Event.

The study area is the Peshawar Valley, Pakistan. The app steps through nine real NISAR browse previews from 2 July to 18 October 2026, compares HH and HV polarizations, shows a seasonal colour composite, and shows what NISAR did not observe. Site curves are not in the build yet, because they need calibrated data, and the first calibrated run has not been done.

## Read this first

- **The app now shows real NISAR images, but only low-resolution previews.** They are NASA's public browse PNGs for nine dates of track 84 (listed in `docs/DATA_SOURCES.md`). Their pixel values are **scaled for display and are not calibrated**. The app never presents them as decibels or backscatter measurements, and no curve, statistic or finding is taken from them. Each preview pixel covers about 174 m. The map banner reads "REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED".
- **Two dates carry a visible caution.** 2 July: "Possible radio interference over the western area (unconfirmed). Do not read this as surface change." 14 July: "Forecast-orbit product; positions may be less precise."
- **Placement is from the published footprint.** The previews are on a plain longitude and latitude grid, placed using the scene footprint from NASA's catalogue. Checked against the footprint corners and two landmarks (Tarbela reservoir, Peshawar), the placement agrees to within about 2 km. No other check was possible.
- **There are no calibrated results and no site curves.** Calibrated GCOV files need an Earthdata login. The login now works and the nine calibrated files are being downloaded (five verified so far), but the calibrated build has not been run. Nothing in this repository claims a finding about the ground. Site Stories says "No site curves yet", and shows only curves stamped with the stack and processing version of the manifest next to them.
- **The processing code has not read a real P05023 file.** The GCOV reader (`processing/sartale/gcov.py`) and the multilook step were run on two public single-pol NISAR sample GCOV files dated 2008 (older product versions over a different area), only to test the reader. They have no HV term, and their mask holds only 0 and 255, so they cannot confirm what the mask means on a real file. HV and the real `P05023` files are unread until the first real run. The unit tests in `processing/tests/` use small made-up files.
- **The synthetic demo is a test fixture only.** It lives in `app/demo-data/`, outside the folder the app serves, so it cannot ship. See "Run the pipeline locally".
- **This is not an official warning service.** It does not issue flood warnings or forecasts. For warnings, use the Pakistan Meteorological Department (PMD), NDMA and PDMA.
- **NISAR data is Provisional.** The provisional NISAR products are not yet validated, and NASA expects to reprocess them. If calibrated data is loaded later, the app labels it "Provisional NISAR data".

## What it does

| View | What it shows |
|---|---|
| The Dance | NASA browse previews by date on a map, a date slider and play button, HH or HV polarization, a before and after swipe, and a seasonal red/green/blue composite (26 Jul, 12 Sep and 18 Oct, HH) |
| Site Stories | Built to show a backscatter curve in decibels for each sampled site with an evidence-labelled card. With no calibrated data it shows "No site curves yet" and says why |
| What NISAR Missed | A timeline of the dates NISAR observed (nine in the preview; dates found by the search but not built into a calibrated build are marked "Observed, not used in this build") and the gap in the record (27 Jul to 10 Aug 2026) |

Evidence labels on the cards: Observed, Reference agrees, Hypothesis, Not observed. Wording such as "damage" or "detected flood" is blocked in the visible app text by a test (`app/src/content.ts`, `app/src/app.test.ts`). A change in backscatter is not proof of a physical change.

## Judging criteria

These are the criteria the Seoul event site listed. They **still need confirming in NASA's Judging and Awards Guide, due 13 November 2026**. The middle column says what we plan to show. **None of this evidence has been achieved yet**: the app shows real previews, but has no calibrated data and no checked findings.

| Criterion | Evidence in the project (planned) | Status |
|---|---|---|
| Impact | The decision or check a local planner could make | Planned, not yet achieved |
| Creativity | Radar season as a "dance", the composite, "what NISAR missed" | Planned, not yet achieved |
| Validity | Stable control, same-season checks, stated limits | Planned, not yet achieved |
| Relevance | Uses NISAR, surface change, polarizations, physical drivers | Planned, not yet achieved |
| Presentation | A clear story and a working demo | Planned, not yet achieved |

## Run the app locally

You need Node.js and npm.

```bash
npm --prefix app install
npm --prefix app run dev          # development server, http://localhost:5173
npm --prefix app test -- --run    # unit tests
npm --prefix app run build        # type-check, then build into app/dist/
npm --prefix app run preview      # serve the built app
```

The build uses relative paths (`base: "./"`) and bundles the map library, the web font and the map worker, so the built folder can be served from any path. The map has no online base map: it draws a plain background and the radar overlays. The app was checked for outside URLs in its built output, but it has **not been tested with the network turned off**.

## Run the pipeline locally

You need conda (the environment file uses conda-forge).

```bash
conda env create -f environment.yml
conda run -n sartale pytest processing/tests -q               # tests, synthetic arrays only
conda run -n sartale python app/scripts/make_brand_assets.py  # rebuild the small logo files
conda run -n sartale python app/scripts/make_demo_data.py     # rewrite the synthetic fixture in app/demo-data/
```

The synthetic fixture in `app/demo-data/` is for the app's tests. To look at it in a browser, copy it over `app/public/data/` by hand, and do not commit that copy. Its `sites.json` is written by hand, not by a script.

### Build the real preview frames

The browse PNGs are public and need no login. `data/browse/` (git-ignored) holds them with a `browse_manifest.json` listing each file's source URL and sha256 (see `docs/DATA_SOURCES.md`). The scene footprints from NASA's catalogue are in `processing/reference/cmr_footprints.json`.

```bash
cd processing
conda run -n sartale python -m sartale.run_pipeline preview
```

This checks each file's sha256, splits the RGB images into HH (red, equal to blue) and HV (green), places them on the footprint, warps to Web Mercator, crops to lon 71.2 to 73.4 and lat 33.8 to 34.8, and writes lossy WebP frames and `manifest.json` into `app/public/data/`. It writes no dB values.

## Rerun on calibrated data

This has not been done. These are the steps the code is written for.

1. Have an Earthdata Login account with the data terms accepted, and its credentials in `~/.netrc` (the download step reads it and never prints it).
2. Search the catalogue (metadata only), from the `processing/` folder:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline search --out ../data/manifest_h0.json
   ```
   This selects stack `084_A_019` (track 84, ascending, frame 19; mode 4005, DHDH) over the study box set in `processing/sartale/config.py`. See `docs/DATA_SOURCES.md`.
   `search` keeps only granules of the configured processing version (CRID `P05023`) and prints any it leaves out, so a repeat search that finds a newer version does not stop the pipeline. It also stores each file's size and MD5 from the catalogue.
3. Download the GCOV files for the four default dates into `data/gcov/` as `<granule name>.h5`. The command writes `.part` files, resumes after an interruption, and renames a file only when its size and MD5 match the catalogue:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline download      --manifest ../data/manifest_h0.json      --dates 2026-07-26,2026-08-19,2026-09-12,2026-10-18
   ```
4. Build the map images, cloud-optimised GeoTIFFs and manifest. This **overwrites the preview frames and manifest** in `app/public/data/`:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline build \
     --gcov-dir ../data/gcov --manifest-in ../data/manifest_h0.json \
     --dates 2026-07-26,2026-08-19,2026-09-12,2026-10-18
   ```
5. Sample the site curves. The sites file is a JSON list of `{id, name, lon, lat, role}` objects, and should include one stable control site:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline sites \
     --gcov-dir ../data/gcov --manifest ../app/public/data/manifest.json --sites-in ../data/sites_in.json
   ```
6. Inspect every date by eye (NASA warns that radio-interference filtering can leave residuals). Then replace the placeholder text in `app/src/content/sites.json` and the site entries in `app/src/content/story.json` using the real curves, and rebuild the app.

Use one processing version (CRID `P05023`) and one track only. The pipeline refuses a date whose CRID differs, and refuses a file whose own `granuleId` or release ID differs from the manifest (so a renamed file cannot pass as Provisional).

What `build` does besides the images:

- It applies the GCOV mask: 255 (fill) is always blank. 0 (partially focused or invalid) is blanked only when the clip also holds subswath numbers 1 to 254; a mask that holds only 0 and 255, like the 2008 samples, is left usable. It prints a mask histogram for each file, so check the first real run by eye.
- It prints a warning, without stopping, for any granule with accuracy `F` (forecast orbit) and for 2026-07-02 (possible radio interference).
- It writes `acquisitions` (every date found by the search, including dates not built) so What NISAR Missed does not call a real pass unobserved, and `composite_dates`.
- It deletes any `sites.json` and any frame the new manifest does not list. `sites` stamps every site with the manifest's `stack` and `crid`, and the app drops sites whose stamp does not match.

After the first calibrated run, update this README.

## Repository layout

| Path | Contents |
|---|---|
| `app/` | The TypeScript and MapLibre app (Vite). `app/src/content/` holds the story and site card text |
| `app/logo/SARtale.png` | The team logo, as supplied, unchanged |
| `app/public/brand/` | Small web versions of the logo, made by `app/scripts/make_brand_assets.py` |
| `app/public/data/` | The data the app loads: the real browse-preview frames, `manifest.json` and `overlays/places.geojson` (approximate hand-entered labels) |
| `app/demo-data/` | The synthetic demo, used only by tests. Not served |
| `processing/` | The Python pipeline (`sartale/`), its tests, and `reference/cmr_footprints.json` (scene footprints from NASA's catalogue) |
| `docs/` | Plan, data sources, AI tool use, concept image |
| `data/` | Local working data. Git-ignored |

## Documentation

- [Data sources and licences](docs/DATA_SOURCES.md)
- [AI tool use and event timing](docs/SI_USE.md)
- [Hackathon plan](docs/SARtale-hackathon-plan.md)

## Licence

The project code is released under the Apache License 2.0 (see `LICENSE`). Dependency and data licences are listed in `docs/DATA_SOURCES.md`, where some are still marked "to confirm". The logo was supplied by the team; `docs/SI_USE.md` records that how it was made is not yet known.
