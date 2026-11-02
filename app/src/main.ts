import "@fontsource-variable/bricolage-grotesque/wdth.css";
import "./styles.css";
import { lazyHostFactory } from "./lazyHost";
import { createUplotChart, createUplotLakeChart } from "./chart";
import { createLakeLocator } from "./lakeLocator";
import { loadImage } from "./images";
import { createPreloader } from "./preload";
import { printBrief } from "./lakeBrief";
import { loadLakes } from "./lakes";
import { sitesForManifest, loadSites } from "./sites";
import { mountOrShowError, showStartupError } from "./startup";
import { loadManifest } from "./timeline";

const root = document.getElementById("app")!;

Promise.all([loadManifest("data/manifest.json"), loadSites("data/sites.json"), loadLakes("data/lakes.json")]).then(
  ([m, sites, lakes]) =>
    // Curves from another build (or with no stamp) are dropped: the view then says "No site curves yet".
    mountOrShowError(root, m, lazyHostFactory(m), { sites: sitesForManifest(sites, m), lakes, createChart: createUplotChart, createLakeChart: createUplotLakeChart, createLakeLocator, onLakeBrief: (lake) => lakes && printBrief(lake, lakes), preload: createPreloader(loadImage) }),
  (err: unknown) =>
    showStartupError(
      root,
      `${err instanceof Error ? err.message : String(err)}. Check that data/manifest.json is next to the page.`,
    ),
);
