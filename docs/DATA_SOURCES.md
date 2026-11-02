# Data sources and licences

Written 2026-11-01, updated 2026-11-02 after the first calibrated build. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and identify their licences. Where a licence has not been checked, this file says "to confirm" and does not guess. The allowed claims are these: OpenStreetMap data is under the ODbL, and NASA data is openly available.

## Status in one paragraph

**The app shows calibrated NISAR data, labelled Provisional.** It is built by `run_pipeline rebuild` from the verified `P05023` GCOV files of track 84 in `data/gcov/` (git-ignored). The first real build ran on 2026-11-02. OPERA DSWx-S1 tiles and Flood Forecasting Division bulletins were read for the checks below. NASA's browse previews remain reproducible with `run_pipeline preview`, but they are no longer what the app shows. Every dataset under "Other datasets" is **planned and not yet used or downloaded**.

## Data in the repository now

| Item | Source | Licence | Access date |
|---|---|---|---|
| Calibrated web frames, `manifest.json` and `sites.json` (`app/public/data/`) | Made by `run_pipeline rebuild` from NISAR GCOV files (see "NISAR GCOV data" below). 30 m analysis, about 67 m on the map | NASA data, openly available. Exact wording to confirm | 2026-11-02 |
| Change frames and scores (`app/public/data/frames/step_date.webp` and `change_<date>.webp`, the `change` record in `manifest.json`, `step` and `change_score` in `sites.json`) | Made by `run_pipeline change` from the calibrated 30 m COGs (see "Before-and-after step layer" and "Unusual dates layer") | Derived from NASA data. Exact wording to confirm | 2026-11-02 |
| Start-screen picture (`app/public/brand/hero-radar.webp`) | The seasonal composite frame (`frames/composite_HH.webp`) scaled to 1280 px wide and recompressed by `app/scripts/make_hero_image.py`, so the first screen stays light. Shown with its three dates named and the word Provisional. The data frames themselves are unchanged | Derived from NASA data. Exact wording to confirm | 2026-11-02 |
| Place labels (`app/public/data/overlays/places.geojson`) | **Approximate, hand-entered** labels for Peshawar, Nowshera, Charsadda, Mardan, Swabi and Tarbela Reservoir. Typed in by the team from general knowledge, not copied from a dataset. Positions are rough, to about a few kilometres | Part of this repository, Apache License 2.0 | Not applicable |
| Site list (`processing/sites_in.json`) | Chosen by the team's tooling from the real stack, each with its reason | Part of this repository, Apache License 2.0 | Not applicable |
| River and reservoir figures in `app/src/content/` | A few dated numbers quoted, with the source named, from the Flood Forecasting Division's public daily bulletins (see "Flood Forecasting Division bulletins" below) | Pakistan Meteorological Department. Reuse terms to confirm; the bulletins themselves are not redistributed | 2026-11-02 |
| Scene footprints (`processing/reference/cmr_footprints.json`) | Corner coordinates of the scenes from NASA CMR granule metadata (UMM-G SpatialExtent). Used to place the previews on the map | NASA catalogue metadata, public | 2026-11-02 |
| Synthetic demo frames, manifest and site curves (`app/demo-data/`) | Made by the team (`app/scripts/make_demo_data.py`, plus a hand-written `sites.json`). Flat colour, not radar, no real place. **Test fixture only: not in the folder the app serves** | Part of this repository, Apache License 2.0 | Not applicable |
| Team logo (`app/logo/SARtale.png`, resized copies in `app/public/brand/`) | Supplied by the team. Origin unknown | To confirm. The team must say who made it and whether an AI tool was used (see `docs/SI_USE.md`) | Not applicable |
| Concept storyboard (`docs/assets/sartale-concept-storyboard.png`) | AI-generated with OpenAI Codex as a planning aid. Not used in the app | To confirm | Not applicable |
| Bricolage Grotesque Variable font (bundled into the built app) | npm package `@fontsource-variable/bricolage-grotesque` 5.3.0, from the Bricolage Grotesque project | SIL Open Font License 1.1 (read from the package metadata and its `LICENSE` file) | Installed 2026-11-01 |

## NISAR browse previews (not shown by the app now; `run_pipeline preview` still builds them)

