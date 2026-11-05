<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale Pakistan logo" width="200" />
</p>

# SARtale Lake Watch

Glacial lakes in Gilgit-Baltistan and upper Khyber Pakhtunkhwa, watched through cloud with NASA–ISRO NISAR radar.

NASA Space Apps Challenge 2026, "Dancing with the SARs". Team **SARcastic Scientists** (Saeed Ahmad, Shaharyar Sajid, Usama Hussain), Islamabad Local Event.

**Demo video:** [media/SARtale-lake-watch-demo.mp4](media/SARtale-lake-watch-demo.mp4) (38 s, subtitles in `media/SARtale-lake-watch-demo.srt`)

**How it works:** [media/SARtale-how-it-works.mp4](media/SARtale-how-it-works.mp4) (3 min 41 s technical walkthrough, subtitles in `media/SARtale-how-it-works.srt`)

## The problem

Pakistan's space agency SUPARCO tracks 131 potentially dangerous glacial lakes, mostly with optical satellites. In summer, when lakes fill and burst, cloud often hides them. Its 2 July 2026 update says: "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days." Radar sees through cloud.

## What it does

- Reads a 6 km window of every NISAR pass over 11 glacial and landslide-dammed lakes, without downloading whole files.
- Turns dark radar pixels into water area inside each lake's zone, and removes radar shadow by comparing the two viewing directions.
- Gives each lake one plain status (Growing, Stable, Shrinking, Not seen this pass, Not observable, Not enough NISAR looks yet), comparing it only with its own earlier passes on the same track, against its own noise.
- Prints a one-page brief per lake, with dates, looks, noise and limits.
- Opens on a story page; the map and lake pages follow from it.

From 17 June to 4 August 2026, while SUPARCO's updates reported cloud limiting optical imagery, NISAR made 60 valid looks across the 11 lakes. All 11 read Stable in this build.

## Limits

- **Indicative screening on provisional data.** NASA's provisional GCOV product (CRID `P05023`) is not validated and will be reprocessed. A status is not a measure of volume or hazard.
- **Optical agreement is poor.** In a Sentinel-2 check on four lakes, radar and optical water overlapped poorly everywhere (IoU 0.013 to 0.09). Neither is a clean reference.
- **Zones.** Attabad is measured inside its OpenStreetMap outline (72% of it falls inside the radar window); the other lakes inside a 1 km circle around a published coordinate. Lakes whose shores sit in radar shadow are under-counted. Frozen lakes, lakes under 0.05 km² and wind-roughened water are not validated.
- **Not a warning service.** Official warnings come from PMD, NDMA, GBDMA and PDMA.

## Run the app

Node.js and npm:

```bash
npm --prefix app install
npm --prefix app run dev          # http://localhost:5173
npm --prefix app test -- --run    # unit tests, including the wording check
npm --prefix app run build        # type-check, then build into app/dist/
```

## Lake requests

Visitors can ask for a lake to be added with the "Add a lake" form. A small server receives the request; a static copy of the site has none, and the form there says "Requests are not open on this copy of the site." Nothing else changes.

Run the server and the app side by side. `npm --prefix app run dev` sends `/api` to the server.

```bash
cd processing && conda run -n sartale python -m sartale.run_pipeline lake-requests-serve   # 127.0.0.1:8787, data/lake_requests.sqlite
npm --prefix app run dev
```

Options: `--host`, `--port`, `--db`, `--origin` (default `http://localhost:5173`). The database is under `data/`, which is git-ignored. The server is set up for local or demo use.

To host it apart from the site, run it with `--host 0.0.0.0 --origin <site origin>` (for example `--origin https://lakes.example.org`), and build the app with `VITE_REQUESTS_API=<server url>/api npm --prefix app run build`. The default, `api`, is the same origin or the dev proxy. Behind a reverse proxy the server sees one address, so all visitors share one rate limit of 5 requests per hour.

A failed search shows visitors a short reason only. The raw error is kept in a private `detail` column and printed by `lake-requests-list`.

The server accepts a point between 34.4 and 37.6 °N and 70.8 and 76.6 °E, a name of 2 to 80 characters and a source of 3 to 200. It refuses a point within 1 km of a watched lake or an open request, more than 5 requests per address per hour, more than 200 open requests, bodies over 4 KB, and slow clients. It searches NASA's CMR catalogue for NISAR passes over the point and never downloads NISAR data.

The team decides, from `processing/`:

```bash
conda run -n sartale python -m sartale.run_pipeline lake-requests-list
conda run -n sartale python -m sartale.run_pipeline lake-requests-accept 3            # --role watch by default; adds one entry to lakes_in.json
conda run -n sartale python -m sartale.run_pipeline lake-requests-reject 4 --reason "No public source for the coordinate"
```

After an accept, run `lakes-search`, `lakes-fetch` and `lakes-build` below to give the lake its status.

## Run the pipeline

conda (`environment.yml`) and an Earthdata login in `~/.netrc`. From `processing/`:

```bash
conda env create -f environment.yml
cd processing
conda run -n sartale python -m sartale.run_pipeline lakes-search   # find NISAR passes over each lake
conda run -n sartale python -m sartale.run_pipeline lakes-fetch    # cache a 6 km window per pass (restartable)
conda run -n sartale python -m sartale.run_pipeline lakes-build    # build app/public/data/lakes.json and the lake images
conda run -n sartale python -m sartale.run_pipeline lakes-check    # compare radar water with Sentinel-2 water
conda run -n sartale pytest tests -q
```

Lakes and the source of each coordinate are in `processing/lakes_in.json`; outlines in `processing/outlines/`. Raw windows are cached in `data/` (git-ignored).

## Repository

| Path | Contents |
|---|---|
| `app/` | The web app (TypeScript, Vite, MapLibre, uPlot). Copy text is in `app/src/content/` |
| `processing/` | The Python pipeline and its tests |
| `media/` | The demo video and the how-it-works walkthrough |
| `docs/` | [Data sources and licences](docs/DATA_SOURCES.md), [AI tool use](docs/SI_USE.md) |

## Licence

Code: Apache License 2.0 (`LICENSE`). Data and dependency licences: `docs/DATA_SOURCES.md`.
