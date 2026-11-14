import { hasLakeNow, hasLevel, isTrendPass, levelMessage, sortLakes, type Lake, type LakeCheck } from "./lakes";
import { formatDate } from "./format";

/** One line on the lake chart: a track's valid passes, or the passes that were left out. */
export interface LakeChartSeries {
  /** Track name, or "Excluded passes". */
  label: string;
  values: (number | null)[];
  /** True for the single marker-only series that holds the passes left out of the trend. */
  excluded: boolean;
  /** True for the marker-only series of passes taken while the lake was probably frozen (drawn grey). */
  frozen?: boolean;
  /** The edges of the band baseline ± 2 × noise of the status track: "hi" and "lo" (drawn as a shaded band). */
  band?: "hi" | "lo";
  /** True for the marker-only series of the passes that set a Watch, an Alert or a Decrease noted. */
  level?: boolean;
}

export interface LakeChartData {
  /** UTC-midnight seconds, ascending, one entry per date that has any point. */
  x: number[];
  series: LakeChartSeries[];
}

/** Draws area per track. The uPlot version lives in chart.ts; tests pass a fake. */
export type LakeChartFactory = (el: HTMLElement, data: LakeChartData) => { destroy(): void };

/** Marks every lake on a small map. Lazy MapLibre in lakeLocator.ts; the overview's map drawer takes it over (Task 15). */
export type LocatorFactory = (el: HTMLElement, lakes: Lake[], onPick: (id: string) => void) => { highlight(id: string): void; destroy(): void };

const utcSeconds = (iso: string): number => Date.parse(`${iso}T00:00:00Z`) / 1000;

/**
 * Chart columns for a lake: one series per track, never joined across tracks, plus one marker-only series for excluded
 * passes. A pass that saw less than `minObservable` of the lake zone is left off, as the status leaves it out. With a
 * level, the status track's band (baseline ± `factor` × noise, pass by pass) and the passes that set a Watch, an Alert or
 * a Decrease noted are added.
 */
export function lakeChartData(lake: Lake, minObservable = 0, factor = 2): LakeChartData {
  const dates = [...new Set(lake.series.map((p) => p.date))].sort();
  const index = new Map(dates.map((d, i) => [d, i]));
  const tracks = [...new Set(lake.series.map((p) => p.track))].sort();
  const blank = (): (number | null)[] => dates.map(() => null);
  const series: LakeChartSeries[] = [];
  for (const track of tracks) {
    const values = blank();
    for (const p of lake.series) {
      if (p.track === track && isTrendPass(p, minObservable)) values[index.get(p.date)!] = p.area_km2;
    }
    if (values.some((v) => v !== null)) series.push({ label: track, values, excluded: false });
  }
  // The pipeline nulls area_km2 on a left-out pass and keeps what it read as diagnostic_km2 (older builds kept area_km2).
  const out = blank();
  for (const p of lake.series) {
    if (p.excluded === null) continue;
    const v = p.diagnostic_km2 ?? p.area_km2;
    if (v !== null && v !== undefined) out[index.get(p.date)!] = v;
  }
  if (out.some((v) => v !== null)) series.push({ label: "Excluded passes", values: out, excluded: true });
  // Passes taken while the lake was probably frozen keep their area but are no open-water reading: grey markers, no line.
  const ice = blank();
  for (const p of lake.series) {
    if (!p.frozen || p.excluded !== null || p.area_km2 === null) continue;
    if (p.observable_share !== null && p.observable_share < minObservable) continue;
    ice[index.get(p.date)!] = p.area_km2;
  }
  if (ice.some((v) => v !== null)) series.push({ label: "Frozen passes (not open water)", values: ice, excluded: false, frozen: true });
  if (hasLevel(lake) && lake.status.track) {
    const hi = blank();
    const lo = blank();
    for (const p of lake.series) {
      if (p.track !== lake.status.track || typeof p.baseline_km2 !== "number" || typeof p.noise_km2 !== "number") continue;
      hi[index.get(p.date)!] = p.baseline_km2 + factor * p.noise_km2;
      lo[index.get(p.date)!] = Math.max(0, p.baseline_km2 - factor * p.noise_km2);
    }
    if (hi.some((v) => v !== null)) {
      const label = `Baseline ± ${factor} × noise (${lake.status.track})`;
      series.push({ label: `${label}, upper`, values: hi, excluded: false, band: "hi" }, { label: `${label}, lower`, values: lo, excluded: false, band: "lo" });
    }
    const set = blank();
    for (const p of lake.series) {
      if (p.level_contrib && p.level_contrib !== "No change" && p.area_km2 !== null) set[index.get(p.date)!] = p.area_km2;
    }
    if (set.some((v) => v !== null)) series.push({ label: "Passes that set a level", values: set, excluded: false, level: true });
  }
  return { x: dates.map(utcSeconds), series };
}