NASA publishes a quick-look PNG set next to each NISAR GCOV granule in the ASF browse archive (`https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/NISAR_L2_GCOV_PROVISIONAL_V1/<granule>/`). These are public: they were fetched with plain HTTPS requests, with no login and no credentials. Three files exist per granule: `_LATLON.png` (RGB, on a longitude and latitude grid), and `_NATIVE_A_HHHH.png` and `_NATIVE_A_HVHV.png` (greyscale, in the scene's own geometry). The preview path uses only the `_LATLON.png` files. The 18 `_NATIVE` files were downloaded to check which colour channel is which polarization, and are not used otherwise. All 27 files are kept in `data/browse/` (git-ignored), with `browse_manifest.json` recording each file's granule, size, sha256 and URL. `run_pipeline preview` re-checks the sha256 of each file before use.

| Item | Detail |
|---|---|
| What the pixels are | Display-scaled 8-bit values. **Not calibrated, not dB.** The app never shows them as measurements |
| Pixel size | About 174 m (measured: 0.0019 degrees east-west and 0.00156 degrees north-south, from the footprint fit) |
| Channel layout | Red and blue are HH (identical on all nine images), green is HV. Checked against the `_NATIVE` greyscale images by histogram and by the difference of channel means across the nine dates |
| Georeferencing | No sidecar file is published. The valid-data bounding box was mapped onto the lon/lat bounding box of the scene footprint from CMR. The four footprint corners land on the data corners to within a few pixels (typically 0 to 3, worst 10, which is about 1.7 km). This is **not an independent check at the corners**: the fit maps the valid-data bounding box onto the footprint's bounding box, so one coordinate of each corner is matched by construction. The coordinates that are not extremes (the other coordinate of each corner), and landmarks such as Tarbela reservoir and Peshawar, are the real check. Tarbela reservoir and Peshawar fall where they should. Overall the placement is good to about 2 km. The nine images lie on one pixel grid (no shift between dates), so one shared extent is used |
| Display window | Longitude 71.2 to 73.4, latitude 33.8 to 34.8, chosen from the real frames: about 96 percent of it holds data on all nine dates, and the tilted west edge of the footprint (longitude about 71.37 at Peshawar's latitude) stays in view |
| Maturity | Provisional. Not validated. NASA expects reprocessing |
| Date cautions | 2 Jul: likely radio interference in HV over the western area (see "Checks on the calibrated data"). 14 Jul: forecast-orbit product (the `F` in the granule name), so positions may be less precise |
| Licence | NASA data is openly available. The exact data-use and citation wording is **to confirm** against the NISAR and ASF pages before submission |
| Access date | 2026-11-01 (browse images and catalogue search) and 2026-11-02 (footprint metadata) |

The `_LATLON.png` files:

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

These granules are the ones in the table below. Their footprints (`processing/reference/cmr_footprints.json`) come from the same CMR search, repeated for metadata only on 2026-11-02 with a time window of 2026-06-30 to 2026-10-20.

### NISAR sample GCOV files from 2008 (reader test only)

Two public NISAR sample GCOV files dated 2008 (`NISAR_L2_PR_GCOV_001_030_A_019_2800_SHNA_A_20081012...` and `..._002_030_..._20081127...`, from NASA's [sample data page](https://science.nasa.gov/mission/nisar/sample-data/)) are kept in `data/sample/` (git-ignored). They are older product versions over a different area. They were used **only** to run `read_layer` and the multilook step and to confirm the coordinate, projection and looks layout, and the field names `identification/granuleId` and `identification/compositeReleaseId`. They are single-pol files with no HV term, and their mask holds only 0 and 255, so they cannot confirm what the mask values mean on a real file or that HV reads correctly. They appear in no result, image or figure.

## NISAR GCOV data (calibrated, used by the app)

| Item | Detail |
|---|---|
| Product | NISAR L2 GCOV (geocoded polarimetric covariance), provisional. CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1`. Product version 1.0.11 in the files read |
| Archive | NASA Earthdata / Alaska Satellite Facility (ASF). A free Earthdata Login is needed to download. `run_pipeline download` fetches the files (resumable, size and MD5 checked against the catalogue) |
| Search | Catalogue search by bounding box 71.4, 33.9, 72.1, 34.4 (lon min, lat min, lon max, lat max), repeated 2026-11-02 |
| Stack chosen | Track 84, ascending, frame 19 (`084_A_019`), mode 4005, polarization DHDH, frequency A (1239 MHz centre, 40 MHz band, 10 m grid in EPSG:32643) |
| Processing version | CRID `P05023`. One version only, never mixed. `build` checks each file's own `granuleId` and `compositeReleaseId` |
| Radiometry | Read from the file: `radiometricTerrainCorrectionApplied` True, output convention `gamma0`, linear power. `noiseCorrectionApplied` False, so dark targets keep the noise floor: the file's noise-equivalent backscatter at Tarbela is about -25 dB in HV |
| Mask | Values 0, 1 and 255 on all files. 0 and 255 are blanked |
| Interference | `rfiMitigationApplied` is False on all files. `inputDataExceptionMask` is all zero over the window on all files. `rfiLikelihood` is documented as 0 to 1 but holds values from about 15 to 1.7e11, so it was not used |
| Multilooking | Mask, then average linear power over 3 x 3 pixels to 30 m, then dB. Web frames average one more 2 x 2 step and are capped at 3000 pixels wide (about 67 m), for display only |
| Maturity | Provisional. Not validated. NASA expects reprocessing |
| Licence | NASA data is openly available. The exact data-use and citation wording is **to confirm** against the NISAR and ASF pages before submission |
| Access date | Downloaded 2026-11-02 |

### Granules found in the catalogue search

These names come from the search manifest `data/manifest_h0.json` (git-ignored, written by `run_pipeline search`). The app's manifest lists which of them each build used. Accuracy and coverage are the codes from the file name, shown as they appear.

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

## Checks on the calibrated data

All numbers below are from the first real build, 2026-11-02. The scripts behind them are in `processing/checks/`. Backscatter is gamma-0 in dB.

### 2 July: likely radio interference in HV

The evidence supports "likely radio interference", so the flag says that. It does not prove the cause: an instrument fault in the HV channel on that pass would look much the same.

- **Where.** A smooth patch over the western area, about 970 km2 where HV is more than 6 dB above the median of the other dates (averaged over 1 km), roughly longitude 71.24 to 71.63, latitude 33.94 to 34.43. It sits against the western edge of the scene and runs across hills, plain and river without following any of them.
- **One compact patch.** Above 6 dB, 99 percent of the area is one connected piece, about 54 km along the track and 29 km across it, in a frame about 240 km long. It is not a strip running the length of the track.
- **HV only.** Inside the area with more than 10 dB of excess, the mean HV is -0.7 dB on 2 July against -13.4 to -15.0 dB on the eight other dates, while the mean HH is -5.2 dB against -5.2 to -6.5 dB.
- **Added, not scaled.** Inside that core the added power is roughly the same over dark and bright ground (0.37 to 0.64 in linear units), so dark ground rises most (13.7 dB) and bright ground least (10.7 dB). A wetter surface would not do this.
- **Two frequencies, same pass.** In a box inside the patch (71.30 to 71.45 E, 34.10 to 34.28 N), HV at 1239 MHz (frequency A) reads 0.3 dB against -13.3 to -14.8 dB on the other dates, while HV at 1293.5 MHz (frequency B) reads -11.7 dB against -13.1 to -14.4 dB. A farmland box away from the patch agrees between the two frequencies to within 0.6 dB on every date. In the box, HV at 1239 MHz is 5.1 dB above HH on 2 July, where on every other date it sits 7.9 to 9.2 dB below. The ground cannot rise about 14 dB at one frequency and about 2 dB at a frequency 55 MHz away, so that 12 dB split between the frequencies rules out the ground. It does not by itself rule out an instrument fault.
- **Stable control.** Peshawar city sits at the patch's edge: HH on 2 July is 3.8 dB, in family with every other date, and HV is 2 to 3 dB above its usual value. The control near Hazro, outside the patch, shows no such jump.
- **Metadata does not help.** `inputDataExceptionMask` is zero everywhere, and `rfiLikelihood` is out of its documented range on every date, so the conclusion rests on the pixels.

Reproduce with `processing/checks/july2.py`.

What follows from this: the 2 July HV frame must not be read over the western area, the composite leaves out every flagged date, the grey scale leaves out 2 July, and site curves show that date's HV as it is, with the flag.

### Stability of the stack

- **Grids.** All files share one grid. Cross-correlation of HH at 30 m against 26 July gives shifts of at most 3 m on every date at three places (`processing/checks/shifts.py`). That includes 14 July, the forecast-orbit file, so no shift was seen on that date; the caution stays because of the file's own accuracy code.
- **Urban controls.** See the table below. They move by 1.3 dB or less apart from the 2 July HV reading at Peshawar. This may indicate that changes well above that are not drift in the stack, but it is a weak limit: the 1.3 dB comes after dropping a first control at 2.13 dB, and a farmland box about 15 km across spans 2.9 dB in HH over the season. A change under about 3 dB at one site needs other support.
- **Scene-wide swings.** The median HH of the whole window is 0.5 to 1 dB lower on some dates (14 July, 31 August, 24 September) than on the others. The urban controls do not show this, and water is darker on the same dates. This may be weather (drier ground and calmer water), but it was not tested. Do not read a change of about 1 dB at a single site as a real signal.

### Sites

Spread is maximum minus minimum over the dates built. "No 2 Jul" leaves that date out.

| Site | Role | HH spread | HH, no 2 Jul | HV spread | HV, no 2 Jul |
|---|---|---|---|---|---|
| Peshawar city | Stable urban control | 0.71 | 0.71 | 2.85 | 0.93 |
| Built-up area near Hazro | Stable urban control, outside the 2 July interference | 1.29 | 1.29 | 1.12 | 1.12 |
| Tarbela Reservoir, main pool | Permanent water control | 1.46 | 1.46 | 1.38 | 1.38 |
| Tarbela Reservoir, south-east shore | Reservoir shoreline | 10.72 | 10.72 | 6.60 | 6.60 |
| Plain west-north-west of Swabi | Plain area, rises in August and falls part way by October | 6.10 | 6.10 | 5.24 | 5.24 |
| Plain east of Mardan | Plain area, rises from July to late September | 6.44 | 6.44 | 5.47 | 5.47 |
| Indus River near Attock | River stretch | 8.02 | 8.02 | 5.63 | 5.63 |

A first second control, a bright cluster west of Mardan (72.0175, 34.1902), was rejected: its HH spread on all dates was 2.13 dB, because of one reading on 6 October about 1.5 dB above the rest. Other points on that plain rose on the same date. The site near Hazro was then picked as the steadier one, so its spread may flatter the stack. Controls were checked against limits of 2 dB (urban) and -12 dB (water), and all passed without 2 July.

### OPERA DSWx-S1 water check

Public OPERA DSWx-S1 WTR tiles (`OPERA_L3_DSWX-S1_V1`, PO.DAAC, 30 m) were downloaded on 2026-11-02 to `data/opera/` (git-ignored) by `processing/checks/opera_fetch.py`, and compared by `processing/checks/opera_compare.py`. The catalogue has no tile over this window between 28 June and 15 September 2026, so nothing can be checked in the monsoon peak. Classes are the ones in `processing/sartale/config.py`: 1 open water and 3 inundated vegetation count as water; 250, 251 and 255 are excluded. The real tiles held exactly the classes 0, 1, 3, 250, 251 and 255. The NISAR mask is HH below -12.1 dB and HV below -18.8 dB, thresholds set on the main Tarbela pool on 26 July, a date not compared. DSWx comes from Sentinel-1 at a different time and look, so days apart are stated.

| NISAR date | DSWx date | Days apart | Pixels compared | Agreement | Calling all dry would score | Water found (recall) | Radar low that is DSWx water (precision) | IoU | Tarbela box: agreement, baseline, IoU |
|---|---|---|---|---|---|---|---|---|---|
| 12 Sep | 15 Sep | 3 | 20,336,660 | 0.983 | 0.980 | 0.81 | 0.56 | 0.50 | 0.984, 0.814, 0.92 |
| 12 Sep | 16 Sep | 4 | 17,658,526 | 0.982 | 0.980 | 0.78 | 0.54 | 0.47 | 0.982, 0.798, 0.91 |
| 24 Sep | 23 Sep | 1 | 12,512,871 | 0.981 | 0.973 | 0.90 | 0.61 | 0.57 | 0.984, 0.814, 0.92 |
| 6 Oct | 5 Oct | 1 | 12,508,890 | 0.970 | 0.974 | 0.89 | 0.45 | 0.43 | 0.981, 0.815, 0.90 |
| 18 Oct | 17 Oct | 1 | 12,510,765 | 0.986 | 0.975 | 0.82 | 0.69 | 0.60 | 0.983, 0.815, 0.91 |

Dates before 12 Sep have no useful partner: the nearest tile to 2 Jul is 28 Jun, 4 days away but on the interference date, and the nearest to 14 Jul is 16 days away. On 6 Oct whole-window agreement is below the all-dry score, because more dry ground fell below the thresholds that day.

Read this with care. Most of the window is dry, so calling everything dry would already score about 97 to 98 percent: **whole-window agreement says little**. Recall and IoU, and the Tarbela box, are the useful numbers. The radar mask also marks smooth dry ground, which is why it finds more low pixels than DSWx has water pixels. The thresholds suit large still water and were not tuned for rivers.

Water share inside the 150 m radius of two sites follows the curves. Tiles are warped to the NISAR grid by nearest neighbour, and each cell gives pixels marked water of valid pixels.

| Site | 28 Jun | 15 Sep | 16 Sep | 23 Sep | 5 Oct | 17 Oct |
|---|---|---|---|---|---|---|
| Tarbela south-east shore | 0 of 79 | 74 of 79 | 60 of 68 | 25 of 79 | 0 of 79 | 0 of 79 |
| Indus near Attock | 77 of 80 | 61 of 80 | 62 of 80 | 48 of 80 | 40 of 80 | 11 of 80 |
| Tarbela main pool (control) | 81 of 81 | 81 of 81 | 81 of 81 | 81 of 81 | 81 of 81 | 81 of 81 |

On that support, and only for what they state, the Tarbela shore and Indus cards carry "Reference agrees". Neither reference says what the surface was on a NISAR date itself.

### Flood Forecasting Division bulletins

Source: Flood Forecasting Division (FFD), Pakistan Meteorological Department, daily flood bulletins, https://ffd.pmd.gov.pk/bulletin (read 2026-11-02). Figures are at 06:00 PST, in thousands of cusecs for flow. Bulletin numbers are 018/26 (2 Jul), 030/26 (14 Jul), 035/26 (19 Jul), 038/26 (22 Jul), 039/26 (23 Jul), 042/26 (26 Jul), 066/26 (19 Aug), 078/26 (31 Aug), 090/26 (12 Sep), 102/26 (24 Sep), 114/26 (6 Oct) and 124/26 (15 Oct, the last of the season, so no bulletin exists for 18 Oct).

Kabul River at Nowshera, with the NISAR passes marked:

| Date | Flow | Note |
|---|---|---|
| 2 Jul | 49.9 | NISAR pass |
| 14 Jul | 41.1 | NISAR pass |
| 19 Jul | 32.6 | |
| 21 Jul | 42.4 | |
| 22 Jul | 66.6 | Low flood level |
| 23 Jul | 78.5 | Low flood level. Highest figure listed for the 2026 flood season, still listed on 15 Oct |
| 24 Jul | 74.6 | Low flood level |
| 25 Jul | 70.3 | Low flood level |
| 26 Jul | 53.5 | NISAR pass. Not listed in flood in that bulletin's summary |
| 27 Jul | 48.3 | Last reading before the gap starts at 22:03 UTC |
| 28 Jul to 9 Aug | 38.0 to 57.8 | Inside the data gap. Highest on 5 Aug. The bulletins' summaries do not list this gauge in flood |

So the river's rise of late July fell between the 14 and 26 July passes, **before the data gap and not inside it**. The 26 July pass, at about 05:22 Pakistan time, came three days after the highest reading. The gap itself holds no reading above 57.8. A press report dated 27 July (The Nation, "Fresh spell of rainfall increases water flows in Kabul, Indus rivers across KP") describes a low-level flood at Nowshera, and Radio Pakistan on 25 July cites NDMA on low-level flooding there. Neither adds a number. No PDMA report of this rise was found.

The table for 20 Jul could not be read from the PDF, so that day is left out.

Indus at Kalabagh, the next gauge downstream of Attock, inflow in thousands of cusecs: 26 Jul 334.2, 19 Aug 342.5, 31 Aug 253.0, 12 Sep 176.6, 24 Sep 138.2, 6 Oct 86.8, 15 Oct 50.6. It also carries the Kabul, so it shows the direction of the river, not the level at the site.

Tarbela reservoir level, feet:

| Date | Level | |
|---|---|---|
| 2 Jul | 1458.85 | NISAR pass |
| 14 Jul | 1501.53 | NISAR pass |
| 26 Jul | 1528.11 | NISAR pass |
| 19 Aug | 1550.00 | NISAR pass, maximum conservation level |
| 31 Aug | 1550.00 | NISAR pass |
| 12 Sep | 1545.30 | NISAR pass |
| 24 Sep | 1531.10 | NISAR pass |
| 6 Oct | 1520.04 | NISAR pass |
| 15 Oct | 1518.80 | Last bulletin, 3 days before the 18 Oct pass |

### Before-and-after step layer (the main Change view)

Numbers from `processing/checks/step_evidence.py` on 2026-11-02. Built by `run_pipeline change` (also part of `rebuild`) from the 30 m COGs.

**Verdict.** With HH and HV moving the same way, a mean step of at least 3 dB and a stability of at least 3.0, the step layer is enough to separate the known changes from the controls (0 to 1% of control pixels, against 90% at the Tarbela shore around 19 Aug and 88% at Attock around 24 Sep within 150 m), but it cannot say what changed, because plain ground flags as strongly (35 to 68%) with no named cause, and the Unusual dates layer alone is still not enough to place a lasting change.

A step is a change in backscatter. It does not name a cause, and land cover here is not established.

**Why this layer exists.** The z-score layer (next section) judges a date against the season, so a pixel that stays dark for most of the season has dark as its usual state and the shore does not stand out in August. A step test asks when the season split into a before and an after, so that problem goes away. The idea and a first prototype came from the team's coordinator, who had seen the known sites. That prototype used HH with no scene normalisation and no stability test. Its "13 km" box near 71.925, 34.275 read 6 km across in the code; both sizes are reported here.

**Method.** Scene offsets are removed, then linear power is averaged once more, 3 x 3, to 90 m, because a split chosen from several needs quieter pixels. The test uses eight dates: 2 Jul is left out, and 14 Jul is in, keeping its flag, because without it no step before 31 Aug could be placed. For each pixel, every split with at least 2 valid dates on each side is tried, and the one with the largest joint stability of HH and HV is kept, so both polarizations report one date. A step is mean dB after minus mean dB before. Stability is |step| over its standard error, from the scatter inside the two segments: a two-sample t statistic, with the scatter floored at 0.5 dB, about what the controls show at 90 m (0.41 to 0.44 dB). A pixel with fewer than 4 valid dates has no score. The date given is the first date after the step, so it fell between that pass and the one before.

**What choosing the best split inflates.** Dates were shuffled per pixel, which keeps a pixel's values and removes their order. Against one fixed split, the best of five doubles the median step (0.55 to 1.14 dB in HH on the plain box, 0.20 to 0.40 on stable ground) and raises the 99th percentile about 1.4 times (2.99 to 4.16 dB). The stability 99th percentile goes from 3.33 to 4.88 on the plain box. So a size limit alone is not safe: HH of at least 3 dB would fire on about 1% of shuffled pixels at one fixed split, and more at the best of five.

**The rule.** A pixel is flagged where HH and HV move in the same direction at the split, their mean |step| is at least 3 dB, and the root mean square of their stabilities is at least 3.0. The size limit is the project's standing limit that a change under about 3 dB at one site needs other support. The stability limit is computed in `build_change`: the smallest multiple of 0.5 that leaves at most 1% of control pixels (293 pixels within 500 m of the three controls) and 1% of shuffled pixels in the plain box passing both limits (2.95, rounded to 3.0). The shuffle is seeded, so a rebuild repeats it.

**This rule was not blind, and it changed.** The first rule took the 99th percentile of each limit separately, on the smaller of HH and HV. That came to 3.5 dB and 4.0, and I then saw it flag 13% at the shore and 5% east of Mardan within 450 m. Looking at why, two faults showed up that do not depend on the sites: 1% on each limit compounds to about 0.08% together, far stricter than meant, and asking each polarization to pass alone loses steps that are weaker in HV. I replaced it with one joint 1% budget and chose how to combine HH and HV on synthetic steps added to shuffled plain pixels, with no known site involved. The choice still followed seeing the sites, so treat the limits as chosen with the known sites in view. Both results are given below.

**Combining HH and HV.** Best limits with shuffled false alarms at most 1% on the plain box, and the share of synthetic steps found:

| Rule | Best limits | False alarms | 5 dB in both | 5 dB HH, 3 dB HV | Mean over all sizes |
|---|---|---|---|---|---|
| Each polarization passes alone | 2.5 dB, 3.0 | 0.69% | 90% | 61% | 63% |
| Mean size, RMS stability, same direction (used) | 3.0 dB, 3.5 | 0.70% | 91% | 79% | 68% |
| HH only | 3.5 dB, 3.0 | 0.92% | 90% | 90% | 70% |
| Either polarization | 3.5 dB, 3.5 | 0.91% | 93% | 87% | 71% |

The grid's best stability limit for the rule used is 3.5 because 3.0 sat just above 1% in that draw; the build's own seeded shuffle lands at 3.0, with false alarms of 1.0%. HH only and either score slightly higher, but they do not ask the two polarizations to agree. Where either polarization passes on the real data, they agree in direction at 96.5% of pixels. On the real data at the same limits, the rule flags 1.39% of the window against 2.54% for either polarization, 8.5% of the plain box against 12.6%, and 52% at Attock within 450 m against 61%. Asking each to pass alone would give 30% at Attock and 32% east of Mardan. HV is the weaker: at Attock alone it passes at half the rate of HH.

**False alarms under shuffles, percent.**

| Limits | Stable ground | Plain box | Box at 71.925, 13 km | Whole window |
|---|---|---|---|---|
| 3.0 dB, 3.0 (rule) | 0.001 | 1.006 | 0.459 | 0.253 |
| 2.5 dB, 3.0 | 0.002 | 1.784 | 0.803 | 0.492 |
| 3.5 dB, 4.0 | 0.000 | 0.261 | 0.094 | 0.077 |

A per-pixel shuffle breaks up patches, which real weather does not. So the dates were also shuffled together, in one order for all pixels, 200 times. At the rule the plain box flags a median of 0.38%, 3.5% at the 90th percentile and 6.9% at most; the whole window 0.15%, 0.72% and 1.26%. The real order flags 8.5% and 1.39%, more than any of the 200 orders.

**Percent of 90 m pixels flagged.**

| Area | Pixels | 3.0 dB, 3.0 (rule) | 2.5 dB, 3.0 | 3.5 dB, 4.0 | Main step dates |
|---|---|---|---|---|---|
| Peshawar, 500 m (control) | 99 | 0.0 | 0.0 | 0.0 | none |
| Hazro, 500 m (control) | 96 | 1.0 | 1.0 | 1.0 | one pixel |
| Tarbela pool, 1 km (water control) | 387 | 0.0 | 0.0 | 0.0 | none |
| **Tarbela shore, 150 m** | 10 | **90** | 90 | 90 | all down, 19 Aug |
| Tarbela shore, 450 m | 78 | 27 | 28 | 27 | all down, 19 Aug |
| **Attock, 150 m** | 8 | **88** | 88 | 75 | up: 24 Sep 57%, 6 Oct 29%, 12 Sep 14% |
| Attock, 450 m | 79 | 52 | 56 | 39 | up: 24 Sep 68%, 12 Sep 20%, 6 Oct 12% |
| Plain near Swabi, 450 m | 79 | 35 | 41 | 28 | all up, 19 Aug |
| Plain east of Mardan, 450 m | 79 | 68 | 78 | 38 | up: 19 Aug 46%, 31 Aug 39% |
| Plain box, 72.10 to 72.25 E | 34,502 | 8.5 | 13.4 | 3.8 | up: 19 Aug 41%, 24 Sep 23% |
| Box at 71.925, 6 km | 4,489 | 1.4 | 2.7 | 0.6 | mixed |
| Box at 71.925, 13 km | 20,880 | 3.4 | 6.0 | 1.4 | up: 6 Oct 34%, 12 Sep 22% |
| Tarbela box | 114,707 | 0.8 | 1.1 | 0.4 | down 19 Aug 22%, up 19 Aug 20%, up 6 Oct 19% |
| Attock box | 18,868 | 5.0 | 6.9 | 3.3 | up: 24 Sep 37%, 6 Oct 25%, 12 Sep 17% |
| **Whole window** | 2,814,517 | **1.39** | 2.30 | 0.65 | up 19 Aug 39%, up 12 Sep 17%, up 6 Oct 10%, down 24 Sep 8% |

Only about 20% of flagged pixels in the window step down. The steady ground of a control barely moves: its 99th percentile mean step is 1.8 dB.

**Sites, from each site's own curve.** The card shows these, so they can be read off the chart.

| Site | Step between | HH | HV | Stability | Passes | Map pixels flagged |
|---|---|---|---|---|---|---|
| Peshawar city | 24 Sep, 6 Oct | -0.23 | -0.28 | 0.6 | No | 0% |
| Near Hazro | 19, 31 Aug | -0.73 | -0.79 | 2.1 | No | 0% |
| Tarbela pool | 24 Sep, 6 Oct | -0.53 | +0.18 | 0.0 | No | 0% |
| Tarbela shore | 26 Jul, 19 Aug | -8.14 | -5.26 | 6.1 | Yes | 90% |
| Plain near Swabi | 26 Jul, 19 Aug | +3.75 | +3.03 | 3.8 | Yes | 27% |
| Plain east of Mardan | 19, 31 Aug | +3.84 | +2.24 | 4.4 | Yes | 44% |
| Indus at Attock | 12, 24 Sep | +4.82 | +3.00 | 6.1 | Yes | 88% |

**What a single split misses.** The shore's second step is missed. After August it climbs by HH +3.10 dB and HV +1.43 dB between 12 and 24 Sep, a mean of 2.3 dB, stability 5.4: stable, but under the size limit even when tested alone. In the window only 1.4% of flagged pixels show a second step by the same rule. Short pulses are also missed: of 42 pixels in the Tarbela box that went dark in August and came back by late September, 7% are flagged, because a before and an after cannot describe a return. The Unusual dates view catches many of those.

**How firm are the steps?**

- **One date.** Dropping any one date from 19 Aug on keeps 86 to 90% of flagged pixels, except 6 Oct (71%) and 18 Oct (78%). Dropping a July date keeps 46 to 51%. That is partly built in: a step at 19 Aug has only those two dates before it, so without either the split cannot exist. For the same reason the shore cannot be tested this way, and its step rests on two dates, one of them the flagged 14 Jul. 24% of flagged pixels survive every single drop.
- **14 July.** It still reads low on plain ground after normalising. With 1 dB more added to it, 73% of flagged pixels stay flagged in the window and 71% in the plain box, and 100% at the shore. So some of the step-ups at 19 Aug come from that date.
- **Mardan.** Its strong signal is not the 6 Oct patch: the site is south of the patch, dropping 6 Oct keeps 89% of its flagged pixels, and no date from 19 Aug on keeps fewer than 89%. The two July dates keep 50% and 65%, as above. Its date is rough: 19 and 31 Aug split it almost evenly, and a straight line fits 26% of its flagged pixels better than a step. It is a real rise, more gradual than a step, and its cause is unknown.
- **6 October.** The unexplained brightening does make steps. In the patch, 33% of flagged pixels are dated up at 6 Oct, and only 44% survive dropping that date. Treat those steps as weak.
- **Step or slope?** A line fits better at 15% of flagged pixels in the window, 42% at Attock, 0% at the shore. Where a slope fits, a date is only a rough middle.

**Display.** `frames/step_date.webp`, 16 KB, lossless. Hue is the date, the light tint is up, the deep shade is down. Lossy WebP would blur small patches and bilinear warping would invent colours between dates, so classes are warped by nearest neighbour. The map's image layer has no mipmaps, so a fine frame loses patches at the default zoom. Instead each 270 m cell is drawn in its commonest class if at least 2 of its 9 pixels are flagged: lone pixels drop out and small patches stay, drawn a little wider than measured (2.7% of cells against 1.39% of pixels). COGs at 90 m: `data/cog/change_step_HH.tif`, `_HV`, `_stability` (0 where HH and HV disagree in direction) and `_split` (position in the eight dates).

**Checks added when the app copy was written (2 Nov 2026).** These back statements the app makes about the step map.

- **Not drawn.** Rebuilding the frame's cell rule from the 90 m COGs (`change_step_HH`, `_HV`, `_stability`, `_split`) gives 39,096 flagged pixels, 1.39% of those scored, of which 12,196 (31%) lie in 270 m cells that are not drawn, because fewer than 2 of the cell's 9 pixels are flagged. A further 12% of flagged pixels lie in a drawn cell but take the colour of the cell's commonest class, so 43% are not drawn in their own class. The app says the 31%. The check was a short script run once and is not kept in `processing/checks/`.
- **Fresh cities.** A reviewer ran the rule on five cities that played no part in setting the limits: 0% of pixels flagged within 450 m. The cities are not named here and the script is not in the repository, so this check is reported, not reproduced by us. The three controls (Peshawar, Hazro, the Tarbela pool) were used in setting the stability limit, so their quiet is partly built in.
- **Card against map.** A site card judges the site's averaged curve (mean dB inside the 150 m circle, then the same limits). The map judges each 90 m pixel, which is stricter, so a card can pass where few map pixels do. Percentages of map pixels within 150 m rest on 8 to 10 pixels and are not quoted; the card quotes the share within 450 m and its pixel count (the table above).

### Unusual dates layer (z-scores)

This is the secondary view. Its verdict below still stands for what it is: it cannot place a lasting change, which is why the step layer above is the main one. It still catches short pulses the step layer misses.

Numbers from `processing/checks/change_evidence.py` on 2026-11-02. The layer is built by `run_pipeline change` (also part of `rebuild`) from the 30 m COGs. No deep learning is used.

**Verdict.** At a threshold of 3.5 the layer is not enough on its own: controls stay quiet (at most 6.2% of control pixels on any date, 0% in the Tarbela pool) and the Attock river stands out as its curve rises (37.5% on 18 Oct), but the Tarbela shore does not stand out on 19 or 31 Aug (1.3% and 2.5%, against 73 to 77% on the July dates) and plain ground flags as strongly as the known changes, so it can show which dates are odd for a pixel but not when a lasting change happened or why.

**Method.** For each date and pixel, in HH and in HV: the distance from the median of the season's other baseline dates, divided by a robust scale of those dates. The score is the larger of the two. So a date is never in its own baseline. The scale is 1.4826 x the median absolute deviation, with a floor of 1 dB, because six dates give a noisy spread and about 1 dB is meaningless at a site. This is the modified z-score of Iglewicz and Hoaglin (1993), per pixel. A pixel with fewer than 4 valid baseline dates has no score. Linear averaging happens at multilooking; all these statistics are in dB after multilooking.

**Dates.** Baseline: 26 Jul, 19 Aug, 31 Aug, 12 Sep, 24 Sep, 6 Oct, 18 Oct, so six dates behind each score. 2 Jul is excluded entirely: no score, no frame, not in any baseline. 14 Jul stays out of the baseline and is scored against all seven, keeping its flag.

**Why not distmetrics.** `distmetrics` 1.0.8 (Apache-2.0, confirmed from the package's `LICENSE.txt` and conda-forge metadata, https://github.com/opera-adt/distmetrics) was read, not installed. Its package `__init__` imports the transformer and search code, so importing even the Mahalanobis function brings PyTorch and `asf_search`. A conda dry run added 64 packages and a 2.4 GB download, and replaced one installed package. Its functions take VV and VH arrays, but nothing in the maths needs those polarizations, so HH and HV would work. CuSum documents linear gamma-0 as its assumed input and offers a dB transform. The Mahalanobis floor (`eig_lb`, about 1.4e-4) suits linear or logit values, so dB would need a new floor, and it uses a mean and covariance, not robust statistics, while `get_spatiotemporal_mu` drops its `window_size` argument. The sums are short, so `processing/sartale/change.py` does them with numpy, and nothing is added to `environment.yml`.

**Alternatives tried on the same data and left out.** A full Mahalanobis form with a correlation from the same dates had a control 99th percentile of 4.33, and at thresholds around that value it flagged no more of the known changes and about the same share of the plain box. The larger z-score is simpler to explain. Smoothing the scale over 5 x 5 pixels raised the control 99th percentile from 3.46 to 3.61 and lowered the Attock site's scores, so the floor alone is used. CuSum in date order peaked at a median of 4.7 at the Tarbela shore, but 4.3 east of Mardan and 3.6 near Swabi, against 2.0 to 2.3 at the controls, so it does not separate known change from plain ground either and is not used.

**Scene drift.** Each date's offset is the median, over stable pixels, of that date minus the median of the other baseline dates. Stable pixels are the lowest quarter of temporal spread in both polarizations, about 2.0 million pixels. Comparing with the other dates matters: against a median that includes the date, the result sits near zero because each pixel's median is often that date's own value. Removed, in dB:

| | 14 Jul | 26 Jul | 19 Aug | 31 Aug | 12 Sep | 24 Sep | 6 Oct | 18 Oct |
|---|---|---|---|---|---|---|---|---|
| HH | -0.59 | 0.15 | 0.03 | -0.17 | 0.11 | -0.14 | -0.12 | 0.12 |
| HV | -0.60 | 0.12 | -0.02 | 0.04 | 0.00 | -0.08 | -0.08 | 0.03 |

Only 14 Jul moves much on stable ground. The 0.5 to 1 dB swings of the whole-window median on 31 Aug and 24 Sep are mostly not in stable pixels, so this step does not remove them from variable ground: the plain box's median still reads about 0.6 dB low on 31 Aug after this step.

**Threshold: 3.5.** The 99th percentile of the 1,928 control pixel scores (Peshawar, Hazro and the Tarbela pool, within 150 m, all eight scored dates) is 3.46, rounded up to the next 0.5. It is computed in `build_change`, from the controls only. The shared display scale runs from 3.5 to 7.

Percent of 30 m pixels above 3.5:

| Area | 14 Jul | 26 Jul | 19 Aug | 31 Aug | 12 Sep | 24 Sep | 6 Oct | 18 Oct |
|---|---|---|---|---|---|---|---|---|
| Peshawar, 150 m | 6.2 | 1.2 | 0.0 | 6.2 | 0.0 | 0.0 | 2.5 | 1.2 |
| Peshawar, 500 m | 3.3 | 3.2 | 0.1 | 3.2 | 0.5 | 0.0 | 0.6 | 0.3 |
| Hazro, 150 m | 1.3 | 1.3 | 0.0 | 2.5 | 0.0 | 0.0 | 0.0 | 0.0 |
| Hazro, 500 m | 4.7 | 1.6 | 0.8 | 2.5 | 0.8 | 0.6 | 0.3 | 0.5 |
| Tarbela pool, 150 m | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Tarbela pool, 1 km | 0.0 | 0.1 | 0.1 | 0.1 | 0.0 | 0.0 | 0.4 | 0.0 |
| **Tarbela shore, 150 m** | 77.2 | 73.4 | **1.3** | **2.5** | 0.0 | 0.0 | 6.3 | 7.6 |
| **Indus at Attock, 150 m** | 2.5 | 0.0 | 1.2 | 0.0 | 0.0 | 10.0 | 26.2 | 37.5 |
| Plain east of Mardan, 150 m | 35.4 | 34.2 | 16.5 | 1.3 | 1.3 | 10.1 | 1.3 | 5.1 |
| Plain near Swabi, 150 m | 27.8 | 43.0 | 2.5 | 3.8 | 2.5 | 3.8 | 2.5 | 8.9 |
| Plain box, 72.10 to 72.25 E, 34.10 to 34.28 N | 11.4 | 6.1 | 3.4 | 3.4 | 0.9 | 1.0 | 8.1 | 2.7 |
| Whole window | 3.9 | 2.7 | 1.4 | 1.7 | 0.7 | 0.5 | 2.3 | 1.3 |

Sensitivity, worst date for each:

| Threshold | Peshawar 150 m | Hazro 150 m | Pool 150 m | Plain box | Shore 19, 31 Aug | Attock 18 Oct |
|---|---|---|---|---|---|---|
| 3.0 | 8.6 | 6.3 | 1.2 | 17.4 | 3.8, 5.1 | 52.5 |
| 3.5 | 6.2 | 2.5 | 0.0 | 11.4 | 1.3, 2.5 | 37.5 |
| 4.0 | 4.9 | 2.5 | 0.0 | 7.5 | 1.3, 1.3 | 27.5 |

No threshold near these values changes the result for the shore.

**Site scores** are the median pixel score within 150 m, so a site can have many pixels above 3.5 while its typical pixel is below it:

| Site | 14 Jul | 26 Jul | 19 Aug | 31 Aug | 12 Sep | 24 Sep | 6 Oct | 18 Oct |
|---|---|---|---|---|---|---|---|---|
| Peshawar city | 1.22 | 1.22 | 0.81 | 1.28 | 0.70 | 1.19 | 0.91 | 0.79 |
| Near Hazro | 1.29 | 0.99 | 0.99 | 1.06 | 0.99 | 0.72 | 0.84 | 0.79 |
| Tarbela pool | 0.88 | 0.92 | 0.86 | 1.00 | 0.86 | 0.94 | 1.16 | 0.97 |
| Tarbela shore | 5.39 | 4.43 | 1.17 | 1.52 | 0.90 | 0.79 | 0.90 | 1.49 |
| Plain near Swabi | 2.28 | 2.78 | 1.62 | 1.30 | 1.03 | 0.95 | 1.25 | 1.58 |
| Plain east of Mardan | 3.04 | 2.73 | 2.02 | 0.88 | 0.73 | 1.64 | 1.11 | 1.28 |
| Indus at Attock | 1.85 | 1.08 | 1.05 | 0.79 | 0.99 | 1.67 | 2.40 | 3.08 |

**Known changes.**

- **Tarbela shore: fails on the dates asked.** It scores 1.17 on 19 Aug and 1.52 on 31 Aug, like a control. It scores 5.39 and 4.43 on 14 and 26 Jul. HH is -6.1 and -7.6 dB on those two dates and -12.8 to -16.8 dB on the six dates after them, so dark is this pixel's usual state and the bright July dates are the odd ones. The curve's 9 dB step between 26 Jul and 19 Aug is real, but a season-only baseline cannot place it. Adding the excluded dates would not help: scoring 19 Aug against the eight other dates, using the curve as it stands, gives about 0.8, because the season has two states. A pre-monsoon baseline would be needed, and the stack starts on 2 Jul.
- **The rest of the shore.** In the Tarbela box, 2,390 pixels were bright on 26 Jul (HH above -10 dB) and dark on 19 and 31 Aug (HH below -13 dB). Of these, the 1,096 that were not dark on any of 24 Sep, 6 Oct or 18 Oct had 35%, 50% and 25% above threshold on 19 Aug, 31 Aug and 12 Sep, and about 3% in July. The 627 that stayed dark on all three had 57% and 76% on 14 and 26 Jul and at most 6% in August. So the layer marks the August water only where it left again quickly. These groups were selected on those dates, so high scores on them are partly built in; this describes the behaviour and does not test it.
- **Attock: passes.** Its score moves as the curve did, flat from 26 Jul to 12 Sep, then 1.67, 2.40 and 3.08, with 10%, 26% and 37.5% of pixels above threshold. The typical pixel stays under 3.5, again because the later dates form a large part of its baseline.

**Plain ground.** The plain box reaches 11.4% above threshold on 14 Jul and 8.1% on 6 Oct, and 0.9 to 6.1% on other dates. The two plain sites reach 35% and 43%, as much as Attock on its best date. A high score on plain ground says little on its own, and the cards say so.

**OPERA DSWx-S1, inside two boxes and on dates with tiles only.** A DSWx change is a pixel whose water state on the tile differs from the majority of the other three tiles (15, 23 Sep, 5, 17 Oct). "Flagged water-like" is above threshold and water-like by the mask in "OPERA DSWx-S1 water check" on the date but not in the other dates' median, or the reverse. Tarbela box 72.60 to 72.90 E, 34.00 to 34.30 N (977,898 pixels), Attock box 72.15 to 72.32 E, 33.87 to 33.96 N (168,556 pixels).

| Box | NISAR date, DSWx date | Pixels DSWx changed | Flagged water-like | Of those, DSWx changed | Of DSWx changes, flagged |
|---|---|---|---|---|---|
| Tarbela | 12 Sep, 15 Sep | 1.3% | 689 | 28.2% | 1.5% |
| Tarbela | 24 Sep, 23 Sep | 0.8% | 208 | 1.9% | 0.0% |
| Tarbela | 6 Oct, 5 Oct | 0.8% | 2,088 | 28.6% | 7.5% |
| Tarbela | 18 Oct, 17 Oct | 0.9% | 3,856 | 39.5% | 16.7% |
| Attock | 12 Sep, 15 Sep | 3.0% | 76 | 2.6% | 0.0% |
| Attock | 24 Sep, 23 Sep | 2.4% | 627 | 33.0% | 5.1% |
| Attock | 6 Oct, 5 Oct | 2.4% | 2,678 | 31.0% | 20.1% |
| Attock | 18 Oct, 17 Oct | 3.2% | 4,216 | 44.5% | 34.8% |

On six of eight rows a flagged water-like pixel is many times likelier than chance to be a DSWx change, but most DSWx changes are not flagged and most flagged pixels are not DSWx changes. Tiles differ by 1 to 3 days and in look geometry, and there is no tile for 19 or 31 Aug, so OPERA cannot test the August step.

**Interference and 6 October.** 2 Jul is in no baseline, has no frame and no score COG, and every site's score on it is null (a test also shows that wild 2 Jul values change no output). The rejected cluster west of Mardan (72.0175, 34.1902) is not flagged on 6 Oct: 3.8% within 150 m, with a median score of 1.5. The rise it belonged to does show as patches: the largest, 71.82 to 72.15 E and 34.29 to 34.46 N, reads 1.9 dB in HH and 1.4 dB in HV above the other dates, with 10.7% of pixels flagged, and 10 km cells reach 20% on that date against a median of 1.5%. Unlike 2 July it is in both polarizations and agrees between frequencies: box means on 6 Oct are -1.52 dB in HH at both 1239 and 1293.5 MHz (-3.35 to -4.82 dB on other dates), and -11.88 and -11.73 dB in HV. That argues against narrow-band interference. Wet ground is a possible cause, but no rain record was compared, so the app calls it unexplained.

**Reading the frames.** Web frames average the 30 m score in 2 x 2 blocks, then apply the threshold, so isolated pixels fade and the map shows fewer than the shares above. The eight frames total 2.8 MB. Score COGs are `data/cog/change_<date>.tif`.

## Lake Watch sources (added 2 Nov 2026)

Lake Watch (`lakes.json`, per-lake images) is built by `run_pipeline lakes-search`, `lakes-fetch`, `lakes-build` and `lakes-check`. OpenStreetMap is **not used** by Lake Watch.

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| NISAR GCOV via HTTPS range reads (ASF, `NISAR_L2_GCOV_PROVISIONAL_V1`, CRID `P05023`, mode 4005, DHDH, Frequency A, HHHH and HVHV) | Small windows (6 km) read from each pass over HTTPS range requests, 232 passes, about 5.4 GB in total. Whole files are not downloaded. Passes from 2026-06-17 only. Windows are cached in `data/lakes/` (git-ignored); only derived data is committed | NASA data, openly available. Provisional product, not validated. Exact citation wording: terms not confirmed | 2026-11-02 |
| HMAGLOFDB (https://github.com/fidelsteiner/HMAGLOFDB) | Coordinates of four lakes (Rogheli, Yarkhun, Shazore, Bindo Gol), each with the event date recorded in `processing/lakes_in.json` | CC0 1.0 Universal (read from the repository's `LICENSE` file) | 2026-11-02 |
| Shrestha et al. 2023, ESSD 15:3941 | Table 3 coordinates for Khurdopin, Ghulkin, Karambar and Batura | CC BY 4.0 (stated on the journal article page). Attribution required | 2026-11-02 |
| Muhammad et al. 2021, doi 10.1080/19475705.2021.1975833 | Shisper map frame (36 21-22 N, 74 34-36 E, Fig. 2) used to place the Shisper search circle. Only the frame is used, no outline | Journal licence: terms not confirmed. Cited, not redistributed | 2026-11-02 |
| Passu event table, doi:10.1016/j.rcar.2025.03.005 | Coordinate for Passu lake | Journal licence: terms not confirmed. Cited, not redistributed | 2026-11-02 |
| SUPARCO space4climate, GLOF Status Update, 2 Jul 2026 (space4climate.gov.pk) | One quoted sentence (the cloud-cover statement) and the figures cited in the design. Nothing else is copied | Terms not confirmed. Quoted text only, with the source named | 2026-11-02 |
| Sentinel-2 L2A via Earth Search | Optical water cross-check (MNDWI) for Attabad, Khurdopin, Passu and Shisper. Only derived areas are kept | Copernicus Sentinel data terms (free, full and open; attribution "Contains modified Copernicus Sentinel data"). Exact legal notice wording: terms not confirmed | 2026-11-02 |
| Radio Pakistan, 7 May 2022 | Source for the Shisper downstream note (event report). Cited, not copied | Terms not confirmed. Cited only | 2026-11-02 |
| Attabad coordinates | Chosen by the team on 2 Nov 2026 from lake visibility in NISAR passes | Part of this repository, Apache License 2.0 | Not applicable |

Sentinel-2 cross-check result (from `lakes.json`, `checks`): areas were similar only at Attabad, and even there the overlap was low: Attabad radar 0.218 against optical 0.185 km2 (IoU 0.11); elsewhere the areas disagreed widely: Khurdopin 0.036 against 0.885; Passu 0.048 against 0.239; Shisper (no lake expected) 0.087 against 0.288, where optical also flags water. Areas are water inside a search circle and under-count lakes whose shores sit in radar shadow.

SUPARCO quote, verbatim: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days." (space4climate.gov.pk, GLOF Status Update, 2 Jul 2026.)

## Other datasets (planned, not yet used or downloaded)

All of these are listed in the plan (`docs/SARtale-hackathon-plan.md`, section 5). Their licence status has **not** been verified for this project unless stated.

| Dataset | Planned use | Licence status | Access date |
|---|---|---|---|
| OPERA DSWx-HLS | Optical water check | NASA data, openly available. Specific terms to confirm | Not accessed |
| HLS (Harmonized Landsat Sentinel-2) | Crop and vegetation check | NASA data, openly available. Specific terms to confirm | Not accessed |
| NISAR SME2 soil moisture | Stretch goal only. Not fully calibrated | NASA data, openly available. Specific terms to confirm | Not accessed |
| GPM IMERG | Rain timing | NASA data, openly available. Specific terms to confirm | Not accessed |
| OpenStreetMap | Not used by Lake Watch or the Peshawar chapter. Planned only for optional roads, bridges, hospitals and schools overlays (the only overlay in the current build is the hand-entered place labels, not OSM) | ODbL 1.0. Attribution "© OpenStreetMap contributors" is required if used. Share-alike duties to confirm | Not accessed |
| UNOSAT August 2025 flood map | Historical context only | To confirm | Not accessed |
| WorldPop | Rough population near road links | To confirm | Not accessed |
| HydroRIVERS and HydroBASINS (HydroSHEDS) | River and catchment context | To confirm | Not accessed |
| KP C&W, PDMA and PMD data | Not redistributed. Only a few dated FFD figures are quoted with the source named (above). Official warnings are linked, not republished | Not applicable | Not applicable |

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
| requests | 2.34.2 | Apache-2.0 | Yes (`run_pipeline download`) |
| networkx | 3.7 | BSD-3-Clause | Listed, not imported yet (planned road analysis) |
| osmnx | 2.1.1 | MIT | Listed, not imported yet (planned road analysis) |
| Python | 3.12 | Python Software Foundation licence (to confirm the exact text for the conda build) | Yes |

`distmetrics` 1.0.8 (Apache-2.0) was read to decide the change method and is not a dependency; see "Unusual dates layer".

## Still to do

- Confirm the data-use and citation wording for NISAR, OPERA (used now), HLS and IMERG, and whether quoting FFD figures needs anything more than naming the source.
- Confirm UNOSAT, WorldPop and HydroSHEDS terms, or leave them out.
- Record the logo's origin and licence.
- Check the place labels against a map or gazetteer before they are described as anything more than approximate.
