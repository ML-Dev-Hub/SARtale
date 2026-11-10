# Data sources and licences

Updated 10 Nov 2026. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and name their licences. Where a licence has not been checked, this file says "terms not confirmed" and does not guess.

## Status in one paragraph

Lake Watch shows NISAR radar data labelled **Provisional**. `app/public/data/lakes.json` and the per-lake images are built by the pipeline in `processing/` (`lakes-search`, `lakes-fetch`, `lakes-build`, `lakes-check`) from 6 km windows of NASA's NISAR GCOV passes (the provisional release up to 21 Oct 2026, the standard product after it), read over HTTPS without downloading whole files. Only derived data is committed; the cached windows live in `data/lakes/` (git-ignored).

## Satellite data

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| NISAR L2 GCOV (NASA, from ASF): the provisional release, CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1`, CRID `P05023`, passes up to 21 Oct 2026; and the standard product, CMR short name `NISAR_L2_GCOV_V1` (C3622241360-ASF), CRID `P05036`, passes from 21 Oct 2026. Mode 4005, DHDH, frequency A, HH and HV | A 6 km window of every calibrated pass over each lake from 17 Jun 2026 (the passes used are listed per lake in `lakes.json`). Every lake area and radar picture | NASA data, openly available. The provisional release is not validated and NASA expects to reprocess it; we have no statement that the standard product is validated. A status track that spans both is flagged on the lake. Exact citation wording: terms not confirmed | 2026-11-02 |
| Sentinel-2 L2A, via Earth Search (Element 84) | Optical water (MNDWI) cross-check for every lake that holds a lake now (sites with no lake now are not compared). Only derived areas are kept. Scenes Earth Search flags `earthsearch:boa_offset_applied` already have the BOA offset applied, so it is not applied again | Copernicus Sentinel data terms (free, full and open; attribution "Contains modified Copernicus Sentinel data"). Exact legal notice wording: terms not confirmed | 2026-11-04 |

## Lake locations and outlines

A location check on 10 Nov 2026 compared every register point with Sentinel-2 imagery of summer 2026, OpenStreetMap
and HMAGLOFDB. Ghulkin (the zone measured the Hunza River), Batura (no lake), Yarkhun (wet snow and glacier ice) and
Bindo Gol (no lake at the point) were dropped from the register. Shisper and Khurdopin are kept as sites with no lake
now; Rogheli is kept as a lake not confirmed in 2026 imagery.

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| OpenStreetMap way 60065056, "Attabad lake" (`processing/outlines/attabad_osm.geojson`) | Attabad's lake outline, buffered 200 m. 7.2 km² in total; only the part inside the 6 km radar window is counted. Attabad's register point is a point inside this outline | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-04 (outline), 2026-11-10 (point) |
| OpenStreetMap way 360957778, "Passu lake" (`processing/outlines/passu_osm.geojson`) | Passu's lake outline, buffered 200 m | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-10 |
| OpenStreetMap way 349316277, an unnamed lake at Shazore (`processing/outlines/shazore_osm.geojson`) | Shazore's lake outline, buffered 200 m | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-10 |
| HMAGLOFDB v1.3.0 (Zenodo 18257243; https://github.com/fidelsteiner/HMAGLOFDB), the dataset of Shrestha et al. 2023, ESSD 15:3941 | Coordinates of Khurdopin (lake point), Karambar (lake GL074079E36622N, with a 300 m search circle on the terminus pond), Rogheli and Shazore, and the Shisper lake point cited beside the Sentinel-2 position | CC0 1.0 Universal (read from the repository's `LICENSE` file) | 2026-11-02, 2026-11-10 |
| Sentinel-2 L2A, via Earth Search (Element 84) | The Shisper basin position (water centroids on 25 May 2020 and 5 Apr 2022), and the no-lake and not-confirmed notes for Shisper, Khurdopin and Rogheli (scenes of Jul to Sep 2026) | Copernicus Sentinel data terms, as above | 2026-11-10 |
| Passu event table, doi 10.1016/j.rcar.2025.03.005 | Coordinate for Passu lake (within 50 m of the HMAGLOFDB point) | Journal licence: terms not confirmed. Cited, not redistributed | 2026-11-02 |

## Context and quotes

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| SUPARCO, GLOF status updates of 2 Jul and 5 Aug 2026 (space4climate.gov.pk) | The cloud window and one quoted sentence. Nothing else is copied | Terms not confirmed. Quoted text only, with the source named | 2026-11-02 |
| Radio Pakistan, 7 May 2022 | The Shisper outburst and the Hassanabad bridge, as context in the demo video | Terms not confirmed. Cited only | 2026-11-02 |

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
| UNDP GLOF-II (more than 3,000 glacial lakes in Gilgit-Baltistan and Khyber Pakhtunkhwa) | One spoken and shown figure | Cited only |
| SUPARCO, Radio Pakistan | As above: the quote and the 2022 Shisper outburst | Cited only |
| Sentinel-2 scene count over Attabad, 17 Jun to 4 Aug 2026 (13 scenes, 5 mostly cloud) | One spoken figure | Copernicus Sentinel data terms, as above |
| Narration and music | Generated with ElevenLabs (paid account) | ElevenLabs terms for paid plans: terms not confirmed for this use |

## Story page images (`app/public/story/`)

| Item | Use | Licence or terms |
|---|---|---|
| `hunza_valley.jpg`: Sentinel-2 L2A true colour, Hunza valley, 20 Jul 2026 | Cover picture | Copernicus Sentinel data terms, as above |
| `attabad_cloud.jpg`: Sentinel-2 L2A true colour, Attabad, 3 Jul 2026, 70% cloud over the 6 km window | Optical side of the cloud-versus-radar pair | Copernicus Sentinel data terms, as above |
| `attabad_radar_0630.jpg`: NISAR GCOV L-band HH, 30 Jun 2026, track 055A | Radar side of the same pair | NASA data, as above |
| `north_map.jpg`: NASA MODIS Terra true colour, 5 Oct 2026, 70.8-76.6 E, 34.4-37.6 N | Base map for the lake pins | NASA EOSDIS data, openly available. Exact citation wording: terms not confirmed |
| Radio Pakistan, 7 May 2022 | The Shisper outburst and the destroyed Karakoram Highway bridge (story 01) | Terms not confirmed. Cited only |
| OpenStreetMap way 651792498 | The 6.6 km straight line from the Shisper register point (the lake basin) to the Hassanabad bridge (story 01) | © OpenStreetMap contributors, ODbL 1.0 |
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
