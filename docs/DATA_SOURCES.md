# Data sources and licences

Updated 6 Nov 2026. Space Apps rules say we must confirm that non-NASA data and code are freely and publicly available or open source, and name their licences. Where a licence has not been checked, this file says "terms not confirmed" and does not guess.

## Status in one paragraph

Lake Watch shows NISAR radar data labelled **Provisional**. `app/public/data/lakes.json` and the per-lake images are built by the pipeline in `processing/` (`lakes-search`, `lakes-fetch`, `lakes-build`, `lakes-check`) from 6 km windows of NASA's provisional NISAR GCOV passes, read over HTTPS without downloading whole files. Only derived data is committed; the cached windows live in `data/lakes/` (git-ignored).

## Satellite data

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| NISAR L2 GCOV, provisional (NASA, from ASF). CMR short name `NISAR_L2_GCOV_PROVISIONAL_V1`, CRID `P05023`, mode 4005, DHDH, frequency A, HH and HV | A 6 km window of every calibrated pass over each lake from 17 Jun 2026: 232 passes, about 5.4 GB read in total. Every lake area and radar picture | NASA data, openly available. Provisional product, not validated; NASA expects reprocessing. Exact citation wording: terms not confirmed | 2026-11-02 |
| Sentinel-2 L2A, via Earth Search (Element 84) | Optical water (MNDWI) cross-check for Attabad, Khurdopin, Passu and Shisper. Only derived areas are kept | Copernicus Sentinel data terms (free, full and open; attribution "Contains modified Copernicus Sentinel data"). Exact legal notice wording: terms not confirmed | 2026-11-04 |

## Lake locations and outlines

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| OpenStreetMap way 60065056, "Attabad lake" (`processing/outlines/attabad_osm.geojson`) | Attabad's lake outline, buffered 200 m. 7.2 km² in total, 72% of it inside the 6 km radar window | © OpenStreetMap contributors, ODbL 1.0 | 2026-11-04 |
| HMAGLOFDB (https://github.com/fidelsteiner/HMAGLOFDB) | Coordinates of Rogheli, Yarkhun, Shazore and Bindo Gol, each with the event date recorded in `processing/lakes_in.json` | CC0 1.0 Universal (read from the repository's `LICENSE` file) | 2026-11-02 |
| Shrestha et al. 2023, ESSD 15:3941 | Table 3 coordinates for Khurdopin, Ghulkin, Karambar and Batura | CC BY 4.0 (stated on the article page). Attribution required | 2026-11-02 |
| Muhammad et al. 2021, doi 10.1080/19475705.2021.1975833 | The Shisper map frame (36°21′–36°22′ N, 74°34′–74°36′ E, Fig. 2), used to place the Shisper search circle | Journal licence: terms not confirmed. Cited, not redistributed | 2026-11-02 |
| Passu event table, doi 10.1016/j.rcar.2025.03.005 | Coordinate for Passu lake | Journal licence: terms not confirmed. Cited, not redistributed | 2026-11-02 |
| Attabad point coordinate | Chosen by the team on 2 Nov 2026 from where the lake shows in NISAR passes | Part of this repository, Apache License 2.0 | Not applicable |

## Context and quotes

| Item | Use | Licence or terms | Access date |
|---|---|---|---|
| SUPARCO, GLOF status updates of 2 Jul and 5 Aug 2026 (space4climate.gov.pk) | The cloud window and one quoted sentence. Nothing else is copied | Terms not confirmed. Quoted text only, with the source named | 2026-11-02 |
| Radio Pakistan, 7 May 2022 | The Shisper outburst and the Hassanabad bridge, as context in the demo video | Terms not confirmed. Cited only | 2026-11-02 |

SUPARCO quote, verbatim: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days." (space4climate.gov.pk, GLOF Status Update, 2 Jul 2026.)

Sentinel-2 cross-check result (`lakes.json`, `checks`): radar and optical water overlapped poorly at every lake checked (IoU 0.013 to 0.09), and their areas disagreed widely. Attabad, now measured inside its outline: radar 2.65 km² against optical 1.02 km². Khurdopin 0.036 against 0.885; Passu 0.048 against 0.239; Shisper, where no lake is expected, 0.087 against 0.288 (optical also flags water there). Neither is a clean reference, and this is not a validation of lake extent.

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
| OpenStreetMap way 651792498 | The 6.4 km straight line from the Shisper register point to the Hassanabad bridge (story 01) | © OpenStreetMap contributors, ODbL 1.0 |
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
