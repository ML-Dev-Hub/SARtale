# Lake requests

Visitors can ask for a lake to be watched with the "Add a lake" form on the story page. A small Python server (standard library and SQLite only) receives each request and searches NASA's CMR catalogue for NISAR passes over the point. It never downloads NISAR data. A static copy of the site has no server, and the form there says "Requests are not open on this copy of the site." Nothing else changes.

## Run it locally

Run the server and the app side by side. `npm --prefix app run dev` sends `/api` to the server.

```bash
cd processing && conda run -n sartale python -m sartale.run_pipeline lake-requests-serve   # 127.0.0.1:8787, data/lake_requests.sqlite
npm --prefix app run dev
```

Options: `--host`, `--port`, `--db`, `--origin` (default `http://localhost:5173`). The database lives under `data/`, which is git-ignored. The server is set up for local or demo use.

## Host it apart from the site

Run the server with `--host 0.0.0.0 --origin <site origin>` (for example `--origin https://lakes.example.org`). Build the app with `VITE_REQUESTS_API=<server url>/api npm --prefix app run build`. The default, `api`, means the same origin or the dev proxy.

Behind a reverse proxy the server sees a single address, so all visitors share one rate limit of 5 requests per hour.

## What the server accepts

| Check | Limit |
|---|---|
| Point | 34.4 to 37.6 °N, 70.8 to 76.6 °E |
| Name | 2 to 80 characters |
| Source of the coordinate | 3 to 200 characters |
| Nearby lakes | Refused within 1 km of a watched lake or an open request |
| Rate | 5 requests per address per hour; at most 200 open requests |
| Body and clients | Bodies over 4 KB and slow clients are refused |

A failed catalogue search shows visitors a short reason only. The raw error is kept in a private `detail` column and printed by `lake-requests-list`.

## Review requests

The team decides, from `processing/`:

```bash
conda run -n sartale python -m sartale.run_pipeline lake-requests-list
conda run -n sartale python -m sartale.run_pipeline lake-requests-accept 3     # --role watch by default; adds one entry to lakes_in.json
conda run -n sartale python -m sartale.run_pipeline lake-requests-reject 4 --reason "No public source for the coordinate"
```

After an accept, run `lakes-search`, `lakes-fetch` and `lakes-build` (see the [README](../README.md#run-the-pipeline)) to give the lake its status.
