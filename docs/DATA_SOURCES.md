# Data sources and licences

Written 2026-11-01, updated 2026-11-02 after the first calibrated build. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and identify their licences. Where a licence has not been checked, this file says "to confirm" and does not guess. The allowed claims are these: OpenStreetMap data is under the ODbL, and NASA data is openly available.

## Status in one paragraph

**The app shows calibrated NISAR data, labelled Provisional.** It is built by `run_pipeline rebuild` from the verified `P05023` GCOV files of track 84 in `data/gcov/` (git-ignored). The first real build ran on 2026-11-02. OPERA DSWx-S1 tiles and Flood Forecasting Division bulletins were read for the checks below. NASA's browse previews remain reproducible with `run_pipeline preview`, but they are no longer what the app shows. Every dataset under "Other datasets" is **planned and not yet used or downloaded**.

## Data in the repository now

| Item | Source | Licence | Access date |
|---|---|---|---|
| Calibrated web frames, `manifest.json` and `sites.json` (`app/public/data/`) | Made by `run_pipeline rebuild` from NISAR GCOV files (see "NISAR GCOV data" below). 30 m analysis, about 67 m on the map | NASA data, openly available. Exact wording to confirm | 2026-11-02 |
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

All numbers below are from the first real build, 2026-11-02. Scripts were one-off; the working notes hold the full tables. Backscatter is gamma-0 in dB.

### 2 July: likely radio interference in HV

The evidence supports "likely radio interference", so the flag says that. It does not prove the cause: an instrument fault in the HV channel on that pass would look much the same.

- **Where.** A smooth patch over the western area, about 970 km2 where HV is more than 6 dB above the median of the other dates (averaged over 1 km), roughly longitude 71.24 to 71.63, latitude 33.94 to 34.43. It sits against the western edge of the scene and runs across hills, plain and river without following any of them..
- **HV only.** Inside the area with more than 10 dB of excess, HV reads -2.7 dB on 2 July against -14.2 to -15.8 dB on the eight other dates, while HH reads -6.6 dB against -6.6 to -7.9 dB.
- **Added, not scaled.** Inside that core the added power is roughly the same over dark and bright ground (0.37 to 0.64 in linear units), so dark ground rises most (13.7 dB) and bright ground least (10.7 dB). A wetter surface would not do this.
- **One frequency.** In the same box on the same pass, HV at 1239 MHz (frequency A) reads 0.3 dB against -13.3 to -14.8 dB on the other dates, while HV at 1293.5 MHz (frequency B) reads -11.7 dB against -13.1 to -14.4 dB. A farmland box away from the patch agrees between the two frequencies to within 0.6 dB on every date. The ground cannot rise about 14 dB at one frequency and about 2 dB at a frequency 55 MHz away.
- **Stable control.** Peshawar city sits at the patch's edge: HH on 2 July is 3.8 dB, in family with every other date, and HV is 2 to 3 dB above its usual value. The control west of Mardan, outside the patch, shows no such jump.
- **Metadata does not help.** `inputDataExceptionMask` is zero everywhere, and `rfiLikelihood` is out of its documented range on every date, so the conclusion rests on the pixels.

What follows from this: the 2 July HV frame must not be read over the western area, the composite and the grey scale leave out 2 July, and site curves show that date's HV as it is, with the flag.

### Stability of the stack

- **Grids.** All files share one grid. Cross-correlation of HH at 30 m against 26 July gives shifts of at most 3 m on every date at three places. That includes 14 July, the forecast-orbit file, so no shift was seen on that date; the caution stays because of the file's own accuracy code.
- **Urban controls.** See the table below. They move by 1.3 dB or less apart from the 2 July HV reading at Peshawar, so changes well above that are not stack drift.
- **Scene-wide swings.** The median HH of the whole window is 0.5 to 1 dB lower on some dates (14 July, 31 August, 24 September) than on the others. The urban controls do not show this, and water is darker on the same dates. This may be weather (drier ground and calmer water), but it was not tested. Do not read a change of about 1 dB at a single site as a real signal.

### Sites

Spread is maximum minus minimum over the dates built. "No 2 Jul" leaves that date out.

| Site | Role | HH spread | HH, no 2 Jul | HV spread | HV, no 2 Jul |
|---|---|---|---|---|---|
| Peshawar city | Stable urban control | 0.71 | 0.71 | 2.85 | 0.93 |
| Built-up area near Hazro | Stable urban control, outside the 2 July interference | 1.29 | 1.29 | 1.12 | 1.12 |
| Tarbela Reservoir, main pool | Permanent water control | 1.46 | 1.46 | 1.38 | 1.38 |
| Tarbela Reservoir, south-east shore | Reservoir shoreline | 10.72 | 10.72 | 6.60 | 6.60 |
| Plain south-west of Swabi | Field area, rises in August and falls by October | 6.10 | 6.10 | 5.24 | 5.24 |
| Plain east of Mardan | Field area, rises from July to late September | 6.44 | 6.44 | 5.47 | 5.47 |
| Indus River near Attock | River stretch | 8.02 | 8.02 | 5.63 | 5.63 |

