import evidenceJson from "./content/evidence.json";
import { cardFor } from "./content";
import { lakeTokens, type LakesFile } from "./lakes";
import { formatDate, maturityBanner } from "./timeline";
import type { Manifest, Site } from "./types";

interface EvidenceItem {
  text: string;
  /** Shown only when the build has this layer. */
  needs?: "step" | "lakes";
}

interface EvidenceSection {
  id: string;
  title: string;
  needs?: "step" | "lakes";
  paragraphs?: string[];
  afterTable?: string[];
  steps?: (string | EvidenceItem)[];
  list?: (string | EvidenceItem)[];
  table?: { head: string[]; rows: string[][] };
}

export interface EvidenceCopy {
  title: string;
  lede: string;
  can: string[];
  cannot: string[];
  sections: EvidenceSection[];
}

export const evidenceCopy = evidenceJson as EvidenceCopy;

export interface EvidenceViewOptions {
  manifest: Manifest;
  /** The sites whose control results fill the table. Without them the table is left out. */
  sites?: Site[] | null;
  /** Lake data. Without it the lake sections are left out. */
  lakes?: LakesFile | null;
}

export interface EvidenceViewHandle {
  destroy(): void;
}

/** The numbers in the copy, taken from the manifest so the page cannot drift from the data it describes. */
export function evidenceTokens(m: Manifest, lakes?: LakesFile | null): Record<string, string> {
  const step = m.change?.step;
  return {
    ...(lakes ? lakeTokens(lakes) : {}),
    analysis_m: String(m.analysis_m ?? 30),
    pixel_m: String(m.pixel_m ?? 67),
    step_pixel_m: step ? String(step.pixel_m) : "",
    drawn_m: step ? String(step.pixel_m * 3) : "",
    step_dates: step ? String(step.dates.length) : "",
    min_step_db: step ? String(step.min_step_db) : "",
    min_stability: step ? step.min_stability.toFixed(1) : "",
    flagged_pct: step ? (step.flagged_share * 100).toFixed(1) : "",
  };
}

export function fillTokens(text: string, tokens: Record<string, string>): string {
  return text.replace(/\{(\w+)\}/g, (whole, key: string) => tokens[key] ?? whole);
}

const asItem = (x: string | EvidenceItem): EvidenceItem => (typeof x === "string" ? { text: x } : x);

