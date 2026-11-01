import "@fontsource-variable/bricolage-grotesque/wdth.css";
import "./styles.css";
import { mountApp } from "./app";
import { hostFactoryFor } from "./maplibreAdapter";
import { createUplotChart } from "./chart";
import { loadSites } from "./sites";
import { loadManifest } from "./timeline";

const root = document.getElementById("app")!;

function showStartupError(message: string): void {
  root.innerHTML = "";
  const p = document.createElement("p");
  p.className = "startup-error";
  p.setAttribute("role", "alert");
  p.textContent = message;
  root.append(p);
}

Promise.all([loadManifest("data/manifest.json"), loadSites("data/sites.json")]).then(
  ([m, sites]) => mountApp(root, m, hostFactoryFor(m), { sites, createChart: createUplotChart }),
  (err: unknown) =>
    showStartupError(`${err instanceof Error ? err.message : String(err)}. Check that data/manifest.json is next to the page.`),
);
