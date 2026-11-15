import { formatDate } from "../format";
import { isFrozen, isTrendPass, type Lake } from "../lakes";
import { lakeChartData, statusTrackName, statusTrackPasses, type LakeChartFactory } from "../lakeWatchView";
import { el } from "../overview/marks";

export interface ReadingRow {
  d: string;
  area: string;
  z: string;
  base: string;
  crid: string;
  note: string;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const NEWEST = 6;
const DASH = "—";

/** "History on track 055A, June to November 2026" (years shown on both ends when the history spans two). */
export function historyHeading(l: Lake): string {
  const ds = statusTrackPasses(l).map((p) => p.date);
  const track = statusTrackName(l);
  if (!ds.length) return `History on track ${track}`;
  const [y0, m0] = [ds[0].slice(0, 4), MONTHS[+ds[0].slice(5, 7) - 1]];
  const [y1, m1] = [ds[ds.length - 1].slice(0, 4), MONTHS[+ds[ds.length - 1].slice(5, 7) - 1]];
  return y0 === y1 ? `History on track ${track}, ${m0} to ${m1} ${y1}` : `History on track ${track}, ${m0} ${y0} to ${m1} ${y1}`;
}

const sign = (v: number): string => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1));

function noteFor(p: Lake["series"][number]): string {
  const n: string[] = [];
  if (p.excluded !== null) n.push(`Left out: ${p.excluded}`);
  else if (p.area_km2 === null) n.push("No usable reading");
  else if (p.frozen) n.push("Probably frozen: not an open-water reading, left out of baselines and noise");
  else if (p.observable_share !== null && p.observable_share < 0.5) n.push(`Saw ${Math.round(p.observable_share * 100)}% of the lake zone`);
  if (p.new_version) n.push(`First pass on processing version ${p.crid ?? "new"}: it can raise a Watch, not an Alert`);
  if (p.after_open) n.push("First pass after the lake opened: only rebuilds the baseline");
  if (p.level_contrib && p.level_contrib !== "No change") n.push(`Set a ${p.level_contrib}`);
  return n.join(". ");
}

/** The status track's readings, newest first: the newest six, or all of them. */
export function readingRows(l: Lake, all: boolean): ReadingRow[] {
  const rows = statusTrackPasses(l).reverse().map((p) => ({
    d: formatDate(p.date),
    area: p.area_km2 === null ? DASH : p.area_km2.toFixed(3),
    z: typeof p.z === "number" ? sign(p.z) : DASH,
    base: typeof p.baseline_km2 === "number" ? p.baseline_km2.toFixed(3) : DASH,
    crid: p.crid ?? DASH,
    note: noteFor(p),
  }));
  return all ? rows : rows.slice(0, NEWEST);
}

export interface HistoryOptions {
  minObservable: number;
  factor: number;
  createChart?: LakeChartFactory;
  /** Draw the readings as stacked rows, not a table (a phone). */
  phone?: boolean;
}