export function createEvidenceView(root: HTMLElement, opts: EvidenceViewOptions): EvidenceViewHandle {
  const m = opts.manifest;
  const hasStep = !!m.change?.step;
  const lakes = opts.lakes ?? null;
  const tokens = evidenceTokens(m, lakes);
  const fill = (t: string): string => fillTokens(t, tokens);
  const keep = (x: { needs?: "step" | "lakes" }): boolean => (x.needs !== "step" || hasStep) && (x.needs !== "lakes" || !!lakes);

  const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };

  const scroll = el("div", "evidence-scroll");
  scroll.dataset.role = "evidence-scroll";
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", "How we know");
  scroll.tabIndex = 0;

  const toc = el("nav", "evidence-toc");
  toc.setAttribute("aria-label", "On this page");
  const tocList = el("ul");
  toc.append(tocList);

  const main = el("div", "evidence-main");
  const head = el("header", "evidence-head");
  const title = el("h2", "evidence-title", evidenceCopy.title);
  head.append(title, el("p", "evidence-lede", fill(evidenceCopy.lede)));
  const banner = maturityBanner(m);
  const status = el("p", "evidence-status", `${banner.text}. ${banner.kind === "provisional" ? "NASA expects to reprocess these files." : ""}`.trim());
  head.append(status);

  const verdict = el("div", "evidence-verdict");
  const can = el("section", "verdict-can");
  can.append(el("h3", undefined, "What the evidence supports (Peshawar chapter)"));
  const canList = el("ul");
  canList.append(...evidenceCopy.can.map((t) => el("li", undefined, fill(t))));
  can.append(canList);
  const cannot = el("section", "verdict-cannot");
  cannot.append(el("h3", undefined, "What it cannot do (Peshawar chapter)"));
  const cannotList = el("ul");
  cannotList.append(...evidenceCopy.cannot.map((t) => el("li", undefined, fill(t))));
  cannot.append(cannotList);
  verdict.append(can, cannot);

  if (lakes) {
    head.append(el("p", "evidence-lede", "The first two sections cover Lake Watch. The rest covers the Peshawar chapter."));
  }
  main.append(head);
  // The Peshawar verdict follows the lake sections, so a visitor who came for the lakes reads their method first.
  let verdictPlaced = false;
  const placeVerdict = (): void => {
    if (!verdictPlaced) main.append(verdict);
    verdictPlaced = true;
  };

  /** The control table: one row per site, built from the cards so it cannot disagree with them. */
  function controlsTable(): HTMLTableElement | null {
    const sites = opts.sites ?? [];
    const rows = sites.filter((s) => cardFor(s.id).mapCheck);
    if (!rows.length) return null;
    const table = el("table", "evidence-table");
    table.dataset.role = "evidence-controls";
    const cap = el("caption", undefined, "Share of map pixels flagged near each site");
    const thead = el("thead");
    const hr = el("tr");
    for (const h of ["Site", "Kind", "Flagged near it"]) {
      const th = el("th", undefined, h);
      th.scope = "col";
      hr.append(th);
    }
    thead.append(hr);
    const tbody = el("tbody");
    for (const s of rows) {
      const c = cardFor(s.id).mapCheck!;
      const tr = el("tr");
      if (/\bcontrol\b/i.test(s.role)) tr.dataset.control = "true";
      const name = el("th", undefined, s.name);
      name.scope = "row";
      tr.append(name, el("td", undefined, s.role), el("td", undefined, `${c.flagged_pct}% of ${c.pixels} pixels within ${c.radius_m} m`));
      tbody.append(tr);
    }
    table.append(cap, thead, tbody);
    return table;
  }

  /** The Sentinel-2 cross-check rows, copied from lakes.json without adjusting any figure. */
  function lakeChecksTable(): HTMLTableElement | null {
    if (!lakes?.checks.length) return null;
    const table = el("table", "evidence-table");
    table.dataset.role = "lake-checks-table";
    table.append(el("caption", undefined, "One NISAR pass against one Sentinel-2 scene, inside each lake's 1 km zone"));
    const thead = el("thead");
    const hr = el("tr");
    for (const h of ["Lake", "NISAR date and track", "Sentinel-2 date and scene", "Radar km²", "Optical km²", "Overlap (IoU)"]) {
      const th = el("th", undefined, h);
      th.scope = "col";
      hr.append(th);
    }
    thead.append(hr);
    const tbody = el("tbody");
    for (const c of lakes.checks) {
      const tr = el("tr");
      const name = el("th", undefined, lakes.lakes.find((l) => l.id === c.lake)?.name ?? c.lake);
      name.scope = "row";
      tr.append(
        name,
        el("td", undefined, `${formatDate(c.nisar_date)}, track ${c.nisar_track}`),
        el("td", undefined, `${formatDate(c.s2_date)}, ${c.s2_id}`),
        el("td", undefined, c.radar_km2.toFixed(3)),
        el("td", undefined, c.optical_km2.toFixed(3)),
        el("td", undefined, c.iou === null ? "n/a" : c.iou.toFixed(2)),
      );
      tbody.append(tr);
    }
    table.append(thead, tbody);
    return table;
  }

  const sections = evidenceCopy.sections.filter(keep);
  for (const sec of sections) {
    if (sec.needs !== "lakes") placeVerdict();
    const s = el("section", "evidence-section");
    s.id = `evidence-${sec.id}`;
    s.dataset.section = sec.id;
    s.setAttribute("aria-labelledby", `${s.id}-h`);
    const h = el("h3", undefined, sec.title);
    h.id = `${s.id}-h`;
    s.append(h);
    for (const p of sec.paragraphs ?? []) s.append(el("p", undefined, fill(p)));
    if (sec.steps) {
      const ol = el("ol", "evidence-steps");
      ol.append(...sec.steps.map(asItem).filter(keep).map((i) => el("li", undefined, fill(i.text))));
      s.append(ol);
    }
    if (sec.list) {
      const ul = el("ul", "evidence-list");
      ul.append(...sec.list.map(asItem).filter(keep).map((i) => el("li", undefined, fill(i.text))));
      s.append(ul);
    }
    if (sec.table) {
      const table = el("table", "evidence-table");
      const thead = el("thead");
      const hr = el("tr");
      for (const col of sec.table.head) {
        const th = el("th", undefined, col);
        th.scope = "col";
        hr.append(th);
      }
      thead.append(hr);
      const tbody = el("tbody");
      for (const row of sec.table.rows) {
        const tr = el("tr");
        row.forEach((cell, i) => {
          const c = i === 0 ? el("th", undefined, fill(cell)) : el("td", undefined, fill(cell));
          if (i === 0) c.scope = "row";
          tr.append(c);
        });
        tbody.append(tr);
      }
      table.append(thead, tbody);
      const wrap = el("div", "table-wrap");
      wrap.append(table);
      s.append(wrap);
    }
    if (sec.id === "controls") {
      const t = controlsTable();
      if (t) {
        const wrap = el("div", "table-wrap");
        wrap.append(t);
        s.append(wrap);
      }
    }
    if (sec.id === "lake-checks") {
      const t = lakeChecksTable();
      if (t) {
        const wrap = el("div", "table-wrap");
        wrap.append(t);
        s.append(wrap);
      }
    }
    for (const p of sec.afterTable ?? []) s.append(el("p", undefined, fill(p)));
    main.append(s);

    const li = el("li");
    const a = el("a", undefined, sec.title);
    a.href = `#${s.id}`;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      s.scrollIntoView?.({ behavior: smooth ? "smooth" : "auto", block: "start" });
      h.focus({ preventScroll: true });
    });
    h.tabIndex = -1;
    li.append(a);
    tocList.append(li);
  }

  placeVerdict();
  scroll.append(toc, main);
  root.replaceChildren(scroll);
  return {
    destroy: () => {
      root.innerHTML = "";
    },
  };
}
