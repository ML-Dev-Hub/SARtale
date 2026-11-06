<p align="center">
  <img src="app/logo/SARtale.png" alt="SARtale logo" width="140" />
</p>

<h1 align="center">SARtale</h1>

<p align="center">
  <b>When clouds close in, the lakes stay in view.</b><br/>
  Glacial lakes in Gilgit-Baltistan and upper Khyber Pakhtunkhwa, watched through cloud with NASA–ISRO NISAR radar.
</p>

<p align="center">
  NASA Space Apps Challenge 2026 · <i>Dancing with the SARs</i> · Islamabad local event<br/>
  Team <b>SARcastic Scientists</b>: Saeed Ahmad, Shaharyar Sajid, Usama Hussain
</p>

<p align="center">
  <a href="media/SARtale-lake-watch-demo.mp4"><b>Demo video</b></a> (38 s) ·
  <a href="media/SARtale-how-it-works.mp4"><b>How it works</b></a> (3 min 41 s) ·
  <a href="https://saeedahmadicp.github.io/SARtale/"><b>Live site</b></a> ·
  <a href="https://saeedahmadicp.github.io/SARtale/guide/"><b>Guide</b></a>
</p>

![The SARtale story page](media/screens/story.jpg)

## Why

Pakistan has more than 3,000 glacial lakes (UNDP GLOF-II), and SUPARCO tracks 131 of them as potentially dangerous, mostly with optical satellites. The lakes fill in summer, and summer brings cloud. SUPARCO's [2 July 2026 update](https://space4climate.gov.pk/glof-status-update/) says:

> "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days."

Radar sees through cloud, day or night. From 17 June to 4 August 2026, while cloud limited the optical checks, NISAR made **60 valid looks across the 11 lakes** SARtale first watched (build of 23 Oct 2026).

## What it does

- **Gives each watched lake one plain status:** Growing, Stable, Shrinking, Not seen this pass, Not observable, or Not enough NISAR looks yet. The site shows the current status of each.
- **Shows the evidence:** the latest radar picture with the water read from it, a chart and a table of every pass, and each pass left out, with the reason.
- **Prints a one-page brief** per lake: dates, looks, noise and limits.
- **Takes requests for new lakes through GitHub issues.** A visitor fills in the website's form, which opens a pre-filled "Add a lake" issue (a GitHub sign-in is needed). A workflow checks the point, counts the NISAR passes over it and comments; a team member adds the `accepted` label to start the rebuild, or closes the issue to reject it. See [Lake requests](docs/guide/lake-requests.html). The repository is private for now, so only collaborators can open request issues until it is made public.

![Lake Watch: lake map, list with radar thumbnails, and Attabad's status and water picture](media/screens/lake-watch.jpg)

## How it works

![How SARtale works: six pipeline steps from NISAR passes to a status, the web app, and the lake request loop](media/workflow.jpg)

For every lake and every NISAR pass, SARtale reads a 6 km window straight from NASA's archive. It marks pixels at least 3 dB darker than the window in both HH and HV, removes radar shadow by comparing the two viewing directions, and measures water inside the lake's zone. It then compares the result only with that lake's earlier passes on the same track: a change counts only if it beats twice the lake's own noise. For example, Attabad on 23 October 2026 held 2.08 km², a change of +0.25 km² against a noise of 0.52 km², so it reads **Stable**.

The full method, with every constant, is in the [guide](docs/guide/method.html).

## Quick start

The app runs on the data in the repository; no NASA login is needed.

```bash
npm --prefix app install
npm --prefix app run dev          # http://localhost:5173
npm --prefix app test -- --run    # app tests, including the wording check
```

Rebuilding the data needs conda and an [Earthdata login](https://urs.earthdata.nasa.gov/) in `~/.netrc`:

```bash
conda env create -f environment.yml
cd processing
conda run -n sartale python -m sartale.run_pipeline lakes-search   # find NISAR passes over each lake
conda run -n sartale python -m sartale.run_pipeline lakes-fetch    # cache a 6 km window per pass
conda run -n sartale python -m sartale.run_pipeline lakes-build    # write app/public/data/lakes.json
conda run -n sartale pytest tests -q
```

## Guide

The developer and user guide is a small website in [`docs/guide/`](docs/guide/). It is published with the site at <https://saeedahmadicp.github.io/SARtale/guide/>; you can also open `docs/guide/index.html` in a browser.

| Page | For |
|---|---|
| [Getting started](docs/guide/getting-started.html) | Install, run and test |
| [Using the website](docs/guide/user-guide.html) | The story page, Lake Watch, statuses, Add a lake |
| [The method](docs/guide/method.html) | The six steps, noise, exclusions, constants |
| [Pipeline](docs/guide/pipeline.html) and [Data files](docs/guide/data.html) | Commands, the Attabad gate, `lakes_in.json` and `lakes.json` |
| [Web app](docs/guide/app.html) | Modules, routing, copy rules, tests |
| [Lake requests](docs/guide/lake-requests.html) | The issue flow, labels, accepting and rejecting |
| [Deploying](docs/guide/deploy.html) (with the owner setup), [Contributing](docs/guide/contributing.html), [Questions and limits](docs/guide/faq.html) | Hosting, ground rules, FAQ |

## Deploying

The site is at <https://saeedahmadicp.github.io/SARtale/>, published by `.github/workflows/deploy.yml` on every push to `main`. A weekly workflow refreshes the data, and the lake-request workflows handle issues. The owner sets up three things once, in this order, before any lake request is opened (steps in the [Deploying](docs/guide/deploy.html) page):

1. Settings → Pages → Source: **GitHub Actions**.
2. Settings → Environments → new environment `earthdata`, deployment branches limited to `main`, with the secrets `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`; then delete the repository-level copies.
3. Actions → Lake requests → Run workflow once, to create the labels. The issue form drops labels that do not exist yet, so a request opened before this is never seen.

The default workflow permissions can stay at **Read repository contents**: every workflow declares the permissions it needs.

On a public repository GitHub pauses scheduled workflows after 60 days without activity.

## Limits

- **Indicative screening on provisional data.** NASA's provisional GCOV product (CRID `P05023`) is not validated and will be reprocessed. A status is not a measure of volume or hazard.
- **Optical agreement is poor.** On clear days, radar and Sentinel-2 water overlapped poorly at all four lakes tested (IoU 0.013 to 0.09). Neither is a clean reference.
- **Zones are approximate.** Attabad is measured in its OpenStreetMap outline; the others in a 1 km circle around a published coordinate. Shadowed shores are under-counted.
- **Not a warning service.** Official warnings come from PMD, NDMA, GBDMA and PDMA.

## Repository

| Path | Contents |
|---|---|
| `app/` | The website: TypeScript, Vite, MapLibre, uPlot |
| `processing/` | The Python pipeline and its tests |
| `media/` | Videos, screenshots and the workflow figure |
| `docs/` | The [guide](docs/guide/), [data sources and licences](docs/DATA_SOURCES.md), [AI tool use](docs/SI_USE.md) |

## Licence

Code: Apache License 2.0 ([LICENSE](LICENSE)). Data keep their own licences, listed in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md). Video narration and music were made with ElevenLabs.
