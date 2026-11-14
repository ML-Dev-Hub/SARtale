import { formatDate } from "../format";
import { isFrozen, type Lake } from "../lakes";

/** What the gauge draws: the change, the lake's noise, the pipeline's decision band, and whether the marker is hollow. */
export interface GaugeInput {
  change: number;
  noise: number;
  band: number;
  floorApplied: boolean;
  hollow: boolean;
}

export interface GaugeGeometry {
  band: number;
  extent: number;
  x: (v: number) => number;
  /** Null when the change is beyond the scale (an arrow is drawn instead). */
  markerX: number | null;
  overflow: "left" | "right" | null;
  nudged: boolean;
  label: string;
}

const NUDGE_PX = 2;
const SVG_WIDTH = 900;

const signed = (v: number, digits: number): string => `${v < 0 ? "−" : "+"}${Math.abs(v).toFixed(digits)}`;

/**
 * Positions for the gauge, from full-precision values. The band is the pipeline's decision threshold; the scale is
 * ±4 × noise. A change with |change| >= band is beyond the band (the pipeline's |z| >= 2 test), so on the band edge it
 * sits just outside, on its own side; a marker within 2 px of the edge is nudged to exactly 2 px on the side the exact
 * comparison puts it.
 */
export function gaugeGeometry(g: GaugeInput, width: number, pad = 24): GaugeGeometry {
  const band = g.band;
  const extent = Math.max(4 * g.noise, 2 * band, 1e-9);
  const x = (v: number): number => pad + ((v + extent) / (2 * extent)) * (width - 2 * pad);
  const side = g.change < 0 ? -1 : 1;
  if (Math.abs(g.change) > extent) {
    return { band, extent, x, markerX: null, overflow: side < 0 ? "left" : "right", nudged: false, label: `${signed(g.change, 4)} km² · beyond this scale` };
  }
  const outside = Math.abs(g.change) >= band;
  const edge = x(side * band);
  let markerX = x(g.change);
  let nudged = false;
  if (Math.abs(markerX - edge) < NUDGE_PX) {
    markerX = edge + side * (outside ? NUDGE_PX : -NUDGE_PX);
    nudged = true;
  }
  const label = `${signed(g.change, 4)} km²${nudged && !outside ? " · within threshold (rounded values shown)" : ""}`;
  return { band, extent, x, markerX, overflow: null, nudged, label };
}

/** The latest valid reading of the status track, for its area and the share of the zone observable on that pass. */
function latestPoint(l: Lake): Lake["series"][number] | null {
  const track = l.status.track;
  const date = l.status.latest_date;
  const pts = l.series.filter((p) => p.area_km2 !== null && p.excluded === null && !p.frozen && (!track || p.track === track));
  return pts.find((p) => p.date === date) ?? pts.sort((a, b) => a.date.localeCompare(b.date)).pop() ?? null;
}

/** The gauge's numbers, or null when there is none to draw: a frozen lake, or one without a baseline, noise or change. */
export function gaugeInput(l: Lake, factor: number): GaugeInput | null {
  if (isFrozen(l)) return null;
  const s = l.status;
  if (s.baseline_km2 == null || s.noise_km2 == null || s.change_km2 == null) return null;
  const band = s.threshold_km2 ?? factor * s.noise_km2;
  return {
    change: s.change_km2,
    noise: s.noise_km2,
    band,
    floorApplied: s.noise_floor_applied === true,
    hollow: s.status === "Not yet validated against Sentinel-2" || s.status === "Not measurable",
  };
}

const NS = "http://www.w3.org/2000/svg";

function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, text?: string): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  return e;
}

function p(text: string, cls?: string): HTMLParagraphElement {
  const e = document.createElement("p");
  if (cls) e.className = cls;
  e.textContent = text;
  return e;
}

/** The heading for the gauge block: "Change against baseline · 9 Nov 2026". */
export function gaugeHeading(l: Lake): string {
  const d = l.status.latest_date?.slice(0, 10);
  return d && /^\d{4}-\d{2}-\d{2}$/.test(d) ? `Change against baseline · ${formatDate(d)}` : "Change against baseline";
}

