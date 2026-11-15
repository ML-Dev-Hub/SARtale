import "./lakePage.css";
import { authorityFor } from "../contacts";
import { dataUrl, formatDate } from "../format";
import { freezeFacts, frozenAreaLine, isFrozen, levelMessage, picturedPassFrozen, suparcoLine, type Lake, type LakesFile } from "../lakes";
import type { LakeChartFactory } from "../lakeWatchView";
import { sentinel2Url } from "../links";
import { nextRefresh } from "../overview/model";
import { PHONE_QUERY } from "../overview/overviewView";
import { familyChip } from "../overview/marks";
import { statusDisplay } from "../statusDisplay";
import { provinceName } from "../provinces";
import { renderExtent } from "./extent";
import { renderCompare, type MaskDecoder } from "./compare";
import { historyHeading, renderHistory } from "./history";
import { gaugeHeading, gaugeInput, renderGauge } from "./gauge";
import { changedLimits, plainLimit } from "../plainLimits";
import { limitsList, sourceRows } from "./sources";

export interface LakePageOptions {
  file: LakesFile;
  lakeId: string;
  /** A pass_id to show in the radar picture (Task 20). */
  pass?: string;
  /** Two pass_ids of one track to compare (Task 22). The compare view replaces the blocks. */
  compare?: [string, string];
  onRoute(hash: string): void;
  createChart?: LakeChartFactory;
  decodeMask?: MaskDecoder;
  onBrief?(l: Lake): void;
  isPhone?: boolean;
}

export const OFFICIAL_WARNINGS = "Official warnings come from PMD, NDMA, GBDMA and PDMA.";

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function link(text: string, href: string, cls?: string): HTMLAnchorElement {
  const a = el("a", cls, text);
  a.href = href;
  return a;
}

/** "9 Nov 2026" from an ISO date or a build timestamp; null when it is not a date. */
function day(iso: string | null | undefined): string | null {
  const d = iso?.slice(0, 10);
  return d && /^\d{4}-\d{2}-\d{2}$/.test(d) ? formatDate(d) : null;
}

const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;

/** The tracks that read this lake: those with a valid reading, else the directions the pipeline lists. */
function trackCount(l: Lake): number {
  const read = new Set(l.series.filter((p) => p.area_km2 !== null && p.excluded === null).map((p) => p.track));
  return read.size || (l.directions?.length ?? 0);
}

/** "13 Nov": a date without its year, for the phone's one-line header. */
const shortDay = (iso: string): string => formatDate(iso).replace(/ \d{4}$/, "");

function header(lake: Lake, file: LakesFile, phone: boolean): HTMLElement {
  const sec = el("section", "lp-header");
  sec.dataset.role = "lp-header";
  sec.setAttribute("aria-labelledby", "lp-name");

  const top = el("div", "lp-top");
  const watched = file.counts?.watched ?? file.lakes.length;
  top.append(link(phone ? "All lakes" : `All ${watched} watched lakes`, "#lakes", "lp-back"));
  const built = day(file.built);
  if (built && Number.isFinite(Date.parse(file.built))) {
    const next = nextRefresh(file.built);
    const text = phone ? `Data ${shortDay(file.built.slice(0, 10))} · next Mon ${shortDay(next)}` : `Data built ${built} · next refresh Mon ${formatDate(next)}`;
    top.append(el("p", "lp-built", text));
  }
  sec.append(top);

  const display = statusDisplay(lake, file.constants);
  const place = [lake.district, provinceName(lake.province)].filter((s): s is string => !!s).join(", ");
  const placeEl = place ? el("p", "lp-place", place) : null;
  const h1 = el("h1", "lp-name", lake.name);
  h1.id = "lp-name";
  if (phone) {
    // On a phone the name comes first, the place under it, then the chip on its own line.
    sec.append(h1);
    if (placeEl) sec.append(placeEl);
    sec.append(familyChip(display));
    if (display.tag) sec.append(el("p", "lp-tag", display.tag));
  } else {
    if (placeEl) sec.append(placeEl);
    const title = el("div", "lp-title");
    title.append(h1, familyChip(display));
    sec.append(title);
    if (display.tag) sec.append(el("p", "lp-tag", display.tag));
  }

  sec.append(el("p", "lp-suparco", suparcoLine(lake)));

  const s = lake.status;
  const meta: string[] = [];
  const latest = day(s.latest_date);
  if (latest) meta.push(`Latest assessment ${latest}`);
  if (s.track) meta.push(`track ${s.track}`);
  if (s.looks > 0) meta.push(`${s.looks} valid looks`);
  const tracks = trackCount(lake);
  if (tracks > 0) meta.push(plural(tracks, "track"));
  if (meta.length) sec.append(el("p", "lp-meta", meta.join(" · ")));
  return sec;
}

