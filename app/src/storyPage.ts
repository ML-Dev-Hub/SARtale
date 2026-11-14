import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/inter-tight/wght.css";
import "./storyPage.css";
import copyJson from "./content/storyPage.json";
import { dataUrl, formatDate } from "./format";
import { mountAddLake, requestLine, shownRequests, type LakeRequest } from "./lakeRequests";
import { MARKER_LABELS, markerSvg } from "./statusMarkers";
import { familyCounts, frozenBreakdown, statusDisplay, type Family } from "./statusDisplay";
import { alertLakes, cloudLooks, FROZEN_AREA, hasLakeNow, iouRange, isFrozen, lakesNow, levelMessage, opticalOverlapPhrase, picturedPassFrozen, type Lake, type LakesFile } from "./lakes";

const copy = copyJson;
const DASH = "—";

export interface StoryNumbers {
  /** Sites that hold a lake now. */
  lakes: string;
  /** Every site on the list, including those with no lake now. */
  sites: string;
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
  /** Lake requests from requests.json. Invalid and rejected ones are not shown. */
  requests?: LakeRequest[];
}

export interface StoryPage {
  destroy(): void;
  listEl: HTMLElement;
  mapEl: HTMLElement;
  addLakeEl: HTMLElement;
  /** Show these lake requests in the list and on the map, replacing the earlier ones. */
  setRequests(requests: LakeRequest[]): void;
}

