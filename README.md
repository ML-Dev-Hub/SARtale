<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale Pakistan logo" width="220" />
</p>

# SARtale

**An interactive story of one monsoon season, told through NISAR radar.** Built for the NASA Space Apps Challenge 2026, "Dancing with the SARs". Team **SARcastic Scientists** (Saeed Ahmad, Shaharyar Sajid), Islamabad Local Event.

The study area is the Peshawar Valley, Pakistan. The app opens on a plain-language start screen with one finding, then offers a guided story of six parts that moves the real map to each place (or free exploring, and a way back into the story). It steps through calibrated NISAR radar images from July to October 2026 on a date line spaced by real time, compares HH and HV polarizations, shows a seasonal colour composite, charts backscatter at sampled sites, shows what NISAR did not observe, and has a How we know page that sets out its data, method, control results, rule and limits.

## Read this first

- **The app shows calibrated NISAR data, and that data is Provisional.** The images and curves come from NASA's provisional GCOV files (processing version `P05023`, RTC gamma-0, stored as linear power). They are not validated and NASA expects to reprocess them. The banner reads "Provisional NISAR data", and the limits line under the map gives the pixel sizes and the grey scale.
- **Measurements use 30 m pixels; the map pictures are coarser.** Every value in a curve or a downloadable GeoTIFF comes from 10 m samples averaged in linear power to 30 m. The web frames are averaged once more and capped at 3000 pixels wide to keep each file small, so a map pixel is about 67 m.
- **Two dates carry a visible caution.** 2 July: "Likely radio interference in HV over the western area. Do not read this as surface change." The evidence is in `docs/DATA_SOURCES.md`. 14 July: "Forecast-orbit product; positions may be less precise." That date's measured shift against 26 July is under 3 m, so the caution is kept because of what the file says, not because a shift was seen.
- **A change in backscatter is not flood probability.** The curves show that the radar signal changed. On their own they do not say why, and each card keeps its explanation as a hypothesis. A card carries "Reference agrees" only where a dated outside source moved the same way (see `docs/DATA_SOURCES.md`).
- **The Change view is a statistical flag, not proof of what changed.** It marks areas where radar brightness stepped up or down, coloured by the date of the step, about 1.4% of the window. Controls stay quiet, and the Tarbela shore and the Attock river stand out around 19 August and 24 September, but plain ground flags as strongly, and a step names no cause. Its limits were set with the known sites in view, its false-alarm budget is about 1%, and the map is drawn at 270 m but analysed at 90 m, with about 31% of flagged pixels falling in cells that are not drawn. A second view, Unusual dates, shows how odd each date is for a pixel; it cannot place a lasting change. The numbers are in `docs/DATA_SOURCES.md`.
- **No flood, damage or crop finding is claimed.** Plain areas are named by what the radar shows, and land cover has not been checked on the ground.
- **The synthetic demo is a test fixture only.** It lives in `app/demo-data/`, outside the folder the app serves, so it cannot ship. See "Run the pipeline locally".
- **This is not an official warning service.** It does not issue flood warnings or forecasts. For warnings, use the Pakistan Meteorological Department (PMD), NDMA and PDMA.

## What it does

| View | What it shows |
|---|---|
| Start and the story | A hero with the real radar picture and one finding (the Tarbela shore stepped down around 19 Aug as the reservoir rose, worded as a hypothesis), then a ten-step story in six parts: why the valley matters, meet NISAR, the season plays, why it moved (Tarbela, Attock, HH against HV), what NISAR missed (2 July, the 23 July peak, the gap), why it matters and what next. The text is in `app/src/content/story.json`. Leave it at any time and resume where you stopped |
| The Dance | Calibrated frames by date on a map that fills the screen, with a scale bar, one shared grey scale, a date line spaced by real time (the data gap is a hatched band, flagged and excluded dates are marked), play, HH or HV polarization, a before and after swipe, a seasonal red/green/blue composite of three HH dates (the app names them; flagged dates are left out), and a Change map coloured by the date and direction of each step, with an Unusual dates view beside it (2 July is excluded, and says why). Frames load ahead of play and the map says what it is waiting for |
| Site Stories | A backscatter curve in decibels for each sampled site, with an evidence-labelled card: chart first, then observation, hypothesis, what would test it and its limits, with the site's step size and date, the share of map pixels flagged near it (with the pixel count) and each date's score. Tap a point on the chart, or a date in the table, to see the map on that day. Controls are listed apart and marked |
| What NISAR Missed | A timeline of the dates NISAR observed (dates found by the search but not built are marked "Observed, not used in this build"), the gap in the record (27 Jul to 10 Aug 2026), and one dated river report from Pakistan's Flood Forecasting Division |
| How we know | The data sources, the method in plain words, control results, the rule and how it was set (not blind, and it changed), the limits and what would change our mind. Text in `app/src/content/evidence.json`; every figure traces to `docs/DATA_SOURCES.md` |

Evidence labels on the cards: Observed, Reference agrees, Hypothesis, Not observed. Wording such as "damage", "detected flood" or "detected change" is blocked in the visible app text by a test (`app/src/content.ts`, `app/src/app.test.ts`). A change in backscatter is not proof of a physical change.

## Judging criteria

These are the criteria the Seoul event site listed. They **still need confirming in NASA's Judging and Awards Guide, due 13 November 2026**. The middle column says what we plan to show. The calibrated build, the controls and the reference checks now exist; the team still has to judge whether they meet each criterion.

