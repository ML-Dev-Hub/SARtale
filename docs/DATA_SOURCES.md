# Data sources and licences

Written 2026-11-01. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and identify their licences. Where a licence has not been checked, this file says "to confirm" and does not guess. The allowed claims are these: OpenStreetMap data is under the ODbL, and NASA data is openly available.

## Status in one paragraph

**The current app build contains no real data.** Everything in `app/public/data/` is a synthetic demo. No NISAR file has been downloaded. The only NISAR query so far is a metadata-only catalogue search (CMR) run on 2026-11-01. Every other dataset below is **planned and not yet used or downloaded**.

## Data in the repository now

| Item | Source | Licence | Access date |
|---|---|---|---|
| Synthetic demo frames, manifest and site curves (`app/public/data/`) | Made by the team (`app/scripts/make_demo_data.py`, plus a hand-written `sites.json`). Flat colour, not radar, no real place | Part of this repository, Apache License 2.0 | Not applicable |
| Team logo (`app/logo/SARtale.png`, resized copies in `app/public/brand/`) | Supplied by the team. Origin unknown | To confirm. The team must say who made it and whether an AI tool was used (see `docs/SI_USE.md`) | Not applicable |
| Concept storyboard (`docs/assets/sartale-concept-storyboard.png`) | AI-generated with OpenAI Codex as a planning aid. Not used in the app | To confirm | Not applicable |
| Bricolage Grotesque Variable font (bundled into the built app) | npm package `@fontsource-variable/bricolage-grotesque` 5.3.0, from the Bricolage Grotesque project | SIL Open Font License 1.1 (read from the package metadata and its `LICENSE` file) | Installed 2026-11-01 |

## NISAR data (planned use, not downloaded)

