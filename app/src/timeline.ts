import type { Manifest, Pol } from "./types";

export async function loadManifest(url: string): Promise<Manifest> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load the data manifest (${res.status} ${url})`);
  const m = (await res.json()) as Manifest;
  if (!Array.isArray(m.dates) || m.dates.length === 0 || !Array.isArray(m.bounds)) {
    throw new Error("The data manifest has no dates or bounds");
  }
  return m;
}

/** Manifest paths are relative to data/. */
export function dataUrl(path: string): string {
  return `data/${path}`;
}

export function frameUrl(m: Manifest, date: string, pol: Pol): string {
  const entry = m.dates.find((d) => d.date === date);
  if (!entry) throw new Error(`No frame for ${date}`);
  const path = entry.frames[pol];
  if (!path) throw new Error(`No ${pol} frame for ${date}`);
  return dataUrl(path);
}

export function orderedDates(m: Manifest): string[] {
  return m.dates.map((d) => d.date).sort();
}

/** Every date NISAR imaged this stack: the manifest's `acquisitions` plus its built `dates`, sorted. Falls back to `dates`. */
export function acquisitionDates(m: Manifest): string[] {
  const all = new Set([...orderedDates(m), ...(Array.isArray(m.acquisitions) ? m.acquisitions : [])]);
  return [...all].sort();
}

export type MaturityKind = "provisional" | "preview" | "synthetic";

/**
 * The label that must always be visible on the map. Only the exact strings "Provisional" and
 * "Provisional preview" are shown as NISAR data. Anything else fails safe to the synthetic banner.
 */
export function maturityBanner(m: Manifest): { kind: MaturityKind; text: string } {
  if (m.maturity === "Provisional") return { kind: "provisional", text: "Provisional NISAR data" };
  if (m.maturity === "Provisional preview") {
    return { kind: "preview", text: "REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED" };
  }
  return { kind: "synthetic", text: "SYNTHETIC DEMO: NOT NISAR DATA" };
}

/** The flag for a date, or undefined. */
export function flagFor(m: Manifest, date: string): string | undefined {
  return m.dates.find((d) => d.date === date)?.flag || undefined;
}

/** Why a date is left out of the change layer, or undefined. */
export function changeExclusion(m: Manifest, date: string): string | undefined {
  return m.change?.excluded.find((e) => e.date === date)?.reason;
}

/** "2026-07-02" to "2 Jul 2026", without time zone shifts. */
export function formatDate(iso: string): string {
  const [y, mo, d] = iso.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${d} ${months[mo - 1]} ${y}`;
}