| Criterion | Evidence in the project (planned) | Status |
|---|---|---|
| Impact | The decision or check a local planner could make | Not yet judged |
| Creativity | Radar season as a "dance", the composite, "what NISAR missed" | Not yet judged |
| Validity | Stable control, same-season checks, stated limits | Not yet judged |
| Relevance | Uses NISAR, surface change, polarizations, physical drivers | Not yet judged |
| Presentation | A clear story and a working demo | Not yet judged |

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
conda run -n sartale python app/scripts/make_hero_image.py    # rebuild the small start-screen picture from the composite frame
conda run -n sartale python app/scripts/make_demo_data.py     # rewrite the synthetic fixture in app/demo-data/
```

The synthetic fixture in `app/demo-data/` is for the app's tests. To look at it in a browser, copy it over `app/public/data/` by hand, and do not commit that copy. Its `sites.json` is written by hand, not by a script.

## Rerun on calibrated data

1. Have an Earthdata Login account with the data terms accepted, and its credentials in `~/.netrc` (the download step reads it and never prints it).
2. Search the catalogue (metadata only), from the `processing/` folder. This keeps only stack `084_A_019` at processing version `P05023` and stores each file's size and MD5:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline search --out ../data/manifest_h0.json
   ```
3. Download the files you want into `data/gcov/`. The command writes `.part` files, resumes after an interruption, and renames a file only when its size and MD5 match the catalogue:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline download --manifest ../data/manifest_h0.json --dates 2026-07-26,2026-08-19
   ```
4. Rebuild everything from every verified file. This is the one command to run, and it **overwrites** `app/public/data/`:
   ```bash
   conda run -n sartale python -m sartale.run_pipeline rebuild
   ```
   It skips `.part` files and any file whose size differs from the catalogue, runs `build`, `change` and `sites`, and prints mask histograms, warnings, frame sizes, the change threshold and removed offsets, each site's spread and a check of the controls. Allow about half an hour; it peaked at about 8 GB of memory on nine dates. `build` and `sites` can also be run alone, with the same options. `run_pipeline change` rebuilds only the change layer from the COGs, in about 3 minutes, and touches no other frame. **It too peaks at about 8 GB of memory** (a figure from the review of this step, not one we measured again), so close other programs first on a smaller machine. A lone `build` drops the layer until `change` runs again.
5. Read the printed checks and look at every date by eye. Then rerun the app tests: `app/src/publicData.test.ts` compares every value a card quotes with the new curves, so a card that no longer matches fails.

The sites are in `processing/sites_in.json`, each with the reason it was chosen. The cards are in `app/src/content/sites.json`.

What the build does besides the images:

- It works over longitude 71.2 to 73.4 and latitude 33.8 to 34.8 (`WINDOW` in `processing/sartale/config.py`), one date at a time, keeping only 30 m power in memory.
- It applies the GCOV mask: 255 (fill) and 0 (partially focused) are blanked. It prints a mask histogram for each file and stops on any value other than 0, 1 and 255.
- It refuses a date whose CRID differs, and a file whose own `granuleId` or release ID differs from the manifest, so a renamed file cannot pass as Provisional.
- It writes `acquisitions` (every date the search found) so What NISAR Missed does not call a real pass unobserved, and `composite_dates`. The composite leaves out every flagged date, and the grey scale leaves out 2 July.
- It writes the same per-date flags as the preview path, and prints a warning for each.
- `change` looks for the largest step at each 90 m pixel over eight dates, leaving 2 July out entirely, and sets its limits from the controls and from shuffled dates. It also scores each date against the season's other dates; 14 July is scored but stays out of that baseline. With four or fewer baseline dates it writes no layer.
- It deletes any `sites.json` and any frame the new manifest does not list. `sites` stamps every site with the manifest's `stack` and `crid`, and the app drops sites whose stamp does not match.

### Rebuild the low-resolution preview

NASA's public browse PNGs need no login. They are not calibrated, and the preview path still works, but its output replaces the calibrated data and removes `sites.json`:

```bash
cd processing
conda run -n sartale python -m sartale.run_pipeline preview
```

It reads `data/browse/` (git-ignored; see `docs/DATA_SOURCES.md`), checks each file's sha256, and writes the frames and `manifest.json` into `app/public/data/`. It writes no dB values, and the banner then reads "REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED".

## Repository layout

| Path | Contents |
|---|---|
| `app/` | The TypeScript and MapLibre app (Vite). `app/src/content/` holds the story and site card text |
| `app/logo/SARtale.png` | The team logo, as supplied, unchanged |
| `app/public/brand/` | Small web versions of the logo, made by `app/scripts/make_brand_assets.py`, and `hero-radar.webp`, the start-screen picture (the seasonal composite scaled to 1280 px, 213 KB), made by `app/scripts/make_hero_image.py` |
| `app/public/data/` | The data the app loads: calibrated web frames, `manifest.json`, `sites.json` and `overlays/places.geojson` (approximate hand-entered labels) |
| `app/demo-data/` | The synthetic demo, used only by tests. Not served |
| `processing/` | The Python pipeline (`sartale/`), its tests, `checks/` (the scripts behind the evidence in `docs/DATA_SOURCES.md`), `sites_in.json` (the sites and why each was chosen), and `reference/cmr_footprints.json` (scene footprints from NASA's catalogue) |
| `docs/` | Plan, data sources, AI tool use, concept image |
| `data/` | Local working data: GCOV files, 30 m GeoTIFFs in `data/cog/`, OPERA tiles, browse PNGs. Git-ignored |

## Documentation

- [Data sources and licences](docs/DATA_SOURCES.md)
- [AI tool use and event timing](docs/SI_USE.md)
- [Hackathon plan](docs/SARtale-hackathon-plan.md)

## Licence

The project code is released under the Apache License 2.0 (see `LICENSE`). Dependency and data licences are listed in `docs/DATA_SOURCES.md`, where some are still marked "to confirm". The logo was supplied by the team; `docs/SI_USE.md` records that how it was made is not yet known.
