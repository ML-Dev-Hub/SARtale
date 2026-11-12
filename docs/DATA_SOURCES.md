# Data sources and licences

Updated 11 Nov 2026. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and name their licences. Where a licence has not been checked, this file says "terms not confirmed" and does not guess.

## Status in one paragraph

Lake Watch shows NISAR radar data labelled **Provisional**. `app/public/data/lakes.json` and the per-lake images are built by the pipeline in `processing/` (`lakes-search`, `lakes-fetch`, `lakes-build`, `lakes-check`, `lakes-freeze`) from 6 km windows of NASA's NISAR GCOV passes (the provisional release up to 21 Oct 2026, the standard product after it), read over HTTPS without downloading whole files. Only derived data is committed; the cached windows live in `data/lakes/` (git-ignored).

## Satellite data

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| NISAR L2 GCOV (NASA, from ASF): the provisional release, CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1`, CRID `P05023`, passes up to 21 Oct 2026; and the standard product, CMR short name `NISAR_L2_GCOV_V1` (C3622241360-ASF), CRID `P05036`, passes from 21 Oct 2026. Mode 4005, DHDH, frequency A, HH and HV | A 6 km window of every calibrated pass over each lake from 17 Jun 2026 (the passes used are listed per lake in `lakes.json`). Every lake area and radar picture | NASA data, openly available. The provisional release is not validated and NASA expects to reprocess it; we have no statement that the standard product is validated. A status track that spans both is flagged on the lake. Exact citation wording: terms not confirmed | 2026-11-02 |
| Sentinel-2 L2A, via Earth Search (Element 84) | Optical water (MNDWI) cross-check for every lake that holds a lake now (sites with no lake now are not compared). Only derived areas are kept. Scenes Earth Search flags `earthsearch:boa_offset_applied` already have the BOA offset applied, so it is not applied again. Also the freeze check (`lakes-freeze`): for a cold lake, the clearest scene of the last 7 days whose lake zone is at least 80% clear of cloud, cloud shadow and their 100 m edge gives the snow/ice share (SCL class 11) and the water share of the lake itself (its unbuffered outline, or the summer radar water core for a lake without one), over its clear pixels, when at least half of it is clear | Copernicus Sentinel data terms (free, full and open; attribution "Contains modified Copernicus Sentinel data"). Exact legal notice wording: terms not confirmed | 2026-11-12 |
| Copernicus DEM GLO-30 (ESA; © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by the European Union and ESA), public COGs found through Earth Search (`cop-dem-glo-30`) | The height of each lake's surface, measured once (`lakes-elevation`, which the rebuild runs for any lake without one) and stored in `processing/lakes_in.json` as `elevation_m` with `elevation_source`: the 10th percentile of the DEM within 1 km of the lake point (the lake is the low, flat part of the circle; about ±100 m where the DEM has no flat water surface). The freeze check moves air temperature to this height | Copernicus DEM licence: free of charge, worldwide, for any lawful use, with the attribution above. Exact legal notice wording: terms not confirmed | 2026-11-12 |

## Air temperature

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| NASA POWER daily point API (NASA Langley Research Center POWER Project; MERRA-2 based), parameters `T2M` and `T2M_MIN`, community `RE`, no login | The freeze check (`lakes-freeze`), each refresh: daily air temperature at each lake from 1 Sep, moved from the POWER grid cell's height (in the response) to the lake's at −6.5 °C/km. Frozen (likely) when the daily mean has been below 0 °C on 7 days in a row with 30 freezing degree-days since 1 Sep; not assessed when the newest day is more than 10 days old. A reanalysis estimate for a cell about 50 km across, not a measurement at the lake. Only the derived state and numbers are kept in `lakes.json` | NASA data, openly available; POWER asks users to acknowledge "data obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program". Exact citation wording: terms not confirmed | 2026-11-12 |

## Lake locations and outlines

A location check on 10 Nov 2026 compared every register point with Sentinel-2 imagery of summer 2026, OpenStreetMap
and HMAGLOFDB. Ghulkin (the zone measured the Hunza River), Batura (no lake), Yarkhun (wet snow and glacier ice) and
Bindo Gol (no lake at the point) were dropped from the register. Shisper and Khurdopin are kept as sites with no lake
now. A links and coordinates audit on 11 Nov 2026 then moved three points:

- **Passu** to 74.8810 E, 36.4580 N. The old point (the HMAGLOFDB point rounded to 3 decimals) sat on a dark patch
  inside the outline, not on water; the new one is open water 50-67 m from shore in Sentinel-2 on 10 Jul and 18 Sep
  2026. The OpenStreetMap outline is still the zone, so the area does not depend on the point.
- **Shazore** to 72.1741 E, 35.7794 N, on the 2026 remnant lake. The lake partly drained in the GLOF of 30 Aug 2024
  (HMAGLOFDB GF 734); the HMAGLOFDB point now lies on the exposed lake bed. The outline is the 2026 remnant lake from
  Sentinel-2 (below), not the pre-2024 OpenStreetMap lake, of which only 26% was water in 2026.
- **Rogheli** to 71.9677 E, 35.8539 N, the centre of the supraglacial pond seen in Sentinel-2 on 28 Jun 2019
  (0.031 km²) and 27 Jun 2020 (0.036 km²), before the Golain GLOFs of 7 Jul 2019 and 13 Jul 2020 (HMAGLOFDB GF 498,
  504). It is now a site with **no lake now**: no water on any clear scene of 23 Jun-11 Sep 2026. Its zone is a 150 m
  circle round the pond. The earlier 1 km circle took in the clean-ice tongue of Rogheli glacier 600-700 m south,
  whose MNDWI passes for water and whose radar is dark, and a 0.001-0.002 km² pond 150 m north-east. A 150 m circle
  holds the whole pond (radius about 100 m) and leaves both out.

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| OpenStreetMap way 60065056, "Attabad lake" (`processing/outlines/attabad_osm.geojson`) | Attabad's lake outline, buffered 200 m. 7.2 km² in total; only the part inside the 6 km radar window is counted. Attabad's register point is a point inside this outline | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-04 (outline), 2026-11-10 (point) |
| OpenStreetMap way 360957778, "Passu lake" (`processing/outlines/passu_osm.geojson`) | Passu's lake outline, buffered 200 m | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-10 |
| Shazore 2026 outline (`processing/outlines/shazore_s2_2026.geojson`), made by SARtale from Sentinel-2 L2A | Shazore's lake outline, buffered 200 m (0.117 km²). Method: on a 10 m UTM grid (EPSG:32643), water is MNDWI > 0 with the scene classification not cloud, shadow, no data or snow (the BOA offset applied once); the 9 scenes of 1 Aug-30 Sep 2026 whose lake area (600 m round the point) was at least 95% clear were stacked; the outline is the pixels that are water on at least half of them, the connected water at the register point. Scenes: S2B_42SYE_20260805_0_L2A, S2C_42SYE_20260820_0_L2A, S2B_42SYE_20260825_0_L2A, S2C_42SYE_20260830_0_L2A, S2C_42SYE_20260909_0_L2A, S2A_42SYE_20260911_1_L2A, S2C_42SYE_20260919_0_L2A, S2B_42SYE_20260924_0_L2A, S2C_42SYE_20260929_0_L2A. The method and scene ids are also in the file's `source` | Derived from Copernicus Sentinel data (terms as above) | 2026-11-11 |
| OpenStreetMap way 349316277, an unnamed lake at Shazore | The pre-2024 lake (0.150 km²). No longer the zone: it is the lake before the 30 Aug 2024 partial drainage | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-10 |
| HMAGLOFDB v1.3.0 (Zenodo 18257243; https://github.com/fidelsteiner/HMAGLOFDB), the dataset of Shrestha et al. 2023, ESSD 15:3941 | Coordinates of Khurdopin (lake point) and Karambar (lake GL074079E36622N, with a 300 m search circle on the terminus pond); the primary source of Passu (GF 429, 74.879432 E, 36.457073 N, moved onto open water), Rogheli (GF 498, 504) and Shazore (GF 734), and the 30 Aug 2024 Shazore drainage; the Shisper lake point cited beside the Sentinel-2 position | CC0 1.0 Universal (read from the repository's `LICENSE` file) | 2026-11-02, 2026-11-10, 2026-11-11 |
| Sentinel-2 L2A, via Earth Search (Element 84) | The Shisper basin position (water centroids on 25 May 2020 and 5 Apr 2022); the Rogheli pond (28 Jun 2019, 27 Jun 2020); the Passu and Shazore points (Jul to Sep 2026); the no-lake notes for Shisper, Khurdopin and Rogheli; and the dated absence checks (`absence_checked`, below) | Copernicus Sentinel data terms, as above | 2026-11-10, 2026-11-11 |
| Tian et al. 2026, "Are area changes the primary indicator for predicting glacial lake outburst Risks?", RCAR 18, 120-129, doi 10.1016/j.rcar.2025.03.005 | Formerly cited for the Passu coordinate. Its event table could not be read on 11 Nov 2026, so Passu now rests on HMAGLOFDB; kept here only as a secondary reference | CC BY 4.0 (Crossref licence record) | 2026-11-11 |

### No lake now: dated checks and when a lake may be forming

A site the register holds as having no lake now (Shisper, Khurdopin, Rogheli) carries `absence_checked` in
`lakes.json`: the Sentinel-2 scene id and date, the share of the lake zone's clear pixels that held water (MNDWI > 0,
as in the cross-check), and the share of the zone under snow or ice. `lakes-absence` runs on every refresh, all year:
the lake that matters most can form outside summer (Shisper's 2022 lake filled in March and April and burst on 7 May).
It takes the newest scene whose lake zone is at least 80% clear, counting snow and ice (scene classification 11) as
not clear, and with snow or ice on no more than 1% of the zone: a frozen or snow-covered pond reads as dry ground in
MNDWI, so a snowy scene is never evidence that a site is empty. Pixels within 100 m of cloud or cloud shadow (scene
classification 3, 8, 9, 10) are not clear either: their edges are often unflagged haze or shadow that MNDWI reads as
water (Shisper, 16 Oct 2026: 14.5% "water" on bare soil beside cloud shadow). When no scene qualifies, the last check
stands, and the site says so: "Last checked <date> ...; no clear, snow-free Sentinel-2 view of the zone since
(searched to <date>)". The site turns into **Lake may be forming** only when its two most recent qualifying scenes, at
least 5 days apart, both show water above its threshold; one such scene is recorded as pending, and the site says
that SARtale is checking the next clear scene. It returns to No lake now only after two qualifying scenes below the
threshold, again at least 5 days apart. A site where a lake may be forming has no growing or shrinking verdict; its
radar dark area is shown but not yet treated as lake area, and the SARtale team reviews the site to add it to the
register as a measured lake (nothing promotes it automatically). The thresholds come from a survey of every clear
scene of 15 Jun-30 Sep 2026 and of dates when the lakes were there (11 Nov 2026):

| Site and zone | Empty zone, 2026 | When the lake was there | Threshold |
|---|---|---|---|
| Shisper, 1 km circle | 0.6-1.6% (9 scenes; stream threads) | 6.8% (26 Mar 2022), 8.7% (5 Apr 2022), 11.6% (20 May 2020), 12.6% (25 May 2020) | 4% (the default, `FORMING_WATER_SHARE`) |
| Khurdopin, 1 km circle | 7.8-13.3% (14 scenes; the Shimshal River) | No Sentinel-2 L2A scene of the 2017 lake in the archive | 16%: a new lake must add about 0.08 km² over the river's highest. A lake as small as 2017's (0.043 km²) would not show; the site carries this as a limit |
| Rogheli, 150 m circle | 0-5.4% (13 scenes; wet snow and single pixels) | 40% (28 Jun 2019), 43% (27 Jun 2020), 17% (2 Jul 2020, draining) | 10% |

## Context and quotes

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| SUPARCO, GLOF status updates of 2 Jul (https://space4climate.gov.pk/glof-status-update/) and 5 Aug 2026 (space4climate.gov.pk) | The cloud window and one quoted sentence. Nothing else is copied | Terms not confirmed. Quoted text only, with the source named | 2026-11-02 |
| Dawn, 7 May 2022, https://www.dawn.com/news/1688466 ("Hunza's Hassanabad bridge on the Karakoram Highway was on Saturday destroyed and swept away") and 8 May 2022, https://www.dawn.com/news/1688567 ("The outburst of the ice-dammed lake formed by the surging Shisper glacier"; flooding "disconnected road access between central and upper Hunza") | The Shisper outburst and the Hassanabad bridge (story 01, the Shisper `downstream_source`, the demo video) | Terms not confirmed. Cited only | 2026-11-11 |
| Radio Pakistan, 9 May 2022, https://radio.gov.pk/09-05-2022/all-resources-to-be-utilized-for-rehabilitation-of-shishper-glacier-affectees-cm-gb | A steel bridge to replace the collapsed Hassanabad bridge on the Karakoram Highway. Replaces the earlier citation "Radio Pakistan, 7 May 2022", which could not be found | Terms not confirmed. Cited only | 2026-11-11 |
| SUPARCO, GLOF monitoring status of 5 Aug 2026 (posted 20 Aug), https://space4climate.gov.pk/glof-monitoring-status-05-august-2026/ | The end of the cloud window | Terms not confirmed. Cited only | 2026-11-11 |

SUPARCO quote, verbatim: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days." (space4climate.gov.pk, GLOF Status Update, 2 Jul 2026.)

Sentinel-2 cross-check result (`lakes.json`, `checks`): one NISAR pass against one Sentinel-2 scene per lake, inside the lake's zone. The app's How we know page lists every row and words the agreement from the IoU values. Until 10 Nov 2026 the check applied the Sentinel-2 BOA offset twice, which pushed turbid lakes below the water threshold and made the agreement look far worse than it was. Neither source is a clean reference, and this is not a validation of lake extent.

## Demo video (`media/SARtale-lake-watch-demo.mp4`)

| Item | Use | Licence or terms |
|---|---|---|
| Sentinel-2 L2A true colour, 20 Jul 2026 (Hunza valley) and 3 Jul 2026 (Attabad, 70% cloud) | Opening shot and the cloud-versus-radar shot | Copernicus Sentinel data terms, as above |
| NISAR GCOV, 30 Jun 2026, track 055A | The radar side of the same shot | NASA data, as above |
| OpenStreetMap way 651792498 | Location of the Karakoram Highway bridge at Hassanabad (36.3006 N, 74.5869 E) | © OpenStreetMap contributors, ODbL 1.0 |
| Narration, music and two sound effects | Generated with ElevenLabs (paid account) | ElevenLabs terms for paid plans: terms not confirmed for this use |

## How-it-works video (`media/SARtale-how-it-works.mp4`)

| Item | Use | Licence or terms |
|---|---|---|
| NISAR GCOV, Attabad window, every pass 25 Jun to 23 Oct 2026 | The radar image, dark-pixel, shadow and water maps, and the pass chart. Made by the pipeline from the data in this repository | NASA data, as above |
| NASA MODIS Terra true colour (`app/public/story/north_map.jpg`) | Background map | As below |
| UNDP GLOF-II Project Brief 2023, https://www.undp.org/sites/g/files/zskgke326/files/2023-04/GLOF%20II%20Project%20%28Dec%202022%29_Project%20Brief_2023.pdf ("Over 3,000 glacial lakes have developed in Gilgit-Baltistan and Khyber Pakhtunkhwa regions") | One spoken and shown figure | Cited only |
| SUPARCO; Dawn, 7 May 2022 | As above: the quote and the 2022 Shisper outburst (the video's narration names Radio Pakistan; the videos are re-made in a later step) | Cited only |
| Sentinel-2 scene count over Attabad, 17 Jun to 4 Aug 2026 (13 scenes, 5 mostly cloud) | One spoken figure | Copernicus Sentinel data terms, as above |
| Narration and music | Generated with ElevenLabs (paid account) | ElevenLabs terms for paid plans: terms not confirmed for this use |

## Story page images (`app/public/story/`)

| Item | Use | Licence or terms |
|---|---|---|
| `hunza_valley.jpg`: Sentinel-2 L2A true colour, Hunza valley, 20 Jul 2026 | Cover picture | Copernicus Sentinel data terms, as above |
| `attabad_cloud.jpg`: Sentinel-2 L2A true colour, Attabad, 3 Jul 2026, 70% cloud over the 6 km window | Optical side of the cloud-versus-radar pair | Copernicus Sentinel data terms, as above |
| `attabad_radar_0630.jpg`: NISAR GCOV L-band HH, 30 Jun 2026, track 055A | Radar side of the same pair | NASA data, as above |
| `north_map.jpg`: NASA MODIS Terra true colour, 5 Oct 2026, 70.8-76.6 E, 34.4-37.6 N | Base map for the lake pins | NASA EOSDIS data, openly available. Exact citation wording: terms not confirmed |
| Dawn, 7 May 2022 (above) | The Shisper outburst and the destroyed Karakoram Highway bridge (story 01) | Terms not confirmed. Cited only |
| OpenStreetMap way 651792498 | The 6.6 km straight line (6,612 m geodesic) from the Shisper register point (the lake basin) to the Hassanabad bridge (story 01). A straight-line distance, not the flood's path down the gorge | © OpenStreetMap contributors, ODbL 1.0 |
| NASA CMR granule search (`cmr.earthdata.nasa.gov/search/granules.umm_json`) | Lists the NISAR passes over a requested lake's point, to say whether radar covers it. Catalogue entries only; no NISAR data is downloaded for a request | Public, no login. Exact citation wording: terms not confirmed |

## App dependencies (npm)

Licences are the `license` field of each installed package's `package.json`. Only direct dependencies are listed; transitive dependencies have not been audited.

| Package | Version | Licence | Role |
|---|---|---|---|
| maplibre-gl | 6.16.0 | BSD-3-Clause | The small lake locator map, bundled |
| uplot | 1.6.32 | MIT | Charts, bundled |
| @fontsource-variable/inter | 5.3.0 | OFL-1.1 | Body font for the story page, bundled |
| @fontsource-variable/inter-tight | 5.3.0 | OFL-1.1 | Display font for the story page, bundled |
| vite | 8.3.5 | MIT | Build tool (development only) |
| vitest | 5.0.5 | MIT | Tests (development only) |
| jsdom | 30.1.3 | MIT | Test DOM (development only) |
| typescript | 7.0.2 | Apache-2.0 | Type checking (development only) |

## Pipeline dependencies (Python, conda-forge)

Only the packages named in `environment.yml`; their own dependencies have not been audited.

| Package | Installed version | Licence | Used for |
|---|---|---|---|
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Everything numeric |
| scipy | 1.18.1 | BSD-3-Clause | Speckle filter and the outline buffer |
| h5py | 3.16.0 | BSD-3-Clause | Reading GCOV windows |
| rasterio | 1.5.2 | BSD-3-Clause | Outlines, Sentinel-2 windows |
| gdal | 3.13.3 | MIT (conda package metadata) | Through rasterio |
| pyproj | 3.8.0 | MIT | Coordinate transforms |
| pillow | 13.0.0 | MIT-CMU | Writing the lake images |
| requests | 2.34.2 | Apache-2.0 | CMR search, HTTPS range reads, Sentinel-2 search |
| pyyaml | 6.0.3 | MIT | Reading the workflow files in tests |
| pytest | 9.2.0 | MIT | Tests |
| Python | 3.12 | Python Software Foundation licence | |

## Other data

- **The team logo** (`app/logo/SARtale.png`, resized copies in `app/public/brand/`) was supplied by the team. Its origin and licence are to be recorded (see `docs/SI_USE.md`).

## Still to do

- Confirm the data-use and citation wording for NISAR and Sentinel-2.
- Confirm the ElevenLabs terms for using generated audio in a public demo.
- Record the logo's origin and licence.