A first second control, a bright cluster west of Mardan (72.0175, 34.1902), was rejected: its HH spread on all dates was 2.14 dB, because of one reading on 6 October about 1.5 dB above the rest. Other points on that plain rose on the same date. The site near Hazro was then picked as the steadier one, so its spread may flatter the stack. Controls were checked against limits of 2 dB (urban) and -12 dB (water), and all passed without 2 July.

### OPERA DSWx-S1 water check

Public OPERA DSWx-S1 WTR tiles (`OPERA_L3_DSWX-S1_V1`, PO.DAAC, 30 m) were downloaded on 2026-11-02 to `data/opera/` (git-ignored). The catalogue has no tile over this window between 28 June and 15 September 2026, so nothing can be checked in the monsoon peak. Classes are the ones in `processing/sartale/config.py`: 1 open water and 3 inundated vegetation count as water; 250, 251 and 255 are excluded. The real tiles held exactly the classes 0, 1, 3, 250, 251 and 255. The NISAR mask is HH below -12.1 dB and HV below -18.8 dB, thresholds set on the main Tarbela pool on 26 July, a date not compared. DSWx comes from Sentinel-1 at a different time and look, so days apart are stated.

| NISAR date | DSWx date | Days apart | Pixels compared | Agreement | Calling all dry would score | Water found (recall) | Radar low that is DSWx water (precision) | IoU | Tarbela box: agreement, baseline, IoU |
|---|---|---|---|---|---|---|---|---|---|
| 12 Sep | 15 Sep | 3 | 20,325,277 | 0.983 | 0.980 | 0.81 | 0.56 | 0.50 | 0.984, 0.814, 0.92 |
| 12 Sep | 16 Sep | 4 | 17,635,947 | 0.982 | 0.980 | 0.78 | 0.54 | 0.47 | 0.982, 0.798, 0.91 |
| 24 Sep | 23 Sep | 1 | 12,510,708 | 0.982 | 0.973 | 0.90 | 0.61 | 0.57 | 0.984, 0.814, 0.92 |
| 6 Oct | 5 Oct | 1 | 12,506,958 | 0.970 | 0.974 | 0.89 | 0.45 | 0.43 | 0.981, 0.815, 0.90 |
| 18 Oct | 17 Oct | 1 | 12,508,583 | 0.986 | 0.975 | 0.82 | 0.69 | 0.60 | 0.983, 0.815, 0.91 |

Dates before 12 Sep have no useful partner: the nearest tile to 2 Jul is 28 Jun, 4 days away but on the interference date, and the nearest to 14 Jul is 16 days away. On 6 Oct whole-window agreement is below the all-dry score, because more dry ground fell below the thresholds that day.

Read this with care. Most of the window is dry, so calling everything dry would already score about 97 to 98 percent: **whole-window agreement says little**. Recall and IoU, and the Tarbela box, are the useful numbers. The radar mask also marks smooth dry ground, which is why it finds more low pixels than DSWx has water pixels. The thresholds suit large still water and were not tuned for rivers.

Water share inside the 150 m radius of two sites follows the curves. Each row is DSWx cells marked water out of 81.

| Site | 28 Jun | 15 Sep | 23 Sep | 5 Oct | 17 Oct |
|---|---|---|---|---|---|
| Tarbela south-east shore | 0 | 75 | 26 | 0 | 0 |
| Indus near Attock | 76 | 59 | 48 | 39 | 12 |
| Tarbela main pool (control) | 81 | 81 | 81 | 81 | 81 |

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

## Other datasets (planned, not yet used or downloaded)

All of these are listed in the plan (`docs/SARtale-hackathon-plan.md`, section 5). Their licence status has **not** been verified for this project unless stated.

| Dataset | Planned use | Licence status | Access date |
|---|---|---|---|
| OPERA DSWx-HLS | Optical water check | NASA data, openly available. Specific terms to confirm | Not accessed |
| HLS (Harmonized Landsat Sentinel-2) | Crop and vegetation check | NASA data, openly available. Specific terms to confirm | Not accessed |
| NISAR SME2 soil moisture | Stretch goal only. Not fully calibrated | NASA data, openly available. Specific terms to confirm | Not accessed |
| GPM IMERG | Rain timing | NASA data, openly available. Specific terms to confirm | Not accessed |
| OpenStreetMap | Roads, bridges, hospitals, schools (the app can load optional overlays from `data/overlays/`; the only overlay in the current build is the hand-entered place labels, not OSM) | ODbL 1.0. Attribution "© OpenStreetMap contributors" is required if used. Share-alike duties to confirm | Not accessed |
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

## Still to do

- Confirm the data-use and citation wording for NISAR, OPERA (used now), HLS and IMERG, and whether quoting FFD figures needs anything more than naming the source.
- Confirm UNOSAT, WorldPop and HydroSHEDS terms, or leave them out.
- Record the logo's origin and licence.
- Check the place labels against a map or gazetteer before they are described as anything more than approximate.