/** The first message under the header: the pipeline's four parts, then what to do and the actions. */
function message(lake: Lake): HTMLElement | null {
  const m = levelMessage(lake);
  if (!m) return null;
  const sec = el("section", "lp-message");
  sec.dataset.role = "lp-message";
  sec.dataset.level = m.level;
  sec.dataset.status = lake.status.status.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  sec.setAttribute("aria-label", "First message");
  sec.append(el("h2", "lp-message-title", m.title));

  const parts = el("div", "lp-parts");
  const part = (label: string, ...paras: (string | undefined)[]): HTMLElement => {
    const d = el("div", "lp-part");
    d.append(el("h3", undefined, label));
    for (const t of paras) if (t) d.append(el("p", undefined, t));
    return d;
  };
  parts.append(part("What changed", m.what, m.since), part("How sure", m.how_sure), part("What it is not", m.not));
  sec.append(parts);

  const todo = el("div", "lp-todo");
  const text = part("What to do", m.do);
  text.classList.add("lp-todo-text");
  const actions = el("div", "lp-actions");
  const s2 = link("Open recent Sentinel-2 imagery", sentinel2Url(lake), "lp-btn lp-btn-primary");
  s2.dataset.action = "sentinel2";
  s2.target = "_blank";
  s2.rel = "noopener noreferrer";
  actions.append(s2);
  const authority = authorityFor(lake.province);
  if (authority?.url) {
    const a = link(authority.label, authority.url, "lp-btn");
    a.dataset.action = "authority";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    actions.append(a);
    if (authority.note) actions.append(el("p", "lp-authority-note", authority.note));
  }
  todo.append(text, actions);
  sec.append(todo);
  // The message text normally ends with this sentence. It shows once: added here only when the text lacks it.
  if (!m.do.includes(OFFICIAL_WARNINGS)) sec.append(el("p", "lp-official", OFFICIAL_WARNINGS));
  return sec;
}

/**
 * A block with a heading and its content, or null when there is nothing to show yet: a block no task has filled is not
 * drawn, so the page never shows a bare heading.
 */
function block(role: string, heading: string, fill: (body: HTMLElement) => boolean): HTMLElement | null {
  const sec = el("section", "lp-block");
  sec.dataset.role = role;
  sec.setAttribute("aria-labelledby", `${role}-h`);
  const h = el("h2", undefined, heading);
  h.id = `${role}-h`;
  const body = el("div", "lp-slot");
  body.dataset.slot = role;
  if (!fill(body)) return null;
  sec.append(h, body);
  return sec;
}

/** The latest HH picture with the water layer over it, and what it shows. The water layer is hidden while the lake is frozen. */
function fillPicture(lake: Lake): (body: HTMLElement) => boolean {
  return (body) => {
    const hh = lake.images?.latest_hh ?? null;
    const hidden = isFrozen(lake) || picturedPassFrozen(lake);
    const water = hidden ? null : lake.images?.water ?? null;
    if (!hh && !water) {
      body.append(el("p", "lp-none", "No radar picture yet"));
      return true;
    }
    const stack = el("div", "lp-stack");
    const img = (path: string, alt: string, cls: string): HTMLImageElement => {
      const i = el("img", cls);
      i.src = dataUrl(path);
      i.alt = alt;
      return i;
    };
    if (hh) stack.append(img(hh, `Latest HH radar picture of ${lake.name}, north up`, "lp-img lp-img-hh"));
    if (water) stack.append(img(water, `Water pixels for ${lake.name}, north up`, "lp-img lp-img-water"));
    body.append(stack);
    const when = day(lake.images?.date);
    const parts = [when ? `pass of ${when}` : null, lake.images?.track ? `track ${lake.images.track}` : null].filter(Boolean);
    const what = hh ? "Latest HH radar picture" : "Water pixels";
    body.append(el("p", "lp-caption", `${what}${parts.length ? `: ${parts.join(", ")}` : ""}. North up${water ? ", water layer over it" : ""}.`));
    if (hidden && lake.images?.water) body.append(el("p", "lp-caption", "Water layer hidden: not an open-water measurement while frozen."));
    return true;
  };
}

/** The pipeline's last open-water pass, or null when it gave none: no pass is guessed from the series. */
function lastOpenLine(lake: Lake): string | null {
  const o = lake.last_open;
  const when = day(o?.date);
  if (!o || !when) return null;
  return `${when} · ${o.area_km2.toFixed(3)} km² · track ${o.track}`;
}

