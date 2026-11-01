import { mountApp, type AppHandle, type AppOptions, type HostFactory } from "./app";
import { maturityBanner } from "./timeline";
import type { Manifest } from "./types";

/**
 * Replace the page with an error message. When the manifest is known, its maturity banner stays on the page
 * above the message, so a failure never leaves the data unlabelled.
 */
export function showStartupError(root: HTMLElement, message: string, manifest?: Manifest): void {
  root.innerHTML = "";
  if (manifest) {
    const banner = maturityBanner(manifest);
    const label = document.createElement("p");
    label.className = "maturity";
    label.dataset.role = "maturity";
    label.dataset.kind = banner.kind;
    label.textContent = banner.text;
    root.append(label);
  }
  const p = document.createElement("p");
  p.className = "startup-error";
  p.setAttribute("role", "alert");
  p.textContent = message;
  root.append(p);
}

/** Mount the app. If that throws (for example WebGL cannot start), show a message and the banner instead of a blank page. */
export function mountOrShowError(
  root: HTMLElement,
  m: Manifest,
  createHost: HostFactory,
  opts: AppOptions,
): AppHandle | null {
  try {
    return mountApp(root, m, createHost, opts);
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    showStartupError(root, `The map could not start (${reason}). The radar map needs WebGL, so try another browser or device.`, m);
    return null;
  }
}
