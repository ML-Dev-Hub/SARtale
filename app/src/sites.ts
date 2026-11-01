import type { Manifest, Site } from "./types";

export interface ChartSeries {
  /** UTC seconds, as uPlot expects for a time axis. */
  x: number[];
  hh: (number | null)[];
  hv: (number | null)[];
}

function utcSeconds(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 1000;
}

/** Chart columns for a site, in date order. A missing value stays null so the chart can show the gap. */
export function toChartSeries(site: Site): ChartSeries {
  const rows = [...site.series].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  return {
    x: rows.map((r) => utcSeconds(r.date)),
    hh: rows.map((r) => r.hh_db ?? null),
    hv: rows.map((r) => r.hv_db ?? null),
  };
}

function isSite(v: unknown): v is Site {
  const s = v as Site;
  return !!s && typeof s.id === "string" && typeof s.name === "string" && Array.isArray(s.series);
}

/**
 * The sites that belong to this manifest: stamped with its `stack` and `crid`. Sites with no stamp, or
 * another one, are dropped. Returns null when none remain, so the view says "No site curves yet".
 */
export function sitesForManifest(sites: Site[] | null, m: Manifest): Site[] | null {
  if (!sites) return null;
  const own = sites.filter(
    (s) => typeof s.stack === "string" && typeof s.crid === "string" && s.stack === m.stack && s.crid === m.crid,
  );
  return own.length ? own : null;
}

/** Loads data/sites.json. Returns null if it is absent or unusable; the app then shows "No site curves yet". */
export async function loadSites(url: string): Promise<Site[] | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const json: unknown = await res.json();
    return Array.isArray(json) && json.every(isSite) ? json : null;
  } catch {
    return null;
  }
}