/** The frozen card: it replaces the gauge while the lake is frozen. No frozen pass is shown as an open-water number. */
function fillFreeze(lake: Lake): (body: HTMLElement) => boolean {
  return (body) => {
    const d = statusDisplay(lake);
    body.append(el("p", "lp-freeze-head", d.tag ? `${d.chip}: ${d.tag}` : d.chip));
    const area = frozenAreaLine(lake);
    if (area) body.append(el("p", "lp-freeze-area", area));
    const facts = freezeFacts(lake);
    if (facts.length) {
      const ul = el("ul", "lp-freeze-facts");
      for (const t of facts) ul.append(el("li", undefined, t));
      body.append(ul);
    }
    const open = lastOpenLine(lake);
    if (open) {
      const d = el("div", "lp-freeze-open");
      d.append(el("h3", undefined, "Last open-water pass"), el("p", undefined, open));
      body.append(d);
    }
    return true;
  };
}

/** The change gauge, or null when the lake has no change reading to draw. */
function gaugeBlock(lake: Lake, factor: number, phone: boolean): HTMLElement | null {
  if (!gaugeInput(lake, factor)) return null;
  return block("lp-gauge", gaugeHeading(lake), (body) => {
    renderGauge(body, lake, factor, phone);
    return body.childElementCount > 0;
  });
}

/** Sources and limits: where each fact comes from, what the method and this lake cannot do, and the printed brief. */
function fillSources(lake: Lake, file: LakesFile, onBrief?: (l: Lake) => void): (body: HTMLElement) => boolean {
  return (body) => {
    const dl = el("dl", "lp-sources-list");
    for (const r of sourceRows(lake, file)) {
      const row = el("div", "lp-source");
      row.append(el("dt", undefined, r.k), el("dd", undefined, r.v));
      dl.append(row);
    }
    body.append(dl);
    const limits = limitsList(lake, file);
    if (limits.length) {
      const d = el("div", "lp-limits");
      d.append(el("h3", undefined, "Limits"));
      const ul = el("ul");
      for (const t of limits) ul.append(el("li", undefined, plainLimit(t)));
      d.append(ul);
      // Nothing is hidden: the pipeline's own wording of every rewritten line stays here.
      const original = changedLimits(limits);
      if (original.length) {
        const det = el("details", "lp-limits-raw");
        det.append(el("summary", undefined, "Technical wording"));
        const raw = el("ul", "lp-limits-original");
        for (const t of original) raw.append(el("li", undefined, t));
        det.append(raw);
        d.append(det);
      }
      body.append(d);
    }
    if (onBrief) {
      const b = el("button", "lp-btn", "Print lake brief");
      b.type = "button";
      b.dataset.action = "brief";
      b.addEventListener("click", () => onBrief(lake));
      body.append(b);
    }
    return true;
  };
}

/** The lake page (spec decision 5): header and message, then the gauge or frozen card, extent, picture, history, sources. */
export function createLakePage(root: HTMLElement, opts: LakePageOptions): { destroy(): void } {
  const phone = opts.isPhone ?? window.matchMedia?.(PHONE_QUERY).matches ?? false;
  const page = el("div", phone ? "lp lp-phone" : "lp");
  root.replaceChildren(page);
  const lake = opts.file.lakes.find((l) => l.id === opts.lakeId);
  const onClick = (e: Event): void => {
    const a = (e.target as Element).closest?.<HTMLAnchorElement>('a[href^="#lakes"]');
    if (!a || !page.contains(a)) return;
    e.preventDefault();
    opts.onRoute(a.getAttribute("href")!);
  };
  page.addEventListener("click", onClick);

  if (!lake) {
    page.append(el("p", "lp-missing", "This lake is not in the current data."), link("All watched lakes", "#lakes", "lp-back"));
    return { destroy: () => void root.replaceChildren() };
  }

  page.append(header(lake, opts.file, phone));
  if (opts.compare) {
    const sec = el("section", "lp-block");
    sec.dataset.role = "lp-compare";
    sec.setAttribute("aria-label", "Compare passes");
    renderCompare(sec, { file: opts.file, lake, pass: opts.compare, decodeMask: opts.decodeMask, onRoute: opts.onRoute });
    page.append(sec);
  } else {
    const msg = isFrozen(lake) ? null : message(lake);
    if (msg) page.append(msg);
    // Blocks whose content a later task fills (the gauge or frozen card, extent, history, sources) join here, in order.
    const factor = opts.file.constants.change_factor;
    const top = isFrozen(lake) ? block("lp-freeze", "Ice", fillFreeze(lake)) : gaugeBlock(lake, factor, phone);
    const hist = { minObservable: opts.file.constants.min_observable, factor, createChart: opts.createChart, phone };
    const blocks = [
      top,
      block("lp-extent", "Largest recorded extent", (b) => (renderExtent(b, lake, opts.file.constants.min_observable), true)),
      block("lp-picture", "Radar picture", fillPicture(lake)),
      block("lp-history", historyHeading(lake), (b) => renderHistory(b, lake, hist)),
      block("lp-sources", "Sources and limits", fillSources(lake, opts.file, opts.onBrief)),
    ];
    for (const sec of blocks) if (sec) page.append(sec);
  }
  return { destroy: () => void root.replaceChildren() };
}
