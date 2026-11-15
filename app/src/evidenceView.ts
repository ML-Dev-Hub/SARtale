import evidenceJson from "./content/evidence.json";
import { lakeTokens, type LakesFile } from "./lakes";
import { formatDate } from "./format";

interface EvidenceSection {
  id: string;
  title: string;
  paragraphs?: string[];
  afterTable?: string[];
  list?: string[];
  table?: { head: string[]; rows: string[][] };
}

export interface EvidenceCopy {
  title: string;
  lede: string;
  summary: { title: string; steps: string[] };
  can: string[];
  cannot: string[];
  /** The short, plain sections shown on the page. */
  shortSections: EvidenceSection[];
  /** The full method, checks and data, inside a closed block. */
  technical: { title: string; intro: string; sections: EvidenceSection[] };
}

export const evidenceCopy = evidenceJson as EvidenceCopy;

export interface EvidenceViewOptions {
  /** Lake data: fills the numbers in the copy and the Sentinel-2 table. Without it the numbers stay as named gaps. */
  lakes?: LakesFile | null;
}

export interface EvidenceViewHandle {
  destroy(): void;
}

export function fillTokens(text: string, tokens: Record<string, string>): string {
  return text.replace(/\{(\w+)\}/g, (whole, key: string) => tokens[key] ?? whole);
}

/** True when `text` still holds a {token} (its figure comes from lake data that is not there). */
export function hasToken(text: string): boolean {
  return /\{\w+\}/.test(text);
}

export const NO_DATA_NOTE = "No lake data in this build. This page omits figures from that data (passes, constants, checks).";

export function createEvidenceView(root: HTMLElement, opts: EvidenceViewOptions): EvidenceViewHandle {
  const lakes = opts.lakes ?? null;
  const tokens = lakes ? lakeTokens(lakes) : {};
  const fill = (t: string): string => fillTokens(t, tokens);
  /** Filled text, or null when a figure it needs is missing: such a sentence is left out, never shown with {gaps}. */
  const filled = (t: string): string | null => {
    const out = fill(t);
    return hasToken(out) ? null : out;
  };
  const items = (list: string[]): HTMLLIElement[] =>
    list.map(filled).filter((t): t is string => t !== null).map((t) => el("li", undefined, t));

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
  const lede = filled(evidenceCopy.lede);
  head.append(title);
  if (lede !== null) head.append(el("p", "evidence-lede", lede));
  if (!lakes) {
    const note = el("p", "evidence-nodata", NO_DATA_NOTE);
    note.dataset.role = "evidence-nodata";
    head.append(note);
  }
  head.append(el("p", "evidence-status", "Provisional NISAR data up to 21 Oct 2026, which NASA expects to reprocess. Later passes are NASA's standard product."));

  const verdict = el("div", "evidence-verdict");
  const can = el("section", "verdict-can");
  can.append(el("h3", undefined, "What the evidence supports"));
  const canList = el("ul");
  canList.append(...items(evidenceCopy.can));
  can.append(canList);
  const cannot = el("section", "verdict-cannot");
  cannot.append(el("h3", undefined, "What it cannot do"));
  const cannotList = el("ul");
  cannotList.append(...items(evidenceCopy.cannot));
  cannot.append(cannotList);
  verdict.append(can, cannot);

  const summary = el("section", "evidence-summary");
  summary.id = "evidence-steps";
  summary.setAttribute("aria-labelledby", "evidence-steps-h");
  const summaryHead = el("h3", undefined, evidenceCopy.summary.title);
  summaryHead.id = "evidence-steps-h";
  const stepList = el("ol", "evidence-steps");
  stepList.append(...items(evidenceCopy.summary.steps));
  summary.append(summaryHead, stepList);

  main.append(head, summary, verdict);

  /** The Sentinel-2 cross-check rows, copied from lakes.json without adjusting any figure. */
  function lakeChecksTable(): HTMLTableElement | null {
    if (!lakes?.checks.length) return null;
    const table = el("table", "evidence-table");
    table.dataset.role = "lake-checks-table";
    table.append(el("caption", undefined, "One NISAR pass against one Sentinel-2 scene in the open-water season, inside each lake's zone (its outline or search circle)"));
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

  /** Builds one section into the parent and returns it. */
  function addSection(parent: HTMLElement, sec: EvidenceSection): HTMLElement {
    const s = el("section", "evidence-section");
    s.id = `evidence-${sec.id}`;
    s.dataset.section = sec.id;
    s.setAttribute("aria-labelledby", `${s.id}-h`);
    const h = el("h3", undefined, sec.title);
    h.id = `${s.id}-h`;
    s.append(h);
    for (const p of sec.paragraphs ?? []) {
      const t = filled(p);
      if (t !== null) s.append(el("p", undefined, t));
    }
    if (sec.list) {
      const ul = el("ul", "evidence-list");
      ul.append(...items(sec.list));
      if (ul.childElementCount) s.append(ul);
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
        if (row.some((cell) => hasToken(fill(cell)))) continue; // a row whose figure is missing is left out
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
    if (sec.id === "lake-checks") {
      const t = lakeChecksTable();
      if (t) {
        const wrap = el("div", "table-wrap");
        wrap.append(t);
        s.append(wrap);
      }
    }
    for (const p of sec.afterTable ?? []) {
      const t = filled(p);
      if (t !== null) s.append(el("p", undefined, t));
    }
    parent.append(s);
    h.tabIndex = -1;
    return s;
  }

  function tocLink(label: string, target: HTMLElement, focusEl: HTMLElement, before?: () => void): void {
    const li = el("li");
    const a = el("a", undefined, label);
    a.href = `#${target.id}`;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      before?.();
      const smooth = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      target.scrollIntoView?.({ behavior: smooth ? "smooth" : "auto", block: "start" });
      focusEl.focus({ preventScroll: true });
    });
    focusEl.tabIndex = -1;
    li.append(a);
    tocList.append(li);
  }

  tocLink("How it works", summary, summaryHead);
  for (const sec of evidenceCopy.shortSections) {
    const s = addSection(main, sec);
    tocLink(sec.title, s, s.querySelector("h3")!);
  }

  const tech = el("details", "evidence-technical");
  tech.id = "evidence-technical";
  tech.dataset.role = "evidence-technical";
  const techSummary = el("summary", undefined, evidenceCopy.technical.title);
  tech.append(techSummary, el("p", "evidence-technical-intro", evidenceCopy.technical.intro));
  for (const sec of evidenceCopy.technical.sections) addSection(tech, sec);
  main.append(tech);
  tocLink(evidenceCopy.technical.title, tech, techSummary, () => {
    tech.open = true;
  });

  scroll.append(toc, main);
  root.replaceChildren(scroll);
  return {
    destroy: () => {
      root.innerHTML = "";
    },
  };
}
