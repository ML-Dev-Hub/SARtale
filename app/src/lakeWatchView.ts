import { cloudHeadline, hasLakeNow, isTrendPass, mayBeForming, methodLimits, sortLakes, statusSentence, type Lake, type LakeCheck, type LakesFile } from "./lakes";
import { dataUrl, formatDate } from "./format";
import { statusSlug } from "./lakeLocator";

/** One line on the lake chart: a track's valid passes, or the passes that were left out. */
export interface LakeChartSeries {
  /** Track name, or "Excluded passes". */
  label: string;
  values: (number | null)[];
  /** True for the single marker-only series that holds the passes left out of the trend. */
  excluded: boolean;
}

export interface LakeChartData {
  /** UTC-midnight seconds, ascending, one entry per date that has any point. */
  x: number[];
  series: LakeChartSeries[];
}

/** Draws area per track. The uPlot version lives in chart.ts; tests pass a fake. */
export type LakeChartFactory = (el: HTMLElement, data: LakeChartData) => { destroy(): void };

/** Marks every lake on a small map. Lazy MapLibre in lakeLocator.ts; absent in tests. */
export type LocatorFactory = (el: HTMLElement, lakes: Lake[], onPick: (id: string) => void) => { highlight(id: string): void; destroy(): void };

export interface LakeWatchOptions {
  lakes: LakesFile | null;
  createChart?: LakeChartFactory;
  createLocator?: LocatorFactory;
  onBrief?: (lake: Lake) => void;
  /** Called when the person picks a lake (list row or map pin), not when the view opens on one. */
  onSelect?: (id: string) => void;
}

export interface LakeWatchHandle {
  select(id: string): void;
  destroy(): void;
}

const TEMPLATE = `
<div class="lw-empty" data-role="lw-empty" hidden>
  <p class="sites-empty">No lake data in this build</p>
  <p class="sites-why">Lake Watch needs data/lakes.json, made by the pipeline in processing/.</p>
</div>
<div class="lw-body" data-role="lw-body" hidden>
  <p class="lw-headline"><a href="#cloud-gap" data-role="lw-headline"></a></p>
  <p class="lw-screening" data-role="lw-screening">Indicative screening on provisional NISAR data. Official warnings come from PMD, NDMA, GBDMA and PDMA.</p>
  <div class="lw-grid">
    <nav class="lw-list-wrap" aria-label="Lakes">
      <div class="lw-locator" data-role="lw-locator" aria-label="Where the lakes are"></div>
      <ul class="lw-list" data-role="lw-list"></ul>
    </nav>
    <article class="card lw-detail" data-role="lw-detail" aria-live="polite"></article>
  </div>
</div>`;

const utcSeconds = (iso: string): number => Date.parse(`${iso}T00:00:00Z`) / 1000;

/**
 * Chart columns for a lake: one series per track, never joined across tracks, plus one marker-only series for excluded
 * passes. A pass that saw less than `minObservable` of the lake zone is left off, as the status leaves it out.
 */
export function lakeChartData(lake: Lake, minObservable = 0): LakeChartData {
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
  const out = blank();
  for (const p of lake.series) if (p.excluded !== null && p.area_km2 !== null) out[index.get(p.date)!] = p.area_km2;
  if (out.some((v) => v !== null)) series.push({ label: "Excluded passes", values: out, excluded: true });
  return { x: dates.map(utcSeconds), series };
}

const slug = statusSlug;

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

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A single-pass comparison, so it carries its own dates instead of looks and noise. */
export function checkLine(c: LakeCheck): string {
  const iou = c.iou === null ? "" : `, overlap (IoU) ${c.iou.toFixed(2)}`;
  const season = c.season ? ` (open-water season ${c.season})` : "";
  return `One NISAR pass vs one Sentinel-2 scene${season}: NISAR ${c.radar_km2.toFixed(3)} km² on ${formatDate(c.nisar_date)} (${c.nisar_track}), Sentinel-2 ${c.optical_km2.toFixed(3)} km² on ${formatDate(c.s2_date)} (${c.days_apart} days apart, ${Math.round(c.s2_window_cloud_pct)}% cloud in the window)${iou}.`;
}