/**
 * The lake's initial message (a Watch, an Alert or a Decrease noted), as the pipeline wrote it: what changed, how sure,
 * what it is not and what to do. Null without one.
 */
export function messageBox(lake: Lake, cls = "lw-message"): HTMLElement | null {
  const m = levelMessage(lake);
  if (!m) return null;
  const box = document.createElement("section");
  box.className = cls;
  box.dataset.role = "lw-message";
  box.dataset.level = m.level;
  const add = (tag: string, c: string, t: string) => {
    const e = document.createElement(tag);
    e.className = c;
    e.textContent = t;
    box.append(e);
  };
  add("h3", "lw-message-title", m.title);
  add("p", "lw-message-what", m.what);
  add("p", "lw-message-sure", m.how_sure);
  if (m.since) add("p", "lw-message-since", m.since);
  add("p", "lw-message-not", m.not);
  add("p", "lw-message-do", m.do);
  if (!m.since && lake.status.level_since) add("p", "lw-note", `${m.level} since ${formatDate(lake.status.level_since)}.`);
  return box;
}

/** At a site where a lake may be forming: what the radar layer is, and what happens next (no automatic measurement). */
export const FORMING_LAYER =
  "Sentinel-2 shows water here. The blue layer shows the radar dark area. SARtale does not yet treat it as lake area. The SARtale team reviews the site to add it as a measured lake.";
export const FORMING_NO_LAYER =
  "No radar water layer yet. Sentinel-2 shows water here, but no NISAR pass since that scene has been read. The SARtale team reviews the site to add it as a measured lake.";

/**
 * The lake to open on: the one with the most water in its latest trend pass (clearest picture), else the first in list
 * order. A site with no lake now is never picked over a lake: its dark area is not lake water.
 */
export function openingLake(lakes: Lake[], minObservable = 0): Lake {
  const latest = (l: Lake): number => {
    if (!hasLakeNow(l)) return -2;
    const valid = l.series.filter((p) => isTrendPass(p, minObservable)).sort((a, b) => a.date.localeCompare(b.date));
    return valid.length ? valid[valid.length - 1].area_km2! : -1;
  };
  const sorted = sortLakes(lakes);
  return sorted.reduce((best, l) => (latest(l) > latest(best) ? l : best), sorted[0]);
}

/** A single-pass comparison, so it carries its own dates instead of looks and noise. */
export function checkLine(c: LakeCheck): string {
  const iou = c.iou === null ? "" : `, overlap (IoU) ${c.iou.toFixed(2)}`;
  const season = c.season ? ` (open-water season ${c.season})` : "";
  return `One NISAR pass vs one Sentinel-2 scene${season}: NISAR ${c.radar_km2.toFixed(3)} km² on ${formatDate(c.nisar_date)} (${c.nisar_track}), Sentinel-2 ${c.optical_km2.toFixed(3)} km² on ${formatDate(c.s2_date)} (${c.days_apart} days apart, ${Math.round(c.s2_window_cloud_pct)}% cloud in the window)${iou}.`;
}
