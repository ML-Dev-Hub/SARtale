import "@fontsource-variable/bricolage-grotesque/wdth.css";
import "./styles.css";
import { mountApp } from "./app";
import { hostFactoryFor } from "./maplibreAdapter";
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

loadManifest("data/manifest.json").then(
  (m) => mountApp(root, m, hostFactoryFor(m)),
  (err: unknown) =>
    showStartupError(`${err instanceof Error ? err.message : String(err)}. Check that data/manifest.json is next to the page.`),
);
