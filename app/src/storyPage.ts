import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/inter-tight/wght.css";
import "./storyPage.css";
import copyJson from "./content/storyPage.json";
import { dataUrl, formatDate } from "./format";
import { isOpen, mountAddLake, requestLine, type LakeRequest, type RequestsClient } from "./lakeRequests";
import { iouRange, opticalOverlapPhrase, type Lake, type LakesFile } from "./lakes";

const copy = copyJson;
const DASH = "—";

export interface StoryNumbers {
  lakes: string;
  cloudLooks: string;
  passes: string;
  attabadArea: string;
  attabadNoise: string;
  attabadLooks: string;
  attabadTrack: string;
  iou: string;
  latest: string;
}

export interface StoryPageOptions {
  onOpenLakes(): void;
  onOpenEvidence(): void;
  onFollowStory(): void;
  /** The lake-request server. Without it the form says requests are not open. */
  requests?: RequestsClient;
}

export interface StoryPage {
  destroy(): void;
  listEl: HTMLElement;
  mapEl: HTMLElement;
  addLakeEl: HTMLElement;
  /** Show these open lake requests in the list and on the map, replacing the earlier ones. */
  setRequests(open: LakeRequest[]): void;
}

/** The pictured pass's area: the series point on the status track's latest date. */
function latestArea(lake: Lake): number | null {
  const s = lake.status;
  const p = lake.series.find((x) => x.date === s.latest_date && x.track === s.track);
  return p && p.area_km2 !== null ? p.area_km2 : null;
}

function areaText(v: number | null): string {
  if (v === null) return DASH;
  return `${v.toFixed(v < 0.01 ? 3 : 2)} km²`;
}

function attabad(file: LakesFile | null): Lake | null {
  return file?.lakes.find((l) => l.id === "attabad") ?? null;
}

/** Every number on the page, read from lakes.json. "—" for anything missing. */
export function storyNumbers(file: LakesFile | null): StoryNumbers {
  if (!file) {
    return { lakes: DASH, cloudLooks: DASH, passes: DASH, attabadArea: DASH, attabadNoise: DASH, attabadLooks: DASH, attabadTrack: DASH, iou: DASH, latest: DASH };
  }
  const a = attabad(file);
  const dates = file.lakes.map((l) => l.status.latest_date).filter((d): d is string => !!d);
  const latest = dates.length ? dates.reduce((x, y) => (x > y ? x : y)) : null;
  const noise = a?.status.noise_km2;
  return {
    lakes: String(file.lakes.length),
    cloudLooks: String(file.lakes.reduce((n, l) => n + l.cloud_window_looks, 0)),
    passes: String(file.lakes.reduce((n, l) => n + l.series.length, 0)),
    attabadArea: a ? areaText(latestArea(a)) : DASH,
    attabadNoise: noise === null || noise === undefined ? DASH : `±${noise.toFixed(2)}`,
    attabadLooks: a ? String(a.status.looks) : DASH,
    attabadTrack: a?.status.track ?? DASH,
    iou: iouRange(file.checks) ?? DASH,
    latest: latest ? formatDate(latest) : DASH,
  };
}

const MAP = { w: 70.8, e: 76.6, s: 34.4, n: 37.6 };

/** Position of a point on north_map.jpg (equirectangular), as CSS percentages; null outside the map. */
export function mapPin(lon: number, lat: number): { left: string; top: string } | null {
  if (!(lon >= MAP.w && lon <= MAP.e && lat >= MAP.s && lat <= MAP.n)) return null;
  return {
    left: `${(((lon - MAP.w) / (MAP.e - MAP.w)) * 100).toFixed(1)}%`,
    top: `${(((MAP.n - lat) / (MAP.n - MAP.s)) * 100).toFixed(1)}%`,
  };
}

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

/** A whole count in words when small ("three"), digits otherwise. */
function countWord(n: number | undefined): string {
  if (n === undefined || !Number.isInteger(n) || n < 0) return DASH;
  return WORDS[n] ?? String(n);
}

