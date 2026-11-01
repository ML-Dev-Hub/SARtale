# Data sources and licences

Written 2026-11-01, updated 2026-11-02. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and identify their licences. Where a licence has not been checked, this file says "to confirm" and does not guess. The allowed claims are these: OpenStreetMap data is under the ODbL, and NASA data is openly available.

## Status in one paragraph

**The app shows real NISAR images, but only NASA's low-resolution browse previews.** Nine dates of track 84 were downloaded from NASA's public browse archive without a login (details below). Their pixel values are scaled for display and are not calibrated, so the app shows no decibel values, no curves and no statistics. **No calibrated GCOV file has been downloaded**, because that needs an Earthdata login. The catalogue (CMR) was also read for metadata only. Two public 2008 NISAR sample GCOV files were used to test the file reader and are not results. Every other dataset below is **planned and not yet used or downloaded**.

## Data in the repository now

| Item | Source | Licence | Access date |
|---|---|---|---|
| Real NISAR browse preview frames and `manifest.json` (`app/public/data/`) | Made by `run_pipeline preview` from NASA's public browse PNGs (see "NISAR browse previews" below). Reordered, warped and cropped for display only | NASA data, openly available. Exact wording to confirm | 2026-11-01 and 2026-11-02 |
| Place labels (`app/public/data/overlays/places.geojson`) | **Approximate, hand-entered** labels for Peshawar, Nowshera, Charsadda, Mardan, Swabi and Tarbela Reservoir. Typed in by the team from general knowledge, not copied from a dataset. Positions are rough, to about a few kilometres | Part of this repository, Apache License 2.0 | Not applicable |
| Scene footprints (`processing/reference/cmr_footprints.json`) | Corner coordinates of the nine scenes from NASA CMR granule metadata (UMM-G SpatialExtent). Used to place the previews on the map | NASA catalogue metadata, public | 2026-11-02 |
| Synthetic demo frames, manifest and site curves (`app/demo-data/`) | Made by the team (`app/scripts/make_demo_data.py`, plus a hand-written `sites.json`). Flat colour, not radar, no real place. **Test fixture only: not in the folder the app serves** | Part of this repository, Apache License 2.0 | Not applicable |
| Team logo (`app/logo/SARtale.png`, resized copies in `app/public/brand/`) | Supplied by the team. Origin unknown | To confirm. The team must say who made it and whether an AI tool was used (see `docs/SI_USE.md`) | Not applicable |
| Concept storyboard (`docs/assets/sartale-concept-storyboard.png`) | AI-generated with OpenAI Codex as a planning aid. Not used in the app | To confirm | Not applicable |
| Bricolage Grotesque Variable font (bundled into the built app) | npm package `@fontsource-variable/bricolage-grotesque` 5.3.0, from the Bricolage Grotesque project | SIL Open Font License 1.1 (read from the package metadata and its `LICENSE` file) | Installed 2026-11-01 |

## NISAR browse previews (used by the app)

