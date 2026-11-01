<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale Pakistan logo" width="220" />
</p>

# SARtale

**An interactive story of one monsoon season, told through NISAR radar.** Built for the NASA Space Apps Challenge 2026, "Dancing with the SARs". Team **SARcastic Scientists** (Saeed Ahmad, Shaharyar Sajid), Islamabad Local Event.

The study area is the Peshawar Valley, Pakistan. The app steps through a stack of radar images, compares HH and HV polarizations, shows a seasonal colour composite, charts a few sites over time, and shows what NISAR did not observe.

## Read this first

- **The current build uses a synthetic demo.** The map images, site curves and dates in `app/public/data/` are flat-colour placeholders. They are not radar and not derived from NISAR, and they depict no real place. The app shows a permanent "SYNTHETIC DEMO: NOT NISAR DATA" banner while it runs on them.
- **The pipeline is tested on synthetic files only.** The unit tests in `processing/tests/` use small made-up files. The code has **not yet been run on a real NISAR GCOV file**, and its reading of the GCOV HDF5 layout (`processing/sartale/gcov.py`) is unverified against a real file.
- **There are no real results yet.** Nothing in this repository claims a finding about the ground. The site cards and story text are labelled "Placeholder" until real curves have been reviewed.
- **Real runs need an Earthdata login.** NISAR files are downloaded from NASA's archive with a free Earthdata account. The pipeline has no downloader of its own.
- **This is not an official warning service.** It does not issue flood warnings or forecasts. For warnings, use the Pakistan Meteorological Department (PMD), NDMA and PDMA.
- **NISAR data is Provisional.** The provisional NISAR products are not yet validated, and NASA expects to reprocess them. When real data is loaded, the app labels it "Provisional NISAR data".

## What it does

| View | What it shows |
|---|---|
| The Dance | Radar images by date on a map, a date slider and play button, HH or HV polarization, a before and after swipe, and a seasonal red/green/blue composite |
| Site Stories | A backscatter curve in decibels for each sampled site, HH and HV together, and an evidence-labelled card for each site |
| What NISAR Missed | A timeline of the dates NISAR observed and the gap in the record |

Evidence labels on the cards: Observed, Reference agrees, Hypothesis, Not observed. Wording such as "damage" or "detected flood" is blocked in the visible app text by a test (`app/src/content.ts`, `app/src/app.test.ts`). A change in backscatter is not proof of a physical change.

## Judging criteria

These are the criteria the Seoul event site listed. They **still need confirming in NASA's Judging and Awards Guide, due 13 November 2026**. The middle column says what we plan to show. **None of this evidence has been achieved yet**, because the app has no real data.

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
conda run -n sartale pytest processing/tests -q               # tests, synthetic files only
conda run -n sartale python app/scripts/make_demo_data.py     # rewrite the synthetic demo frames and manifest
conda run -n sartale python app/scripts/make_brand_assets.py  # rebuild the small logo files
```

The demo `app/public/data/sites.json` is committed by hand and is not written by a script.

## Rerun on real data

This has not been done yet. These are the steps the code is written for.

1. Create an Earthdata Login account and accept the data terms.
2. Search the catalogue (metadata only), from the `processing/` folder:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline search --out ../data/manifest_h0.json
   ```
   This selects stack `084_A_019` (track 84, ascending, frame 19; mode 4005, DHDH) over the study box set in `processing/sartale/config.py`. See `docs/DATA_SOURCES.md`.
3. Download the GCOV files named in that manifest, using your Earthdata login, and put them in one folder as `<granule name>.h5`.
4. Build the map images, cloud-optimised GeoTIFFs and manifest. This **overwrites the synthetic demo frames and manifest** in `app/public/data/`:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline build \
     --gcov-dir ../data/gcov --manifest-in ../data/manifest_h0.json \
     --dates 2026-07-02,2026-07-14,2026-07-26,2026-08-19
   ```
5. Sample the site curves. The sites file is a JSON list of `{id, name, lon, lat, role}` objects, and should include one stable control site:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline sites \
     --gcov-dir ../data/gcov --manifest ../app/public/data/manifest.json --sites-in ../data/sites_in.json
   ```
6. Inspect every date by eye (NASA warns that radio-interference filtering can leave residuals). Then replace the placeholder text in `app/src/content/story.json` and `app/src/content/sites.json` using the real curves, and rebuild the app.

Use one processing version (CRID `P05023`) and one track only. The pipeline refuses a date whose CRID differs. After the first real run, update this README and the "not yet tested" statements above.

## Repository layout

| Path | Contents |
|---|---|
| `app/` | The TypeScript and MapLibre app (Vite). `app/src/content/` holds the story and site card text |
| `app/logo/SARtale.png` | The team logo, as supplied, unchanged |
| `app/public/brand/` | Small web versions of the logo, made by `app/scripts/make_brand_assets.py` |
| `app/public/data/` | The data the app loads. Currently the synthetic demo |
| `processing/` | The Python pipeline (`sartale/`) and its tests |
| `docs/` | Plan, data sources, AI tool use, concept image |
| `data/` | Local working data. Git-ignored |

## Documentation

- [Data sources and licences](docs/DATA_SOURCES.md)
- [AI tool use and event timing](docs/SI_USE.md)
- [Hackathon plan](docs/SARtale-hackathon-plan.md)

## Licence

The project code is released under the Apache License 2.0 (see `LICENSE`). Dependency and data licences are listed in `docs/DATA_SOURCES.md`, where some are still marked "to confirm". The logo was supplied by the team; `docs/SI_USE.md` records that how it was made is not yet known.
