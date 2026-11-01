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

export type MaturityKind = "provisional" | "synthetic";

/** The label that must always be visible on the map. Anything but "Provisional" is shown as not NISAR data. */
export function maturityBanner(m: Manifest): { kind: MaturityKind; text: string } {
  return m.maturity === "Provisional"
    ? { kind: "provisional", text: "Provisional NISAR data" }
    : { kind: "synthetic", text: "SYNTHETIC DEMO: NOT NISAR DATA" };
}

/** "2026-07-02" to "2 Jul 2026", without time zone shifts. */
export function formatDate(iso: string): string {
  const [y, mo, d] = iso.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${d} ${months[mo - 1]} ${y}`;
}
