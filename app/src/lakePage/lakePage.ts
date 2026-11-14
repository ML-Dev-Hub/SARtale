import "./lakePage.css";
import { authorityFor } from "../contacts";
import { dataUrl, formatDate } from "../format";
import { isFrozen, levelMessage, picturedPassFrozen, suparcoLine, type Lake, type LakesFile } from "../lakes";
import type { LakeChartFactory } from "../lakeWatchView";
import { sentinel2Url } from "../links";
import { nextRefresh } from "../overview/model";
import { statusChip } from "../overview/marks";
import { provinceName } from "../provinces";
import { renderExtent } from "./extent";
import { renderCompare, type MaskDecoder } from "./compare";

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

function header(lake: Lake, file: LakesFile): HTMLElement {
  const sec = el("section", "lp-header");
  sec.dataset.role = "lp-header";
  sec.setAttribute("aria-labelledby", "lp-name");

  const top = el("div", "lp-top");
  const watched = file.counts?.watched ?? file.lakes.length;
  top.append(link(`All ${watched} watched lakes`, "#lakes", "lp-back"));
  const built = day(file.built);
  if (built) top.append(el("p", "lp-built", `Data built ${built} · next refresh Mon ${formatDate(nextRefresh(file.built))}`));
  sec.append(top);

  const place = [lake.district, provinceName(lake.province)].filter((s): s is string => !!s).join(", ");
  if (place) sec.append(el("p", "lp-place", place));

  const title = el("div", "lp-title");
  const h1 = el("h1", "lp-name", lake.name);
  h1.id = "lp-name";
  title.append(h1, statusChip(lake.status.status));
  sec.append(title);

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
  if (authority) {
    const a = link(authority.label, authority.url, "lp-btn");
    a.dataset.action = "authority";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    actions.append(a);
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

/** The lake page (spec decision 5): header and message, then the gauge or frozen card, extent, picture, history, sources. */
export function createLakePage(root: HTMLElement, opts: LakePageOptions): { destroy(): void } {
  const page = el("div", "lp");
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

  page.append(header(lake, opts.file));
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
    for (const sec of [block("lp-extent", "Largest recorded extent", (b) => (renderExtent(b, lake, opts.file.constants.min_observable), true)), block("lp-picture", "Radar picture", fillPicture(lake))]) if (sec) page.append(sec);
  }
  return { destroy: () => void root.replaceChildren() };
}