/** Draws the gauge and its numbers into `el`. Draws nothing when `gaugeInput` has nothing. */
export function renderGauge(el: HTMLElement, l: Lake, factor: number, phone = false): void {
  el.replaceChildren();
  const g = gaugeInput(l, factor);
  if (!g) return;
  const s = l.status;
  const t = s.track ?? "same-track";
  const base = s.baseline_km2 as number;
  const pt = latestPoint(l);

  el.append(p(`Latest valid ${t} reading minus the median of up to 6 earlier valid ${t} readings`, "lp-gauge-sub"));

  if (pt?.area_km2 != null) {
    const row = document.createElement("div");
    row.className = "lp-gauge-area";
    const big = p(`${pt.area_km2.toFixed(3)} km²`, "lp-gauge-value");
    row.append(big, p(`Radar-read ${l.area_label}`, "lp-gauge-areaname"));
    el.append(row);
  }

  const pctText = base > 0 ? ` (${signed((g.change / base) * 100, 0)}%)` : "";
  const d = s.latest_date?.slice(0, 10);
  const passText = d && /^\d{4}-\d{2}-\d{2}$/.test(d) ? `Newest pass, ${formatDate(d)}${s.track ? ` (${s.track})` : ""}: baseline` : "Baseline";
  const observable = pt?.observable_share != null ? ` · zone observable on this pass ${Math.round(pt.observable_share * 100)}%` : "";
  const z = s.z != null ? ` · z ${signed(s.z, 1)}` : "";
  el.append(p(`${passText} ${base.toFixed(3)} km² · change ${signed(g.change, 3)} km²${pctText} · noise ${g.noise.toFixed(3)} km²${z}${observable}`, "lp-gauge-numbers"));

  // On a phone the drawing is 358 units wide, so its text keeps its size and the short labels fit.
  const W = phone ? 358 : SVG_WIDTH;
  const geo = gaugeGeometry(g, W);
  const { x, band, extent } = geo;
  const inside = Math.abs(g.change) < band;
  const where = geo.overflow ? `beyond the scale of plus or minus ${extent.toFixed(3)}` : inside ? "inside the band" : g.change > 0 ? "above the band, larger than usual" : "below the band, smaller than usual";
  const aria = `Change gauge for ${l.name}${s.latest_date ? `, ${s.latest_date.slice(0, 10)}` : ""}: ${signed(g.change, 4)} square kilometres against a band of plus or minus ${band.toFixed(4)}, ${where}. Scale plus or minus ${extent.toFixed(3)}.${g.hollow ? " Not yet confirmed." : ""}`;

  const root = svg("svg", { viewBox: `0 0 ${W} 130`, width: "100%", role: "img", "aria-label": aria, class: "lp-gauge-svg" });
  root.append(svg("rect", { x: x(-extent), y: 34, width: x(extent) - x(-extent), height: 44, class: "lp-g-scale" }));
  root.append(svg("rect", { x: x(-band), y: 34, width: x(band) - x(-band), height: 44, class: "lp-g-band" }));
  root.append(svg("line", { x1: x(-band), x2: x(-band), y1: 34, y2: 78, class: "lp-g-edge" }));
  root.append(svg("line", { x1: x(band), x2: x(band), y1: 34, y2: 78, class: "lp-g-edge" }));
  root.append(svg("line", { x1: x(0), x2: x(0), y1: 30, y2: 82, class: "lp-g-zero" }));

  let labelX = geo.markerX ?? 0;
  let anchor = "middle";
  if (geo.markerX !== null) {
    const cls = `lp-g-marker${g.hollow ? " lp-g-hollow" : ""}`;
    root.append(svg("rect", { x: geo.markerX - 2.5, y: 26, width: 5, height: 60, class: cls }));
    anchor = geo.markerX > W - 150 ? "end" : geo.markerX < 150 ? "start" : "middle";
  } else {
    const dir = geo.overflow === "right" ? 1 : -1;
    const ax = dir > 0 ? x(extent) + 2 : x(-extent) - 2;
    root.append(svg("path", { d: `M${ax} 40 L${ax + dir * 16} 56 L${ax} 72 Z`, class: "lp-g-arrow" }));
    labelX = dir > 0 ? W - 2 : 2;
    anchor = dir > 0 ? "end" : "start";
  }
  root.append(svg("text", { x: labelX, y: 20, "text-anchor": anchor, class: "lp-g-value" }, geo.label));
  root.append(svg("text", { x: (x(-extent) + x(-band)) / 2, y: 100, "text-anchor": "middle", class: "lp-g-zone" }, phone ? "Smaller" : "Smaller than usual"));
  root.append(svg("text", { x: x(0), y: 100, "text-anchor": "middle", class: "lp-g-zone" }, phone ? `Within ±${band.toFixed(3)}` : `Within ±${band.toFixed(3)} km² (threshold)`));
  root.append(svg("text", { x: (x(band) + x(extent)) / 2, y: 100, "text-anchor": "middle", class: "lp-g-zone" }, phone ? "Larger" : "Larger than usual"));
  root.append(svg("text", { x: x(-extent), y: 124, "text-anchor": "start", class: "lp-g-tick" }, phone ? `−${extent.toFixed(3)}` : `−${extent.toFixed(3)} km²`));
  root.append(svg("text", { x: x(0), y: 124, "text-anchor": "middle", class: "lp-g-tick" }, phone ? `0 = ${base.toFixed(3)}` : `0 = baseline ${base.toFixed(3)} km²`));
  root.append(svg("text", { x: x(extent), y: 124, "text-anchor": "end", class: "lp-g-tick" }, phone ? `+${extent.toFixed(3)}` : `+${extent.toFixed(3)} km²`));
  el.append(root);

  const notes: string[] = [];
  if (g.floorApplied) notes.push("Noise: minimum noise used, because this lake's own noise was below the minimum.");
  if (g.hollow) notes.push(`${s.status}: the marker is hollow because the reading is not confirmed.`);
  notes.push(`The scale is this lake's own, ±4 × noise; a change beyond it shows an arrow and its exact value.`);
  el.append(p(notes.join(" "), "lp-gauge-note"));
}
