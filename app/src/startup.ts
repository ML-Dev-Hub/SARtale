import { MATURITY, mountApp, type AppHandle, type AppOptions } from "./app";

/** Replace the page with an error message, with the data label above it so a failure never leaves data unlabelled. */
export function showStartupError(root: HTMLElement, message: string): void {
  const label = document.createElement("p");
  label.className = "maturity";
  label.dataset.role = "maturity";
  label.dataset.kind = "provisional";
  label.textContent = MATURITY;
  const p = document.createElement("p");
  p.className = "startup-error";
  p.setAttribute("role", "alert");
  p.textContent = message;
  root.replaceChildren(label, p);
}

/** Mount the app. If that throws, show a message and the data label instead of a blank page. */
export function mountOrShowError(root: HTMLElement, opts: AppOptions): AppHandle | null {
  try {
    return mountApp(root, opts);
  } catch (err) {
    showStartupError(root, `SARtale could not start (${err instanceof Error ? err.message : String(err)}). Try reloading the page.`);
    return null;
  }
}
