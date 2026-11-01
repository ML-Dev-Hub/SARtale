import "@fontsource-variable/bricolage-grotesque/wdth.css";
import "./styles.css";
import { hostFactoryFor } from "./maplibreAdapter";
import { createUplotChart } from "./chart";
import { sitesForManifest, loadSites } from "./sites";
import { mountOrShowError, showStartupError } from "./startup";
import { loadManifest } from "./timeline";

const root = document.getElementById("app")!;

Promise.all([loadManifest("data/manifest.json"), loadSites("data/sites.json")]).then(
  ([m, sites]) =>
    // Curves from another build (or with no stamp) are dropped: the view then says "No site curves yet".
    mountOrShowError(root, m, hostFactoryFor(m), { sites: sitesForManifest(sites, m), createChart: createUplotChart }),
  (err: unknown) =>
    showStartupError(
      root,
      `${err instanceof Error ? err.message : String(err)}. Check that data/manifest.json is next to the page.`,
    ),
);
