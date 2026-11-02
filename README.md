<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale Pakistan logo" width="220" />
</p>

# SARtale

SARtale uses NISAR's cloud-penetrating radar to keep watching Pakistan's dangerous glacial lakes when optical satellites cannot, and aims to show disaster teams which lakes changed and need checking next. Today it shows how often NISAR looked at each lake while clouds blocked optical satellites, and whether the radar water area moved beyond its own noise.

Built for the NASA Space Apps Challenge 2026, "Dancing with the SARs". Team **SARcastic Scientists** (Saeed Ahmad, Shaharyar Sajid), Islamabad Local Event.

## What the app shows

**Lake Watch** covers 11 glacial and landslide-dammed lakes in Gilgit-Baltistan and upper Khyber Pakhtunkhwa. For each lake it reads a small window from every NISAR pass, maps the dark (water-like) pixels inside a lake zone, and reports one plain status: Growing, Stable, Shrinking, Not seen this pass, Not observable, or Not enough NISAR looks yet.

- From 17 June to 4 August 2026, while SUPARCO's updates reported cloud limiting optical imagery, NISAR made 60 valid looks across the 11 lakes in this build. All 11 lakes read "Stable" in this build.
- The build used 232 NISAR passes: about 5.4 GB of windows read over HTTPS range requests, about one hour.
- Every number carries its date, its look count and its noise. A lake with only a point location is labelled "water area in the search window".
- Passes with a bad calibration (for example +25 dB on 7 July, track 156) are excluded and listed with the reason, never read as growth. A second screen drops passes whose window dark-pixel share or window-median HV is a robust outlier on their own track (z above 3.5); the 5 September pass on track 156, anomalous over the Hunza lakes, is excluded on every lake that has it.
- A lake whose zone sits mostly in radar shadow says "Not observable" instead of "Stable".
- A one-page brief per lake can be read in the app.

The app opens on the lake story and keeps the earlier Peshawar chapter as a downstream view (see the end of this file).

## Read this first: limits

- **Indicative screening only.** A status says whether the radar signal over a lake zone changed. It is not a measurement of lake volume or of hazard.
- **Provisional data.** The images come from NASA's provisional GCOV product (`NISAR_L2_GCOV_PROVISIONAL_V1`, CRID `P05023`). They are not validated and NASA expects to reprocess them. Only passes from 17 June 2026 are used.
- **Optical agreement is poor.** A Sentinel-2 cross-check on four lakes found similar areas only at Attabad (radar 0.218 km2, optical 0.185 km2), and even there the overlap was low (IoU 0.11). Elsewhere the areas disagreed widely: Khurdopin radar 0.036 against 0.885 km2 optical, Passu 0.048 against 0.239, and Shisper, where no lake is expected, 0.087 against 0.288 (the optical method also flags water there). Areas are water inside a search circle and under-count lakes whose shores sit in radar shadow.
- **Official warnings come from PMD and NDMA** (and PDMA, GBDMA). This is not a warning service and does not forecast floods.
- The method constants (drop 3.0 dB, 3 px speckle box, at least 3 looks, at least half of the zone observable, noise floor 0.005 km2, change factor 2.0, outlier screen z 3.5) are recorded in `app/public/data/lakes.json`. They were set by the team and not tuned against ground truth.

Why it matters: SUPARCO's GLOF Status Update of 2 July 2026 says "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days."

## Run the app

You need Node.js and npm.

```bash
npm --prefix app install
npm --prefix app run dev          # development server, http://localhost:5173
npm --prefix app test -- --run    # unit tests, including the wording check
npm --prefix app run build        # type-check, then build into app/dist/
npm --prefix app run preview      # serve the built app
```

The app reads `app/public/data/lakes.json`. If that file is missing or fails to parse, the app still opens and Lake Watch says "No lake data in this build".

## Run the lake pipeline

You need conda (`environment.yml`, conda-forge) and an Earthdata login in `~/.netrc` for the NISAR reads. Run the commands from `processing/` in the `sartale` environment, as a module (running the file directly fails on imports).