| Item | Detail |
|---|---|
| Product | NISAR L2 GCOV (geocoded polarimetric covariance), provisional. CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1` |
| Archive | NASA Earthdata / Alaska Satellite Facility (ASF). A free Earthdata Login is needed to download |
| Search | Catalogue search by bounding box 71.4, 33.9, 72.1, 34.4 (lon min, lat min, lon max, lat max), run 2026-11-01 (14:04 UTC) |
| Stack chosen | Track 84, ascending, frame 19 (`084_A_019`), mode 4005, polarization DHDH, source A |
| Processing version | CRID `P05023`. One version only, never mixed |
| Maturity | Provisional. Not validated. NASA expects reprocessing |
| Licence | NASA data is openly available. The exact data-use and citation wording is **to confirm** against the NISAR and ASF pages before submission |
| Access date | Metadata only, 2026-11-01. No files downloaded |

### Granules found in the catalogue search (not yet downloaded)

These nine names come from the search manifest `data/manifest_h0.json` (git-ignored, written by `run_pipeline search`). They were found in a catalogue search. **None has been downloaded or processed.** Accuracy and coverage are the codes from the file name, shown as they appear.

| Date (UTC) | Cycle | Accuracy | Coverage | Granule name |
|---|---|---|---|---|
| 2026-07-02 | 24 | N | F | `NISAR_L2_PR_GCOV_024_084_A_019_4005_DHDH_A_20260702T002239_20260702T002313_P05023_N_F_J_001` |
| 2026-07-14 | 25 | F | F | `NISAR_L2_PR_GCOV_025_084_A_019_4005_DHDH_A_20260714T002238_20260714T002313_P05023_F_F_J_001` |
| 2026-07-26 | 26 | N | F | `NISAR_L2_PR_GCOV_026_084_A_019_4005_DHDH_A_20260726T002237_20260726T002312_P05023_N_F_J_001` |
| 2026-08-19 | 28 | N | F | `NISAR_L2_PR_GCOV_028_084_A_019_4005_DHDH_A_20260819T002236_20260819T002311_P05023_N_F_J_001` |
| 2026-08-31 | 29 | N | F | `NISAR_L2_PR_GCOV_029_084_A_019_4005_DHDH_A_20260831T002236_20260831T002311_P05023_N_F_J_001` |
| 2026-09-12 | 30 | N | F | `NISAR_L2_PR_GCOV_030_084_A_019_4005_DHDH_A_20260912T002236_20260912T002310_P05023_N_F_J_001` |
| 2026-09-24 | 31 | N | F | `NISAR_L2_PR_GCOV_031_084_A_019_4005_DHDH_A_20260924T002236_20260924T002310_P05023_N_F_J_001` |
| 2026-10-06 | 32 | N | F | `NISAR_L2_PR_GCOV_032_084_A_019_4005_DHDH_A_20261006T002236_20261006T002311_P05023_N_F_J_001` |
| 2026-10-18 | 33 | N | F | `NISAR_L2_PR_GCOV_033_084_A_019_4005_DHDH_A_20261018T002236_20261018T002311_P05023_N_F_J_001` |

Cycle 27 has no granule in this list. The pipeline treats 2026-07-27 to 2026-08-10 as a data gap (`GAP_START` and `GAP_END` in `processing/sartale/config.py`).

## Other datasets (planned, not yet used or downloaded)

All of these are listed in the plan (`docs/SARtale-hackathon-plan.md`, section 5). Their licence status has **not** been verified for this project unless stated.

| Dataset | Planned use | Licence status | Access date |
|---|---|---|---|
| OPERA DSWx-S1 (water classification) | Same-season water check against radar | NASA data, openly available. Specific terms to confirm | Not accessed. Catalogue hits counted only |
| OPERA DSWx-HLS | Optical water check | NASA data, openly available. Specific terms to confirm | Not accessed |
| HLS (Harmonized Landsat Sentinel-2) | Crop and vegetation check | NASA data, openly available. Specific terms to confirm | Not accessed |
| NISAR SME2 soil moisture | Stretch goal only. Not fully calibrated | NASA data, openly available. Specific terms to confirm | Not accessed |
| GPM IMERG | Rain timing | NASA data, openly available. Specific terms to confirm | Not accessed |
| OpenStreetMap | Roads, bridges, hospitals, schools (the app can load optional overlays from `data/overlays/`; none is in the current build) | ODbL 1.0. Attribution "© OpenStreetMap contributors" is required if used. Share-alike duties to confirm | Not accessed |
| UNOSAT August 2025 flood map | Historical context only | To confirm | Not accessed |
| WorldPop | Rough population near road links | To confirm | Not accessed |
| HydroRIVERS and HydroBASINS (HydroSHEDS) | River and catchment context | To confirm | Not accessed |
| KP C&W, PDMA and PMD data | Not used. Left out unless a licence clearly allows open redistribution. Official warnings are linked, not republished | Not applicable | Not applicable |

The pipeline's DSWx class values (`processing/sartale/config.py`) come from the OPERA DSWx-S1 Product Specification, JPL D-108761 Rev A, Version 1.0.0. That document is cited, not redistributed.

## App dependencies (npm)

Licences are the `license` field of each installed package's `package.json`, read on 2026-11-01. Only direct dependencies are listed. Transitive dependencies have **not** been audited.

| Package | Version | Licence | Role |
|---|---|---|---|
| maplibre-gl | 6.16.0 | BSD-3-Clause | Map, bundled into the build |
| uplot | 1.6.32 | MIT | Charts, bundled |
| @fontsource-variable/bricolage-grotesque | 5.3.0 | OFL-1.1 | Font files, bundled |
| vite | 8.3.5 | MIT | Build tool (development only) |
| vitest | 5.0.5 | MIT | Tests (development only) |
| jsdom | 30.1.3 | MIT | Test DOM (development only) |
| typescript | 7.0.2 | Apache-2.0 | Type checking (development only) |

## Pipeline dependencies (Python, conda-forge)

Licences are read from the installed package metadata in the `sartale` conda environment on 2026-11-01. Only the packages named in `environment.yml` are listed; their own dependencies have not been audited.

| Package | Installed version | Licence | Used in the code now |
|---|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Yes |
| h5py | 3.16.0 | BSD-3-Clause | Yes (reads GCOV files) |
| rasterio | 1.5.2 | BSD-3-Clause | Yes |
| gdal | 3.13.3 | MIT (conda package metadata) | Through rasterio |
| pyproj | 3.8.0 | MIT | Yes |
| pillow | 13.0.0 | MIT-CMU | Yes (also the demo and logo scripts) |
| pytest | 9.2.0 | MIT | Tests |
| requests | 2.34.2 | Apache-2.0 | Listed, not imported by the pipeline code yet |
| networkx | 3.7 | BSD-3-Clause | Listed, not imported yet (planned road analysis) |
| osmnx | 2.1.1 | MIT | Listed, not imported yet (planned road analysis) |
| Python | 3.12 | Python Software Foundation licence (to confirm the exact text for the conda build) | Yes |

## Still to do

- Confirm the data-use and citation wording for NISAR, OPERA, HLS and IMERG.
- Confirm UNOSAT, WorldPop and HydroSHEDS terms, or leave them out.
- Record the logo's origin and licence.
- Re-check this file after the first real data run, and add real access dates.