export function createLakeWatchView(root: HTMLElement, opts: LakeWatchOptions): LakeWatchHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => root.querySelector<T>(`[data-role="${role}"]`)!;
  const file = opts.lakes;
  const lakes = file?.lakes ?? [];
  const has = lakes.length > 0;
  q("lw-empty").hidden = has;
  q("lw-body").hidden = !has;
  let chart: { destroy(): void } | undefined;
  let locator: { highlight(id: string): void; destroy(): void } | undefined;
  if (!has) return { select() {}, destroy: () => void (root.innerHTML = "") };

  q("lw-headline").textContent = cloudHeadline(file!);

  const listEl = q("lw-list");
  const rows = new Map<string, HTMLButtonElement>();
  for (const lake of sortLakes(lakes)) {
    const li = el("li");
    const b = el("button", "lw-row");
    b.type = "button";
    b.dataset.lakeId = lake.id;
    b.dataset.control = String(lake.role === "control");
    b.setAttribute("aria-pressed", "false");
    const text = el("span", "lw-row-text");
    text.append(
      el("span", `lw-chip lw-status-${slug(lake.status.status)}`, lake.status.status),
      el("span", "lw-name", lake.name),
      el("span", "lw-sentence", statusSentence(lake, file!.constants.change_factor)),
      el("span", "lw-coord", `Coordinates: ${lake.coord_source}`),
    );
    b.append(thumb(lake), text);
    b.addEventListener("click", () => choose(lake.id));
    b.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        choose(lake.id);
      }
    });
    rows.set(lake.id, b);
    li.append(b);
    listEl.append(li);
  }

  const detail = q("lw-detail");

  /** A small radar picture for a list row: latest HH with the water pixels on top. Decorative; the row text names the lake. */
  function thumb(lake: Lake): HTMLElement {
    const t = el("span", "lw-thumb");
    t.setAttribute("aria-hidden", "true");
    for (const [path, cls] of [[lake.images?.latest_hh, "lw-thumb-hh"], [lake.images?.water, "lw-thumb-water"]] as const) {
      if (!path) continue;
      const i = el("img", cls);
      i.src = dataUrl(path);
      i.alt = "";
      i.loading = "lazy";
      t.append(i);
    }
    if (!t.childElementCount) t.dataset.empty = "true";
    return t;
  }

  function pictures(lake: Lake): HTMLElement {
    const wrap = el("div", "lw-pictures");
    const hh = lake.images?.latest_hh ?? null;
    const water = lake.images?.water ?? null;
    if (!hh && !water) {
      wrap.append(el("p", "lw-none", "No radar picture yet"));
      return wrap;
    }
    const stack = el("div", "lw-stack");
    const mk = (path: string, alt: string, cls: string): HTMLImageElement => {
      const i = el("img", cls);
      i.src = dataUrl(path);
      i.alt = alt;
      return i;
    };
    if (hh) stack.append(mk(hh, `Latest HH radar picture of ${lake.name}, north up`, "lw-img lw-img-hh"));
    let waterImg: HTMLImageElement | undefined;
    if (water) {
      waterImg = mk(water, `Water pixels for ${lake.name}, north up`, "lw-img lw-img-water");
      stack.append(waterImg);
    }
    wrap.append(stack);
    if (waterImg) {
      const img = waterImg;
      const label = el("label", "lw-opacity");
      label.append(el("span", undefined, hh ? "Water picture opacity" : "Opacity"));
      const range = el("input");
      range.type = "range";
      range.min = "0";
      range.max = "100";
      range.value = "70";
      img.style.opacity = "0.7";
      range.addEventListener("input", () => (img.style.opacity = String(Number(range.value) / 100)));
      label.append(range);
      wrap.append(label);
    }
    if (!hh) wrap.append(el("p", "lw-none", "No radar picture yet for the latest HH image"));
    if (!water && hasLakeNow(lake)) wrap.append(el("p", "lw-none", "No radar picture yet for the water pixels"));
    if (!water && mayBeForming(lake)) wrap.append(el("p", "lw-note", "No water layer yet: Sentinel-2 shows water here, and SARtale measures it from the next NISAR pass."));
    else if (!water && !hasLakeNow(lake)) wrap.append(el("p", "lw-note", "No water layer: there is no lake at this site now."));
    wrap.append(el("p", "lw-note", "NISAR GCOV crop on the UTM grid, north up, about 6 km across. A picture, not an interactive map."));
    return wrap;
  }

  /** Every pass as a table, folded: the chart's values for keyboard and screen-reader use, plus the passes it leaves out. */
  function readingsTable(lake: Lake, minObs: number): HTMLElement {
    const box = el("details", "lw-readings");
    box.dataset.role = "lw-readings";
    box.append(el("summary", undefined, `Every pass as a table (${lake.series.length})`));
    const wrap = el("div", "lw-table-wrap");
    const t = el("table", "lw-table");
    t.append(el("caption", undefined, `NISAR passes over ${lake.name}: water area by date and track`));
    const thead = el("thead");
    const head = el("tr");
    for (const h of ["Date", "Track", "Area (km²)", "Zone seen", "Used", "Version"]) {
      const th = el("th", undefined, h);
      th.scope = "col";
      head.append(th);
    }
    thead.append(head);
    const tbody = el("tbody");
    const order = [...lake.series].sort((a, b) => a.date.localeCompare(b.date) || a.track.localeCompare(b.track));
    for (const p of order) {
      const used = p.excluded !== null ? `Left out: ${p.excluded}`
        : p.area_km2 === null ? "No reading"
        : p.observable_share === null ? "Zone share unknown"
        : isTrendPass(p, minObs) ? "Yes" : "Too little of the zone seen";
      const tr = el("tr");
      tr.append(
        el("td", undefined, formatDate(p.date)),
        el("td", undefined, p.track),
        el("td", undefined, p.area_km2 === null ? "–" : p.area_km2.toFixed(3)),
        el("td", undefined, p.observable_share === null ? "–" : `${Math.round(p.observable_share * 100)}%`),
        el("td", undefined, used),
        el("td", undefined, p.crid ?? "–"),
      );
      tbody.append(tr);
    }
    t.append(thead, tbody);
    wrap.append(t);
    box.append(wrap);
    return box;
  }

  function section(title: string, items: string[]): HTMLElement {
    const sec = el("section", "lw-section");
    sec.append(el("h3", undefined, title));
    const ul = el("ul", "lw-bullets");
    for (const t of items) ul.append(el("li", undefined, t));
    sec.append(ul);
    return sec;
  }

  function render(lake: Lake): void {
    chart?.destroy();
    chart = undefined;
    detail.replaceChildren();
    const head = el("header", "card-head");
    head.append(el("h2", "lw-title", lake.name), el("span", `lw-chip lw-status-${slug(lake.status.status)}`, lake.status.status));
    detail.append(
      head,
      el("p", "lw-sentence-big", statusSentence(lake, file!.constants.change_factor)),
      el("p", "lw-scope", `Measures: ${lake.area_label}. Indicative screening on provisional data. Official warnings come from PMD, NDMA, GBDMA and PDMA.`),
      pictures(lake),
    );

    // With too few looks or no observable zone the earlier points are not a trend: show the reason, not a chart.
    // A site with no lake now has no area curve: its dark radar area is not lake water.
    const noTrend = lake.status.status === "Not observable" || lake.status.status === "Not enough NISAR looks yet" || !hasLakeNow(lake);
    const minObs = file!.constants.min_observable;
    const data = lakeChartData(lake, minObs);
    const chartSec = el("section", "lw-section");
    chartSec.append(el("h3", undefined, "Area by track"));
    if (noTrend) {
      chartSec.append(el("p", "lw-none", lake.status.reason));
    } else if (!data.series.length) {
      chartSec.append(el("p", "lw-none", "No area curve yet"));
    } else if (opts.createChart) {
      const host = el("div", "lw-chart");
      chartSec.append(host, el("p", "lw-note", `One line per track. Hollow markers are passes left out of the trend; passes that saw less than ${Math.round(minObs * 100)}% of the lake zone are not drawn. The table lists every pass.`));
      chart = opts.createChart(host, data);
    }
    if (lake.series.length) chartSec.append(readingsTable(lake, minObs));
    detail.append(chartSec);

    for (const check of (file?.checks ?? []).filter((c) => c.lake === lake.id)) detail.append(el("p", "lw-check", checkLine(check)));
    for (const n of (file?.check_notes ?? []).filter((c) => c.lake === lake.id)) detail.append(el("p", "lw-check", `Sentinel-2 check: ${n.note}.`));
    // Standing limits of the method, shown for every lake; the lake's own limits follow when it has any.
    const method = section("Method limits", methodLimits(file!));
    method.dataset.role = "lw-method-limits";
    detail.append(method);
    if (lake.limits.length) detail.append(section("Limits for this lake", lake.limits));
    if (lake.excluded.length) detail.append(section("Excluded passes", lake.excluded.map((x) => `${x.pass}: ${x.reason}`)));
    if (lake.downstream) detail.append(el("p", "lw-downstream", `Downstream: ${lake.downstream}${lake.downstream_source ? ` (${lake.downstream_source})` : ""}`));
    detail.append(el("p", "lw-coords", `Coordinates: ${lake.coord_source}`));
    if (lake.outline_source) detail.append(el("p", "lw-coords", `Outline: ${lake.outline_source}`));
    const brief = el("button", "btn lw-brief", "Print lake brief");
    brief.type = "button";
    brief.dataset.role = "lw-brief";
    brief.addEventListener("click", () => opts.onBrief?.(lake));
    detail.append(brief);
  }

  function select(id: string): boolean {
    const lake = lakes.find((l) => l.id === id);
    if (!lake) return false;
    for (const [rid, b] of rows) b.setAttribute("aria-pressed", String(rid === id));
    render(lake);
    locator?.highlight(id);
    return true;
  }

  /** The person picked a lake: show it, tell the shell, and on a one-column layout bring the panel into view. */
  function choose(id: string): void {
    if (!select(id)) return;
    opts.onSelect?.(id);
    if (window.matchMedia?.("(max-width: 900px)").matches) {
      const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      detail.scrollIntoView?.({ block: "start", behavior: still ? "auto" : "smooth" });
    }
  }

  if (opts.createLocator) locator = opts.createLocator(q("lw-locator"), lakes, (id) => choose(id));
  // Open on a lake from the start, so the panel shows radar pictures and a chart instead of an empty prompt.
  select(openingLake(lakes, file!.constants.min_observable).id);

  return {
    select: (id) => void select(id),
    destroy: () => {
      chart?.destroy();
      locator?.destroy();
      root.innerHTML = "";
    },
  };
}