const NS = "http://www.w3.org/2000/svg";
function swatch(inner: (svg: SVGElement) => void, w = 14): SVGElement {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("width", String(w));
  s.setAttribute("height", "14");
  s.setAttribute("aria-hidden", "true");
  inner(s);
  return s;
}
function shape(tag: string, attrs: Record<string, string>): SVGElement {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

/** The legend: each entry has a shape as well as a colour. Only what the chart draws is listed. */
function legend(data: ReturnType<typeof lakeChartData>, track: string, factor: number): HTMLElement {
  const ul = el("ul", "lp-legend");
  const add = (svg: SVGElement, text: string): void => {
    const li = el("li");
    li.append(svg, text);
    ul.append(li);
  };
  add(swatch((s) => s.append(shape("circle", { cx: "7", cy: "7", r: "5", class: "lg-open" }))), `Open-water reading on ${track}`);
  if (data.series.some((s) => s.frozen)) add(swatch((s) => s.append(shape("circle", { cx: "7", cy: "7", r: "5", class: "lg-frozen" }))), "Frozen pass (greyed, left out)");
  if (data.series.some((s) => s.bridge)) add(swatch((s) => s.append(shape("line", { x1: "0", y1: "7", x2: "26", y2: "7", class: "lg-bridge" })), 26), "Line dashed across a pass with no usable reading");
  const levels = [...new Set(data.series.flatMap((s) => (s.level && s.levelName ? [s.levelName] : [])))];
  for (const lv of levels) add(swatch((s) => s.append(shape("circle", { cx: "7", cy: "7", r: "5", class: `lg-level lg-level-${lv.split(":")[0].toLowerCase().replace(/ /g, "-")}` }))), `Pass that set the level: ${lv.replace("Alert: growing", "Alert")}`);
  if (data.series.some((s) => s.band)) add(swatch((s) => s.append(shape("rect", { x: "0", y: "2", width: "22", height: "10", class: "lg-band" })), 22), `Normal range (baseline ± ${factor} × radar noise)`);
  if (data.series.some((s) => s.rail)) add(swatch((s) => s.append(shape("circle", { cx: "7", cy: "7", r: "5", class: "lg-rail" }))), "No usable reading (own rail)");
  if (data.series.some((s) => s.version)) add(swatch((s) => s.append(shape("line", { x1: "7", y1: "0", x2: "7", y2: "14", class: "lg-version" }))), "Processing version change");
  return ul;
}

/** One reading per row, stacked: date and area, then z, baseline and version, then the note. No sideways scroll. */
function stacked(l: Lake, all: boolean): HTMLElement {
  const ul = el("ul", "lp-reading-list");
  for (const r of readingRows(l, all)) {
    const li = el("li", "lp-reading");
    li.dataset.role = "lp-reading";
    const top = el("span", "lp-reading-top");
    top.append(el("strong", undefined, r.d), el("span", "lp-reading-area", r.area === DASH ? DASH : `${r.area} km²`));
    const mid = el("span", "lp-reading-mid");
    mid.append(el("span", undefined, `z ${r.z} · baseline ${r.base}`), el("span", undefined, r.crid));
    li.append(top, mid);
    if (r.note) li.append(el("span", "lp-note", r.note));
    ul.append(li);
  }
  return ul;
}

function table(l: Lake, all: boolean): HTMLElement {
  const wrap = el("div", "lp-table-wrap");
  const t = el("div", "lp-table");
  t.setAttribute("role", "table");
  t.setAttribute("aria-label", "Readings, newest first");
  const head = el("div", "lp-row lp-row-head");
  head.setAttribute("role", "row");
  ["Date", "Area (km²)", "z", "Baseline", "Version", "Note"].forEach((h, i) => {
    const c = el("span", i >= 1 && i <= 3 ? "lp-num" : undefined, h);
    c.setAttribute("role", "columnheader");
    head.append(c);
  });
  t.append(head);
  for (const r of readingRows(l, all)) {
    const row = el("div", "lp-row");
    row.setAttribute("role", "row");
    [r.d, r.area, r.z, r.base, r.crid, r.note].forEach((v, i) => {
      const c = el("span", i >= 1 && i <= 3 ? "lp-num" : i === 5 ? "lp-note" : undefined, v);
      c.setAttribute("role", "cell");
      row.append(c);
    });
    t.append(row);
  }
  wrap.append(t);
  return wrap;
}

/**
 * Draws the status-track area chart and the readings table into body. Returns false when the lake has no pass on its
 * status track, so the block is not drawn. The chart is drawn when a factory is given; the table is always drawn.
 */
export function renderHistory(body: HTMLElement, l: Lake, o: HistoryOptions): boolean {
  const passes = statusTrackPasses(l);
  const track = statusTrackName(l);
  if (!passes.length || !track) return false;
  const others = [...new Set(l.series.map((p) => p.track))].filter((t) => t !== track).sort();
  const data = lakeChartData(l, o.minObservable, o.factor, { statusTrackOnly: true });

  if (o.createChart) {
    body.append(legend(data, track, o.factor));
    const host = el("div", "lp-chart");
    host.setAttribute("role", "img");
    host.setAttribute("aria-label", `Area readings on track ${track}, ${passes.length} passes`);
    body.append(host);
    o.createChart(host, data);
  }
  if (isFrozen(l)) {
    body.append(el("p", "lp-chart-note", "No reference band is drawn: frozen passes are left out of the baseline and noise, and the lake has no current assessment until it opens again."));
  }
  const valid = passes.filter((p) => isTrendPass(p, o.minObservable));
  if (valid.length) {
    const big = valid.reduce((m, p) => (p.area_km2! > m.area_km2! ? p : m));
    body.append(el("p", "lp-caption", `Largest valid reading on ${track}, ${big.date.slice(0, 4)} season: ${big.area_km2!.toFixed(3)} km² on ${formatDate(big.date)}.`));
  }
  body.append(el("p", "lp-caption", "A track is one repeating NISAR orbit path (e.g. 084A). Each track sees the lake from its own angle, so the chart compares a lake only with readings from the same track."));
  body.append(el("p", "lp-caption", `Only ${track} readings are drawn: each track sees the lake from its own angle, so readings from ${others.length ? others.join(", ") : "other tracks"} are compared only with their own track.`));

  const sec = el("div", "lp-readings");
  sec.append(el("h3", undefined, `Readings on ${track}`));
  let all = false;
  const holder = el("div");
  const btn = el("button", "lp-btn lp-showall");
  btn.type = "button";
  const draw = (): void => {
    holder.replaceChildren(o.phone ? stacked(l, all) : table(l, all));
    btn.textContent = all ? `Show only the newest ${NEWEST}` : `Show all ${passes.length} readings`;
    btn.setAttribute("aria-expanded", String(all));
  };
  btn.addEventListener("click", () => {
    all = !all;
    draw();
  });
  draw();
  sec.append(holder);
  if (passes.length > NEWEST) sec.append(btn);
  body.append(sec);
  return true;
}