NASA publishes a quick-look PNG set next to each NISAR GCOV granule in the ASF browse archive (`https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/<granule>/`). These are public: they were fetched with plain HTTPS requests, with no login and no credentials. Three files exist per granule: `_LATLON.png` (RGB, on a longitude and latitude grid), and `_NATIVE_A_HHHH.png` and `_NATIVE_A_HVHV.png` (greyscale, in the scene's own geometry). The app uses only the `_LATLON.png` files. The 18 `_NATIVE` files were downloaded to check which colour channel is which polarization, and are not used otherwise. All 27 files are kept in `data/browse/` (git-ignored), with `browse_manifest.json` recording each file's granule, size, sha256 and URL. `run_pipeline preview` re-checks the sha256 of each file before use.

| Item | Detail |
|---|---|
| What the pixels are | Display-scaled 8-bit values. **Not calibrated, not dB.** The app never shows them as measurements |
| Pixel size | About 174 m (measured: 0.0019 degrees east-west and 0.00156 degrees north-south, from the footprint fit) |
| Channel layout | Red and blue are HH (identical on all nine images), green is HV. Checked against the `_NATIVE` greyscale images by histogram and by the difference of channel means across the nine dates |
| Georeferencing | No sidecar file is published. The valid-data bounding box was mapped onto the lon/lat bounding box of the scene footprint from CMR. The four footprint corners land on the data corners to within a few pixels (typically 0 to 3, worst 10, which is about 1.7 km). Tarbela reservoir and Peshawar fall where they should. Overall the placement is good to about 2 km. The nine images lie on one pixel grid (no shift between dates), so one shared extent is used |
| Display window | Longitude 70.9 to 72.8, latitude 33.6 to 34.8. The western edge of the scene footprint cuts through this window, so part of its west side is empty |
| Maturity | Provisional. Not validated. NASA expects reprocessing |
| Date cautions | 2 Jul: possible radio interference over the western area, unconfirmed (seen by eye on the browse image only). 14 Jul: forecast-orbit product (the `F` in the granule name), so positions may be less precise |
| Licence | NASA data is openly available. The exact data-use and citation wording is **to confirm** against the NISAR and ASF pages before submission |
| Access date | 2026-11-01 (browse images and catalogue search) and 2026-11-02 (footprint metadata) |

The nine `_LATLON.png` files used by the app:

| Date (UTC) | File | Bytes | sha256 | Source URL |
|---|---|---|---|---|
| 2026-07-02 | `20260702_LATLON.png` | 4,814,646 | `73015a62ebab75da6e5324a3b30e947c44380322eaec039a07ab4f2338d999d8` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_024_084_A_019_4005_DHDH_A_20260702T002239_20260702T002313_P05023_N_F_J_001/NISAR_L2_PR_GCOV_024_084_A_019_4005_DHDH_A_20260702T002239_20260702T002313_P05023_N_F_J_001_LATLON.png |
| 2026-07-14 | `20260714_LATLON.png` | 5,010,721 | `47f20f2e8ecd155d22527a1791165598ce48e489ec92fc7ef6ed61171d7d128d` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_025_084_A_019_4005_DHDH_A_20260714T002238_20260714T002313_P05023_F_F_J_001/NISAR_L2_PR_GCOV_025_084_A_019_4005_DHDH_A_20260714T002238_20260714T002313_P05023_F_F_J_001_LATLON.png |
| 2026-07-26 | `20260726_LATLON.png` | 4,963,406 | `8be28f0de62553fc89e28ab7233556ab212e3334e5848803ecd38978effd6fc2` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_026_084_A_019_4005_DHDH_A_20260726T002237_20260726T002312_P05023_N_F_J_001/NISAR_L2_PR_GCOV_026_084_A_019_4005_DHDH_A_20260726T002237_20260726T002312_P05023_N_F_J_001_LATLON.png |
| 2026-08-19 | `20260819_LATLON.png` | 4,975,615 | `f91f0ce075b9eba69a88c5621c9f3bef28df0ae3f74ab00829f6502dfb689d6c` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_028_084_A_019_4005_DHDH_A_20260819T002236_20260819T002311_P05023_N_F_J_001/NISAR_L2_PR_GCOV_028_084_A_019_4005_DHDH_A_20260819T002236_20260819T002311_P05023_N_F_J_001_LATLON.png |
| 2026-08-31 | `20260831_LATLON.png` | 4,984,514 | `bf7d01507b393459d772c2274f5c367119dd90604d3e8aaad8276fd2f47f9d39` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_029_084_A_019_4005_DHDH_A_20260831T002236_20260831T002311_P05023_N_F_J_001/NISAR_L2_PR_GCOV_029_084_A_019_4005_DHDH_A_20260831T002236_20260831T002311_P05023_N_F_J_001_LATLON.png |
| 2026-09-12 | `20260912_LATLON.png` | 4,807,082 | `f1fb7a1213ff56322e5b5bc648f8be553e9c53c2c677f13ecc7f2ca6a9e60043` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_030_084_A_019_4005_DHDH_A_20260912T002236_20260912T002310_P05023_N_F_J_001/NISAR_L2_PR_GCOV_030_084_A_019_4005_DHDH_A_20260912T002236_20260912T002310_P05023_N_F_J_001_LATLON.png |
| 2026-09-24 | `20260924_LATLON.png` | 4,808,264 | `3ea029e7d7e8cb089ff04b3ab5fd00323523f6b286b818fefbf0d98fe8fb496a` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_031_084_A_019_4005_DHDH_A_20260924T002236_20260924T002310_P05023_N_F_J_001/NISAR_L2_PR_GCOV_031_084_A_019_4005_DHDH_A_20260924T002236_20260924T002310_P05023_N_F_J_001_LATLON.png |
| 2026-10-06 | `20261006_LATLON.png` | 4,969,683 | `9d752113773f83afbaaf05e6d234e7dccf1d595a2fa20cfeb114a225a1ba53d0` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_084_A_019_4005_DHDH_A_20261006T002236_20261006T002311_P05023_N_F_J_001/NISAR_L2_PR_GCOV_032_084_A_019_4005_DHDH_A_20261006T002236_20261006T002311_P05023_N_F_J_001_LATLON.png |
| 2026-10-18 | `20261018_LATLON.png` | 4,982,591 | `43eb86e302bd2101789deca376125af1346b037924901474dfadaf0615d169f9` | https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_084_A_019_4005_DHDH_A_20261018T002236_20261018T002311_P05023_N_F_J_001/NISAR_L2_PR_GCOV_033_084_A_019_4005_DHDH_A_20261018T002236_20261018T002311_P05023_N_F_J_001_LATLON.png |

These nine granules are the ones in the table below. Their footprints (`processing/reference/cmr_footprints.json`) come from the same CMR search, repeated for metadata only on 2026-11-02 with a time window of 2026-06-30 to 2026-10-20.

### NISAR sample GCOV files from 2008 (reader test only)

Two public NISAR sample GCOV files dated 2008 (`NISAR_L2_PR_GCOV_001_030_A_019_2800_SHNA_A_20081012...` and `..._002_030_..._20081127...`, from NASA's [sample data page](https://science.nasa.gov/mission/nisar/sample-data/)) are kept in `data/sample/` (git-ignored). They are older product versions over a different area. They were used **only** to run `read_layer` and the multilook step and to confirm the HDF5 layout. They appear in no result, image or figure.

## NISAR GCOV data (calibrated, not downloaded)

| Item | Detail |
|---|---|
| Product | NISAR L2 GCOV (geocoded polarimetric covariance), provisional. CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1` |
| Archive | NASA Earthdata / Alaska Satellite Facility (ASF). A free Earthdata Login is needed to download |
| Search | Catalogue search by bounding box 71.4, 33.9, 72.1, 34.4 (lon min, lat min, lon max, lat max), run 2026-11-01 (14:04 UTC) |
| Stack chosen | Track 84, ascending, frame 19 (`084_A_019`), mode 4005, polarization DHDH, source A |
| Processing version | CRID `P05023`. One version only, never mixed |
| Maturity | Provisional. Not validated. NASA expects reprocessing |
| Licence | NASA data is openly available. The exact data-use and citation wording is **to confirm** against the NISAR and ASF pages before submission |
| Access date | Metadata only. **No GCOV file has been downloaded.** The real `P05023` files are unread |

### Granules found in the catalogue search

These nine names come from the search manifest `data/manifest_h0.json` (git-ignored, written by `run_pipeline search`). The browse previews of these granules are used by the app. **None of the GCOV HDF5 files has been downloaded or processed.** Accuracy and coverage are the codes from the file name, shown as they appear.

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
| OpenStreetMap | Roads, bridges, hospitals, schools (the app can load optional overlays from `data/overlays/`; the only overlay in the current build is the hand-entered place labels, not OSM) | ODbL 1.0. Attribution "© OpenStreetMap contributors" is required if used. Share-alike duties to confirm | Not accessed |
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
| pillow | 13.0.0 | MIT-CMU | Yes (reads the browse PNGs, writes WebP; also the demo and logo scripts) |
| pytest | 9.2.0 | MIT | Tests |
| requests | 2.34.2 | Apache-2.0 | Listed, not imported by the pipeline code yet |
| networkx | 3.7 | BSD-3-Clause | Listed, not imported yet (planned road analysis) |
| osmnx | 2.1.1 | MIT | Listed, not imported yet (planned road analysis) |
| Python | 3.12 | Python Software Foundation licence (to confirm the exact text for the conda build) | Yes |

## Still to do

- Confirm the data-use and citation wording for NISAR, OPERA, HLS and IMERG.
- Confirm UNOSAT, WorldPop and HydroSHEDS terms, or leave them out.
- Record the logo's origin and licence.
- Re-check this file after the first calibrated data run, and add real access dates.
- Check the place labels against a map or gazetteer before they are described as anything more than approximate.