/** The pictured pass's area: the series point on the status track's latest date. None for a site with no lake now. */
function latestArea(lake: Lake): number | null {
  if (!hasLakeNow(lake)) return null;
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

/** What the measure section shows of a lake: a pass, its picture, water layer, area and noise, and any line on ice. */
export interface MeasureView {
  date: string | null;
  track: string | null;
  area: number | null;
  noise: number | null;
  hh: string | null;
  water: string | null;
  /** A line under the picture when the newest pass is not an open-water reading. */
  note: string | null;
  /** True when the area shown was read while the lake was frozen (no open-water pass to show instead). */
  greyed: boolean;
  /**
   * Set when the picture is the newest pass, taken while frozen, drawn without its water layer: its date and track
   * (the open-water pass has no picture of its own, or there is no open-water pass).
   */
  frozenPicture: { date: string | null; track: string | null } | null;
}

/**
 * The pass the measure section shows. While the lake is frozen (or its pictured pass was taken while it was), never
 * that pass as water: its last open-water pass on the status track instead (lakes.json `last_open`, with its own
 * picture, water layer, area and noise) and a line that says so; without one, the newest picture with no water layer
 * and the area greyed as not an open-water measurement.
 */
export function measureView(a: Lake | null): MeasureView {
  if (!a) return { date: null, track: null, area: null, noise: null, hh: null, water: null, note: null, greyed: false, frozenPicture: null };
  const name = a.name.split(" (")[0];
  const frozen = isFrozen(a) || picturedPassFrozen(a);
  if (!frozen) {
    return { date: a.images?.date ?? a.status.latest_date, track: a.status.track, area: latestArea(a), noise: a.status.noise_km2,
      hh: a.images?.latest_hh ?? null, water: a.images?.water ?? null, note: null, greyed: false, frozenPicture: null };
  }
  const newest = { date: a.images?.date ?? a.status.latest_date, track: a.images?.track ?? a.status.track };
  const lo = a.last_open;
  if (lo) {
    const since = a.freeze?.freeze_up ?? a.freeze?.since ?? null;
    const note = isFrozen(a)
      ? `${name} is frozen now${since ? ` (since ${formatDate(since)})` : ""}. This is its last open-water pass.`
      : `${name}'s newest pass was taken while it was frozen. This is its last open-water pass.`;
    // Its own picture and water layer when lakes-freeze drew them; else the newest picture with no water layer.
    const own = !!lo.images?.latest_hh;
    return { date: lo.date, track: lo.track, area: lo.area_km2, noise: lo.noise_km2,
      hh: own ? lo.images!.latest_hh : a.images?.latest_hh ?? null, water: own ? lo.images!.water ?? null : null, note,
      greyed: false, frozenPicture: own ? null : newest };
  }
  const p = a.series.find((x) => x.date === a.images?.date && x.track === a.images?.track)
    ?? a.series.find((x) => x.date === a.status.latest_date && x.track === a.status.track);
  return { date: newest.date, track: newest.track, area: p?.area_km2 ?? null, noise: null, hh: a.images?.latest_hh ?? null,
    water: null, note: `Water layer hidden: ${FROZEN_AREA}.`, greyed: true, frozenPicture: newest };
}

/** Every number on the page, read from lakes.json. "—" for anything missing. */
export function storyNumbers(file: LakesFile | null): StoryNumbers {
  if (!file) {
    return { lakes: DASH, sites: DASH, cloudLooks: DASH, passes: DASH, attabadArea: DASH, attabadNoise: DASH, attabadLooks: DASH, attabadTrack: DASH, iou: DASH, latest: DASH };
  }
  const a = attabad(file);
  const dates = file.lakes.map((l) => l.status.latest_date).filter((d): d is string => !!d);
  const latest = dates.length ? dates.reduce((x, y) => (x > y ? x : y)) : null;
  const view = measureView(a);
  const noise = view.noise;
  return {
    lakes: String(lakesNow(file).length),
    sites: String(file.lakes.length),
    cloudLooks: String(cloudLooks(file)),
    passes: String(file.lakes.reduce((n, l) => n + l.series.length, 0)),
    attabadArea: a ? areaText(view.area) : DASH,
    attabadNoise: noise === null || noise === undefined ? DASH : `±${noise.toFixed(2)}`,
    attabadLooks: a ? String(a.status.looks) : DASH,
    attabadTrack: view.track ?? DASH,
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
  const date = measureView(a).date;
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

/** The level colours (an Alert also a solid pill with a mark); the statuses without a level are other. Older builds'
 * Stable, Growing and Shrinking keep their colours. */
export function statusClass(status: string): string {
  if (status === "Alert: growing") return "sp-st-alert";
  if (status === "Watch") return "sp-st-watch";
  if (status === "Decrease noted") return "sp-st-decrease";
  if (status === "No change" || status === "Stable") return "sp-st-stable";
  if (status === "Growing" || status === "Shrinking") return "sp-st-change";
  return "sp-st-other";
}

/** The banner at the top of the story page when any lake is at Alert: growing; null otherwise. */
export function alertBanner(file: LakesFile | null, onOpen: () => void): HTMLElement | null {
  const alerts = alertLakes(file);
  if (!alerts.length) return null;
  const box = el("section", "sp-alert-banner");
  box.setAttribute("role", "alert");
  box.setAttribute("aria-label", "Alert");
  box.dataset.role = "sp-alert-banner";
  for (const a of alerts) {
    const m = levelMessage(a);
    box.append(el("p", undefined, text("strong", undefined, "Alert: growing"), ` at ${a.name}. ${m ? `${m.title} ${m.what}` : a.status.reason}`));
  }
  const go = text("button", "sp-btn sp-btn-primary", "Open Lake Watch");
  (go as HTMLButtonElement).type = "button";
  go.addEventListener("click", onOpen);
  box.append(el("p", undefined, "Not an outburst forecast. Check recent optical imagery or the site. Contact GBDMA or PDMA. Official warnings come from PMD, NDMA, GBDMA and PDMA. ", go));
  return box;
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
        el(
          "div",
          "sp-actions",
          button(c.openLabel, "sp-btn-primary", opts.onOpenLakes),
          button(c.followLabel, "sp-btn-ghost", opts.onFollowStory),
          Object.assign(link("#videos", c.videosLabel), { className: "sp-btn sp-btn-ghost" }),
        ),
        stats,
      ),
    ),
    text("p", "sp-credit sp-cover-credit", c.credit),
  );

  // 01 The risk
  const r = copy.risk;
  const facts = el("div", "sp-facts");
  for (const x of r.facts) facts.append(el("div", "sp-fact", text("div", "sp-fact-value", x.value), text("div", "sp-fact-label", x.label), text("div", "sp-src", x.source)));
  const risk = section("01 The flood", "sp-section sp-risk");
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
  const mv = measureView(a);
  const nums = el("div", "sp-numbers");
  m.numbers.forEach((n, i) => {
    // The area tile of a frozen lake with no open-water pass to show: greyed, and labelled with what it is not.
    const grey = i === 0 && mv.greyed;
    const value = text("div", `sp-num-value${"accent" in n ? " sp-accent" : ""}${grey ? " sp-num-frozen" : ""}`, f(n.value));
    nums.append(el("div", undefined, value, text("div", "sp-stat-label", grey ? FROZEN_AREA : f(n.label))));
  });
  const measure = section("04 The measurement", "sp-section sp-measure");
  if (mv.hh) {
    const fig = el("figure", "sp-overlay");
    const fp = mv.frozenPicture;
    const when = (d: string | null) => (d ? formatDate(d) : DASH);
    const alt = fp ? `${a!.name.split(" (")[0]} in NISAR radar on ${when(fp.date)}, while the lake was frozen; no water layer` : f(m.imageAlt);
    const stack = el("div", "sp-overlay-stack", img(dataUrl(mv.hh), alt));
    if (mv.water) {
      const w = img(dataUrl(mv.water), m.waterAlt);
      w.className = "sp-water";
      stack.append(w);
    }
    const caption = fp ? `${when(fp.date)}, track ${fp.track ?? DASH}. Water layer hidden: ${FROZEN_AREA}.` : f(m.caption);
    fig.append(stack, text("figcaption", undefined, caption));
    measure.append(fig);
  }
  if (mv.note && !mv.greyed) {
    // the frozen picture's own caption already says the water layer is hidden; this says what the numbers are
    const note = text("p", "sp-frozen-note", mv.note);
    note.dataset.role = "sp-frozen-note";
    measure.append(note);
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
    if (!pos) continue;
    const fam = statusDisplay(l, file?.constants).family;
    const pin = el("span", `sp-pin sp-pin-svg${fam === "nolake" ? " sp-pin-nolake" : ""}`);
    pin.dataset.family = fam;
    pin.innerHTML = markerSvg(fam, { size: 20 });
    pin.style.left = pos.left;
    pin.style.top = pos.top;
    pin.title = hasLakeNow(l) ? l.name : `${l.name}: ${l.status.status}`;
    mapEl.append(pin);
  }
  // The lake list: one row per status family (attention first), each opening its lakes in place.
  const ATTENTION: Family[] = ["alert", "watch", "decrease", "forming"];
  const GLYPH: Record<string, string> = { triangle: "▲", diamond: "◆", down: "▼", circle: "●", hexagon: "⬢", square: "■", crossed: "✕", ring: "○" };
  const lakeCard = (l: Lake): HTMLElement => {
    const d = statusDisplay(l, file?.constants);
    const meta = [l.status.track, l.status.latest_date ? formatDate(l.status.latest_date) : null].filter(Boolean).join(" · ");
    const glyph = text("span", "sp-lake-mark", GLYPH[d.mark] ?? "●");
    glyph.setAttribute("aria-hidden", "true");
    const chip = el("div", `sp-lake-status ${statusClass(l.status.status)}${d.dashed ? " sp-dashed" : ""}`, glyph, ` ${d.chip}`);
    const right = el("div", "sp-lake-right", chip);
    if (d.tag) right.append(text("div", "sp-lake-tag", d.tag));
    // An area only where it is an open-water reading: not for frozen, unmeasured or no-lake sites.
    const area = ["alert", "watch", "decrease", "nochange", "forming"].includes(d.family) ? latestArea(l) : null;
    if (area !== null) right.append(text("div", "sp-lake-area", areaText(area)));
    const name = el("div", "sp-lake-name", text("div", "sp-lake-title", l.name));
    if (meta) name.append(text("div", "sp-lake-meta", meta));
    return el("div", "sp-lake", name, right);
  };
  const byFamily = new Map<Family, Lake[]>();
  for (const l of lakes) {
    const f = statusDisplay(l, file?.constants).family;
    byFamily.set(f, [...(byFamily.get(f) ?? []), l]);
  }
  const counts = familyCounts(file?.lakes ?? []);
  const frozenSplit = frozenBreakdown(file?.lakes ?? []);
  const families = [...byFamily.entries()].sort((x, y) => statusDisplay(x[1][0], file?.constants).rank - statusDisplay(y[1][0], file?.constants).rank);
  if (file && lakes.length && !families.some(([f]) => ATTENTION.includes(f))) {
    listEl.append(text("p", "sp-levels-calm sp-muted", "No lake is at Alert, Watch or Decrease noted now."));
  }
  families.forEach(([fam, group]) => {
    const first = statusDisplay(group[0], file?.constants);
    const open = ATTENTION.includes(fam);
    const id = `sp-family-${fam}`;
    const n = counts[fam] ?? group.length;
    const summary = fam === "frozen" ? `: ${frozenSplit.seen} seen in Sentinel-2, ${frozenSplit.temperature} by air temperature` : "";
    const glyph = text("span", "sp-lake-mark", GLYPH[first.mark] ?? "●");
    glyph.setAttribute("aria-hidden", "true");
    const toggle = el("button", "sp-family-toggle", glyph, text("span", "sp-family-name", `${first.chip} ${n}${summary}`));
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-controls", id);
    const body = el("div", "sp-family-list");
    body.id = id;
    body.hidden = !open;
    for (const l of group) body.append(lakeCard(l));
    toggle.addEventListener("click", () => {
      const now = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(now));
      body.hidden = !now;
    });
    const row = el("div", "sp-family", toggle, body);
    row.dataset.family = fam;
    row.dataset.count = String(group.length);
    listEl.append(row);
  });
  const requestsEl = el("div", "sp-requests");
  listEl.append(requestsEl);
  if (file && lakes.length) {
    const all = text("button", "sp-btn sp-btn-ghost sp-levels-all", `Open Lake Watch for all ${lakes.length} lakes`);
    all.type = "button";
    all.addEventListener("click", opts.onOpenLakes);
    cleanups.push(() => all.removeEventListener("click", opts.onOpenLakes));
    listEl.append(all);
  }
  const mapCredit = text("figcaption", "sp-map-credit", w.mapCredit);
  const mapKey = el("figcaption", "sp-map-key");
  for (const [fam] of families) {
    const entry = el("span", `sp-key-item${fam === "nolake" ? " sp-key-nolake" : ""}`);
    entry.dataset.family = fam;
    const icon = el("span", "sp-key-icon");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = markerSvg(fam, { size: 14 });
    entry.append(icon, ` ${MARKER_LABELS[fam]}`);
    mapKey.append(entry);
  }
  mapKey.append(el("span", "sp-key-pin sp-key-request"), ` ${w.keyRequested}`);
  mapEl.append(mapKey, mapCredit);
  const requestEls: HTMLElement[] = [];
  // Shared with the add-a-lake form, so a refreshed list is what the form checks a new request against.
  const addDeps = { watched: file?.lakes ?? [], requests: [] as LakeRequest[] };
  const setRequests = (list: LakeRequest[]): void => {
    addDeps.requests = list;
    for (const e of requestEls) e.remove();
    requestEls.length = 0;
    for (const r of shownRequests(list, file?.lakes ?? [])) {
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
      requestsEl.append(card);
      requestEls.push(card);
    }
  };
  const watch = section("05 The levels", "sp-section");
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

  // 07 The videos: native players with captions on by default.
  const vd = copy.videos;
  const videoGrid = el("div", "sp-videos");
  for (const item of vd.items) {
    const video = el("video", "sp-video");
    video.controls = true;
    video.preload = "metadata";
    video.poster = item.poster;
    video.setAttribute("playsinline", "");
    video.setAttribute("aria-label", `${item.title} (${item.length})`);
    const source = el("source");
    source.src = item.src;
    source.type = "video/mp4";
    const track = el("track");
    track.kind = "captions";
    track.srclang = "en";
    track.label = "English";
    track.src = item.captions;
    track.default = true;
    video.append(source, track, link(item.src, `Download ${item.title} (MP4)`));
    videoGrid.append(
      el("figure", "sp-panel sp-video-card", video, el("figcaption", undefined, el("h3", undefined, item.title, text("span", "sp-muted sp-video-len", ` · ${item.length}`)), text("p", "sp-muted", item.text))),
    );
  }
  const videos = section("07 The videos", "sp-section");
  videos.id = "videos";
  videos.append(el("div", "sp-head", el("div", undefined, eyebrow(vd.label), text("h2", undefined, vd.title)), text("p", "sp-muted sp-head-note", vd.lede)), videoGrid);

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

  setRequests(opts.requests ?? []);
  const addLake = mountAddLake(addLakeEl, addDeps);

  const banner = alertBanner(file, opts.onOpenLakes);
  if (banner) page.append(banner);
  page.append(cover, risk, gap, view, measure, watch, add, videos, closing, footer);
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