/** A share as "half" or a percentage. */
function shareWord(v: number | undefined): string {
  if (v === undefined || !Number.isFinite(v)) return DASH;
  return v === 0.5 ? "half" : `${Math.round(v * 100)}%`;
}

function tokensFor(file: LakesFile | null): Record<string, string> {
  const a = attabad(file);
  const date = a?.images?.date ?? a?.status.latest_date ?? null;
  return {
    ...storyNumbers(file),
    minLooks: countWord(file?.constants.min_looks),
    minObservable: shareWord(file?.constants.min_observable),
    attabadName: a ? a.name.split(" (")[0] : DASH,
    attabadStatus: a?.status.status ?? DASH,
    attabadDate: date ? formatDate(date) : DASH,
    attabadDay: date ? formatDate(date).replace(/ \d{4}$/, "") : DASH,
  };
}

function fill(text: string, tokens: Record<string, string>): string {
  return text.replace(/\{(\w+)\}/g, (_, k: string) => tokens[k] ?? DASH);
}

type Child = Node | string;

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, ...kids: Child[]): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  for (const k of kids) e.append(k);
  return e;
}

function text<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string | undefined, t: string): HTMLElementTagNameMap[K] {
  const e = el(tag, cls);
  e.textContent = t;
  return e;
}

function link(href: string, label: string): HTMLAnchorElement {
  const a = text("a", undefined, label);
  a.href = href;
  a.rel = "noopener";
  return a;
}

function img(src: string, alt: string): HTMLImageElement {
  const i = document.createElement("img");
  i.src = src;
  i.alt = alt;
  i.loading = "lazy";
  return i;
}

function section(label: string, cls: string): HTMLElement {
  const s = el("section", cls);
  s.setAttribute("aria-label", label);
  return s;
}

function eyebrow(label: string): HTMLElement {
  return text("p", "sp-eyebrow", label);
}

function statusClass(status: string): string {
  if (status === "Stable") return "sp-st-stable";
  if (status === "Growing" || status === "Shrinking") return "sp-st-change";
  return "sp-st-other";
}