```bash
conda env create -f environment.yml
cd processing
conda run -n sartale python -m sartale.run_pipeline lakes-search   # find NISAR passes over each lake (CMR), report coverage
conda run -n sartale python -m sartale.run_pipeline lakes-fetch    # cache a 6 km window per pass over HTTPS range reads (restartable)
conda run -n sartale python -m sartale.run_pipeline lakes-build    # build lakes.json and per-lake images; exits 1 if the Attabad gate fails (--allow-gate-fail to override)
conda run -n sartale python -m sartale.run_pipeline lakes-check    # compare radar water with Sentinel-2 MNDWI water
conda run -n sartale pytest tests -q                               # pipeline tests, synthetic arrays only
```

Lake inputs are in `processing/lakes_in.json`, each with the source of its coordinates. Raw windows are cached in `data/lakes/` (git-ignored); only the derived `lakes.json` and per-lake images are committed. Whole GCOV files are not downloaded for Lake Watch.

## Documents

- [Data sources and licences](docs/DATA_SOURCES.md)
- [AI tool use and event timing](docs/SI_USE.md)
- [Lake Watch design](docs/superpowers/specs/2026-11-02-glacial-lake-watch-design.md)
- [Administration meeting log](docs/admin-meeting.md)
- [Demo script and deck outline](docs/demo-script.md)
- [Hackathon plan](docs/SARtale-hackathon-plan.md) (earlier direction; the Lake Watch design supersedes its product direction)

## The Peshawar chapter

The earlier chapter follows one monsoon season in the Peshawar Valley through calibrated NISAR images from July to October 2026: a date line, HH and HV polarizations, a seasonal colour composite, backscatter curves at sampled sites, what NISAR did not observe, and a How we know page. It uses track 84 `P05023` GCOV files rebuilt with `python -m sartale.run_pipeline rebuild`, and the same Provisional caution applies. A change in backscatter is not proof of a physical change, and each card keeps its explanation as a hypothesis. Its data and checks are described in `docs/DATA_SOURCES.md`.

### Peshawar chapter: rebuild

Run from `processing/` unless a path says otherwise. You need an Earthdata login with the data terms accepted, in `~/.netrc` (the download step reads it and never prints it).

```bash
conda run -n sartale python -m sartale.run_pipeline search --out ../data/manifest_h0.json     # catalogue metadata only; keeps stack 084_A_019, P05023
conda run -n sartale python -m sartale.run_pipeline download --manifest ../data/manifest_h0.json --dates 2026-07-26,2026-08-19   # into data/gcov/, resumable, size and MD5 checked; about 8 GB for all nine dates
conda run -n sartale python -m sartale.run_pipeline rebuild    # about 30 minutes, peaks near 8 GB of memory
```

**Warning: `rebuild` overwrites the Peshawar files in `app/public/data/`** (frames, `manifest.json`, `sites.json`) and removes any it no longer lists. `lakes.json` and the lake images are written by `lakes-build` and are separate. After a rebuild, read the printed checks, look at every date by eye, and rerun `npm --prefix app test -- --run`: `app/src/publicData.test.ts` compares every value a site card quotes with the new curves, so a card that no longer matches fails.

Asset scripts, run from the repository root:

```bash
conda run -n sartale python app/scripts/make_brand_assets.py   # small logo files in app/public/brand/
conda run -n sartale python app/scripts/make_hero_image.py     # start-screen picture from the seasonal composite frame
```

`app/demo-data/` (made by `app/scripts/make_demo_data.py`) is a synthetic test fixture. It is not served and should not be copied over `app/public/data/` for a commit.

Peshawar limits: the 2 July pass is flagged as likely radio interference in HV and is left out of the change layer. The Change view is a statistical flag on backscatter steps, not proof of what changed on the ground.

## Repository layout

| Path | Contents |
|---|---|
| `app/` | The TypeScript and MapLibre app (Vite). Copy text is in `app/src/content/` |
| `app/public/data/` | Data the app loads: `lakes.json`, per-lake images, and the Peshawar frames, `manifest.json` and `sites.json` |
| `processing/` | The Python pipeline (`sartale/`), tests, `lakes_in.json`, and the scripts behind the evidence in `docs/DATA_SOURCES.md` |
| `docs/` | Design, data sources, AI tool use, meeting log, demo script |
| `data/` | Local working data, including `data/lakes/` window caches. Git-ignored |

## Licence

The project code is released under the Apache License 2.0 (see `LICENSE`). Dependency and data licences are listed in `docs/DATA_SOURCES.md`, where some are marked "terms not confirmed" or "to confirm". The logo was supplied by the team; `docs/SI_USE.md` records that how it was made is not yet known.