export function renderStoryPage(root: HTMLElement, file: LakesFile | null, opts: StoryPageOptions): StoryPage {
  const t = tokensFor(file);
  const f = (s: string) => fill(s, t);
  const page = el("div", "sp-page");
  const cleanups: (() => void)[] = [];

  const button = (label: string, cls: string, handler: () => void): HTMLButtonElement => {
    const b = text("button", `sp-btn ${cls}`, label);
    b.type = "button";
    b.addEventListener("click", handler);
    cleanups.push(() => b.removeEventListener("click", handler));
    return b;
  };

  // Cover. The app shell lays its own header over the top padding.
  const c = copy.cover;
  const cover = section("Cover", "sp-cover");
  const shade = el("div", "sp-cover-shade");
  shade.setAttribute("aria-hidden", "true");
  const floor = el("div", "sp-cover-floor");
  floor.setAttribute("aria-hidden", "true");
  const stats = el("div", "sp-stats");
  for (const s of c.stats) stats.append(el("div", undefined, text("div", "sp-stat-value", f(s.value)), text("div", "sp-stat-label", f(s.label))));
  cover.append(
    img(c.image, c.imageAlt),
    shade,
    floor,
    el(
      "div",
      "sp-cover-body",
      el(
        "div",
        "sp-cover-text",
        text("p", "sp-kicker", c.eyebrow),
        text("h1", undefined, c.title),
        text("p", "sp-lede", c.lede),
        el("div", "sp-actions", button(c.followLabel, "sp-btn-primary", opts.onFollowStory), button(c.openLabel, "sp-btn-ghost", opts.onOpenLakes)),
        stats,
      ),
    ),
    text("p", "sp-credit sp-cover-credit", c.credit),
  );

  // 01 The risk
  const r = copy.risk;
  const facts = el("div", "sp-facts");
  for (const x of r.facts) facts.append(el("div", "sp-fact", text("div", "sp-fact-value", x.value), text("div", "sp-fact-label", x.label), text("div", "sp-src", x.source)));
  const risk = section("01 The risk", "sp-section sp-risk");
  risk.append(
    el("div", undefined, eyebrow(r.label), text("h2", undefined, r.title)),
    el("div", "sp-risk-body", el("div", undefined, text("p", "sp-prose", r.body), text("p", "sp-src", r.source)), facts),
  );

  // 02 The gap
  const g = copy.gap;
  const quote = el("blockquote", "sp-quote", link(g.url, `“${g.quote}”`));
  const gap = section("02 The gap", "sp-section");
  gap.append(el("figure", "sp-panel sp-gap", eyebrow(g.label), quote, el("figcaption", undefined, link(g.url, g.cite), ` · ${g.host}`)));

  // 03 The view
  const v = copy.view;
  const shot = (p: typeof v.optical): HTMLElement =>
    el("figure", "sp-shot", img(p.image, p.alt), el("figcaption", undefined, text("span", "sp-shot-name", p.name), text("span", "sp-muted", p.note), text("span", "sp-credit", p.credit)));
  const cards = el("div", "sp-cards");
  for (const k of v.shadow.cards) cards.append(el("div", `sp-card sp-card-${k.tone}`, text("div", "sp-card-label", k.label), text("p", undefined, f(k.text))));
  const src = el("p", "sp-fine", v.shadow.sourcesLead);
  for (const s of v.shadow.sources) src.append(link(s.url, s.text), s.after);
  const view = section("03 The view", "sp-section");
  view.append(
    el("div", "sp-head", el("div", undefined, eyebrow(v.label), text("h2", undefined, v.title)), text("p", "sp-muted sp-head-note", v.lede)),
    el("div", "sp-pair", shot(v.optical), shot(v.radar)),
    el("div", "sp-panel sp-shadow", text("h3", undefined, v.shadow.title), text("p", "sp-shadow-lede", v.shadow.lede), cards, src),
  );

  // 04 The measure
  const m = copy.measure;
  const a = attabad(file);
  const steps = el("ol", "sp-steps");
  m.steps.forEach((s, i) => steps.append(el("li", undefined, text("span", "sp-step-n", String(i + 1)), text("span", undefined, s))));
  const nums = el("div", "sp-numbers");
  for (const n of m.numbers) nums.append(el("div", undefined, text("div", `sp-num-value${"accent" in n ? " sp-accent" : ""}`, f(n.value)), text("div", "sp-stat-label", f(n.label))));
  const measure = section("04 The measure", "sp-section sp-measure");
  if (a?.images?.latest_hh) {
    const fig = el("figure", "sp-overlay");
    const stack = el("div", "sp-overlay-stack", img(dataUrl(a.images.latest_hh), f(m.imageAlt)));
    if (a.images.water) {
      const w = img(dataUrl(a.images.water), m.waterAlt);
      w.className = "sp-water";
      stack.append(w);
    }
    fig.append(stack, text("figcaption", undefined, f(m.caption)));
    measure.append(fig);
  }
  measure.append(el("div", "sp-measure-text", eyebrow(m.label), text("h2", undefined, m.title), steps, nums));

  // 05 The watch
  const w = copy.watch;
  const noData = !file;
  const mapEl = el("figure", "sp-map", img(w.mapImage, w.mapAlt));
  const listEl = el("div", "sp-lakes");
  const lakes = [...(file?.lakes ?? [])].sort((x, y) => (latestArea(y) ?? -1) - (latestArea(x) ?? -1));
  for (const l of lakes) {
    const pos = mapPin(l.lon, l.lat);
    if (pos) {
      const pin = el("span", "sp-pin");
      pin.style.left = pos.left;
      pin.style.top = pos.top;
      pin.title = l.name;
      mapEl.append(pin);
    }
    const meta = [l.status.track, l.status.latest_date ? formatDate(l.status.latest_date) : null].filter(Boolean).join(" · ");
    listEl.append(
      el(
        "div",
        "sp-lake",
        el("div", "sp-lake-name", text("div", "sp-lake-title", l.name), text("div", "sp-lake-meta", meta || DASH)),
        el("div", "sp-lake-right", text("div", `sp-lake-status ${statusClass(l.status.status)}`, l.status.status), text("div", "sp-lake-area", areaText(latestArea(l)))),
      ),
    );
  }
  const mapCredit = text("figcaption", "sp-map-credit", w.mapCredit);
  const mapKey = el("figcaption", "sp-map-key", el("span", "sp-key-pin"), ` ${w.keyWatched} `, el("span", "sp-key-pin sp-key-request"), ` ${w.keyRequested}`);
  mapEl.append(mapKey, mapCredit);
  const requestEls: HTMLElement[] = [];
  const setRequests = (open: LakeRequest[]): void => {
    for (const e of requestEls) e.remove();
    requestEls.length = 0;
    for (const r of open.filter(isOpen)) {
      const pos = mapPin(r.lon, r.lat);
      if (pos) {
        const pin = el("span", "sp-pin sp-pin-request");
        pin.style.left = pos.left;
        pin.style.top = pos.top;
        pin.title = `${r.name}: ${requestLine(r)}`;
        mapEl.insertBefore(pin, mapCredit);
        requestEls.push(pin);
      }
      const card = el(
        "div",
        "sp-lake sp-request",
        el("div", "sp-lake-name", text("div", "sp-lake-title", r.name), text("div", "sp-lake-meta", `${r.lat.toFixed(2)} °N, ${r.lon.toFixed(2)} °E`)),
        el("div", "sp-lake-right", text("div", "sp-request-line", requestLine(r))),
      );
      listEl.append(card);
      requestEls.push(card);
    }
  };
  const watch = section("05 The watch", "sp-section");
  watch.append(
    el("div", "sp-head", el("div", undefined, eyebrow(w.label), text("h2", undefined, noData ? w.noDataTitle : f(w.title))), text("p", "sp-muted sp-head-note", noData ? w.noDataLede : f(w.lede))),
    el("div", "sp-watch", mapEl, listEl),
  );

  // 06 Add a lake: the form is mounted into addLakeEl by the caller.
  const ad = copy.add;
  const addSteps = el("ol", "sp-add-steps");
  for (const s of ad.steps) addSteps.append(text("li", undefined, f(s)));
  const addLakeEl = el("div", "sp-add-slot");
  const add = section("06 Add a lake", "sp-section");
  add.id = "add-lake";
  add.append(el("div", "sp-panel sp-add", el("div", "sp-add-intro", eyebrow(ad.label), text("h2", undefined, ad.title), text("p", undefined, f(ad.body)), addSteps), addLakeEl));

  // Closing band
  const cl = copy.closing;
  const overlap = file ? opticalOverlapPhrase(file.checks) : null;
  const closing = section("Open Lake Watch", "sp-closing");
  closing.append(
    el(
      "div",
      "sp-closing-in",
      el("div", "sp-closing-text", text("h2", undefined, cl.title), text("p", undefined, overlap ? fill(cl.body, { overlap }) : cl.noIouBody)),
      el("div", "sp-actions", button(cl.openLabel, "sp-btn-primary", opts.onOpenLakes), button(cl.evidenceLabel, "sp-btn-ghost", opts.onOpenEvidence)),
    ),
  );

  const ft = copy.footer;
  const footer = el("footer", "sp-footer", text("span", undefined, ft.team), text("span", undefined, ft.event), el("span", "sp-grow"), text("span", undefined, ft.data));

  const closedClient: RequestsClient = { health: async () => false, list: async () => [], submit: () => Promise.reject(new Error("closed")) };
  const addLake = mountAddLake(addLakeEl, opts.requests ?? closedClient, setRequests);

  page.append(cover, risk, gap, view, measure, watch, add, closing, footer);
  root.replaceChildren(page);

  return {
    listEl,
    mapEl,
    addLakeEl,
    setRequests,
    destroy() {
      addLake.destroy();
      for (const fn of cleanups) fn();
      cleanups.length = 0;
      root.replaceChildren();
    },
  };
}
