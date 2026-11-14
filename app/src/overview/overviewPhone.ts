import { authorityFor } from "../contacts";
import { formatDate } from "../format";
import { statusSlug } from "../lakeLocator";
import { droppedLine, isFrozen, levelMessage, type Lake } from "../lakes";
import { shareState } from "../share";
import { createDrawerPanel, type DrawerPanel } from "./drawerPanel";
import { loadMappedLakes } from "./mappedLakes";
import { statusDisplay } from "../statusDisplay";
import { el, familyChip, statusMark, svg } from "./marks";
import { arrange, latestReadingOnTrack, nextRefresh, type MappedLakesFile, type OverviewFilter, type OverviewState, type SortKey } from "./model";
import { isoDay, OV_CREDITS, OV_FOOTER, shortDate, signed, suparcoShort } from "./text";
import type { OverviewHandle, OverviewOptions } from "./overviewView";

const CHIPS: { filter: OverviewFilter; label: string; mark?: string }[] = [
  { filter: "all", label: "All" },
  { filter: "alert", label: "Alert", mark: "Alert: growing" },
  { filter: "watch", label: "Watch", mark: "Watch" },
  { filter: "open", label: "Open water", mark: "No change" },
  { filter: "frozen", label: "Frozen", mark: "Frozen (likely)" },
  { filter: "no-lake", label: "No lake now", mark: "No lake now" },
  { filter: "above", label: "Above largest" },
  { filter: "suparco", label: "SUPARCO-listed" },
];

/** The sort control: what each choice sets. Change and latest pass put the biggest and the newest first. */
const SORTS: { key: SortKey; dir: "asc" | "desc"; label: string }[] = [
  { key: "status", dir: "asc", label: "Status" },
  { key: "change", dir: "desc", label: "Change" },
  { key: "name", dir: "asc", label: "Name" },
  { key: "latest", dir: "desc", label: "Latest pass" },
];

/** How many lakes the list shows before "Show all". */
const FIRST_LAKES = 8;

const ICON_LOGO = "M4 26 L12 12 L17 19 L21 13 L28 26 Z M6 8 a12 12 0 0 1 10 -4 M6 13 a7 7 0 0 1 6 -4";

function icon(paths: string, view = 20, size = 20, stroke = 2): SVGSVGElement {
  const s = svg("svg", { viewBox: `0 0 ${view} ${view}`, width: String(size), height: String(size), "aria-hidden": "true", class: "ovp-icon", fill: "none", stroke: "currentColor", "stroke-width": String(stroke), "stroke-linecap": "round", "stroke-linejoin": "round" });
  s.append(svg("path", { d: paths }));
  return s;
}

/** The overview on a phone: a field list. A compact header, count chips, the needs-attention card, then the lakes as full-width cards. */
export function renderOverviewPhone(root: HTMLElement, opts: OverviewOptions): OverviewHandle {
  const file = opts.file;
  const lakes = file.lakes;
  const minObs = file.constants.min_observable;
  let state = opts.state;
  let showAll = false;
  const expanded = new Set<string>();

  const shell = el("div", "ovp-shell");
  shell.dataset.role = "ovp-shell";
  const page = el("div", "ovp");
  page.dataset.role = "ovp";

  // ---- Compact header and as-of line -----------------------------------------------------------------------------
  const header = el("header", "ovp-head");
  const top = el("div", "ovp-head-row");
  const brand = el("span", "ovp-brand");
  brand.append(svg("svg", { viewBox: "0 0 32 32", width: "26", height: "26", "aria-hidden": "true", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round" }), el("h1", "ovp-title", "Lake Watch"));
  brand.firstElementChild!.append(svg("path", { d: ICON_LOGO }));
  // The CSV download (Task 14) goes here.
  const actions = el("div", "ovp-actions");
  actions.dataset.role = "ov-actions";
  top.append(brand, actions);
  const asof = el("p", "ovp-asof");
  asof.dataset.role = "ov-asof";
  const parts: [string, string, string][] = [];
  const built = isoDay(file.built);
  if (built) parts.push(["As of ", formatDate(built), ""]);
  const newest = isoDay(file.newest_pass) ?? lakes.map((l) => isoDay(l.status.latest_date)).filter((d): d is string => !!d).sort().pop() ?? null;
  if (newest) parts.push(["latest pass ", shortDate(newest), ""]);
  if (built && Number.isFinite(Date.parse(file.built))) parts.push(["next refresh ", `Mon ${shortDate(nextRefresh(file.built))}`, ""]);
  parts.forEach(([pre, value], i) => {
    if (i) asof.append(" · ");
    asof.append(pre, el("strong", undefined, value));
  });
  header.append(top, asof);
  page.append(header);

  const main = el("main", "ovp-main");
  const dropped = droppedLine(file);
  if (dropped) {
    const p = el("p", "ovp-note", dropped);
    p.dataset.role = "ov-dropped";
    p.setAttribute("role", "status");
    main.append(p);
  }

  // ---- Count chips ------------------------------------------------------------------------------------------------
  const chipsSec = el("section", "ovp-counts");
  chipsSec.setAttribute("aria-label", "Counts and filters");
  const count = el("p", "ovp-count", `${lakes.length} watched ${lakes.length === 1 ? "lake" : "lakes"}`);
  const chips = el("div", "ovp-chips");
  chips.dataset.role = "ovp-chips";
  chips.setAttribute("role", "group");
  chips.setAttribute("aria-label", "Filter by count");
  const chipButtons: HTMLButtonElement[] = [];
  const filterCount = (f: OverviewFilter): number => {
    const a = arrange(lakes, { ...state, show: f, district: null, q: "" }, minObs);
    return a.pinned.length + a.rows.length;
  };
  for (const c of CHIPS) {
    const b = el("button", "ovp-chip");
    b.type = "button";
    b.dataset.filter = c.filter;
    if (c.mark) b.append(statusMark(c.mark, 14));
    b.append(el("span", undefined, c.label), el("span", "ovp-chip-count", String(filterCount(c.filter))));
    b.addEventListener("click", () => set({ show: state.show === c.filter && c.filter !== "all" ? "all" : c.filter }));
    chipButtons.push(b);
    chips.append(b);
  }
  chipsSec.append(count, chips);
  main.append(chipsSec);

  // ---- The needs-attention card (rebuilt on every draw) -----------------------------------------------------------
  const attentionSlot = el("div", "ovp-slot");
  main.append(attentionSlot);

  // ---- Search, sort, list ----------------------------------------------------------------------------------------
  const listSec = el("section", "ovp-listsec");
  listSec.id = "ovp-list";
  listSec.setAttribute("aria-labelledby", "ovp-list-h");
  const listHead = el("div", "ovp-listhead");
  const listTitle = el("h2", "ovp-h", "Watched lakes");
  listTitle.id = "ovp-list-h";
  const shown = el("span", "ovp-shown");
  shown.dataset.role = "ov-shown";
  shown.setAttribute("role", "status");
  listHead.append(listTitle, shown);

  const searchField = el("div", "ovp-field");
  const searchLabel = el("label", undefined, "Find a lake");
  searchLabel.htmlFor = "ovp-q";
  const search = el("input", "ovp-input");
  search.id = "ovp-q";
  search.type = "search";
  search.placeholder = "Name, district or SUPARCO number";
  search.value = state.q;
  search.addEventListener("input", () => set({ q: search.value }));
  searchField.append(searchLabel, search);

  const sortField = el("div", "ovp-field");
  const sortLabel = el("label", undefined, "Sort by");
  sortLabel.htmlFor = "ovp-sort";
  const sort = el("select", "ovp-input");
  sort.id = "ovp-sort";
  for (const s of SORTS) {
    const o = el("option", undefined, s.label);
    o.value = s.key;
    sort.append(o);
  }
  sort.addEventListener("change", () => {
    const s = SORTS.find((x) => x.key === sort.value);
    if (s) set({ sort: s.key, dir: s.dir });
  });
  sortField.append(sortLabel, sort);

  const list = el("div", "ovp-list");
  list.dataset.role = "ovp-list";
  listSec.append(listHead, searchField, sortField, list);
  main.append(listSec);

  const footer = el("footer", "ovp-footer");
  footer.dataset.role = "ov-footer";
  footer.append(el("p", "ovp-footer-main", OV_FOOTER), el("p", "ovp-credits", OV_CREDITS));
  main.append(footer);
  page.append(main);

  // ---- Bottom bar --------------------------------------------------------------------------------------------------
  const bar = el("nav", "ovp-bar");
  bar.dataset.role = "ovp-bar";
  bar.setAttribute("aria-label", "Lake Watch views");
  const listBtn = el("button", "ovp-bar-item");
  listBtn.type = "button";
  listBtn.append(icon("M7 5 H17 M7 10 H17 M7 15 H17 M3 5 H3.5 M3 10 H3.5 M3 15 H3.5"), "List");
  listBtn.addEventListener("click", () => {
    if (state.map) {
      state = { ...state, map: false };
      opts.onState(state);
      draw();
    }
    listSec.scrollIntoView?.({ block: "start" });
  });
  const mapBtn = el("button", "ovp-bar-item");
  mapBtn.type = "button";
  mapBtn.hidden = !opts.mapDrawer;
  mapBtn.setAttribute("aria-controls", "ovp-map");
  mapBtn.append(icon("M2 5 L7 3 L13 5 L18 3 V15 L13 17 L7 15 L2 17 Z M7 3 V15 M13 5 V17", 20, 20, 1.8), "Map");
  mapBtn.addEventListener("click", () => {
    state = { ...state, map: true };
    opts.onState(state);
    draw();
  });
  bar.append(listBtn, mapBtn);

  // ---- The map, full screen above the list ---------------------------------------------------------------------------
  const sheet = el("div", "ovp-sheet");
  sheet.dataset.role = "ovp-map";
  sheet.id = "ovp-map";
  sheet.hidden = true;
  const drawer = el("aside", "ov-drawer");
  drawer.dataset.role = "ov-drawer";
  sheet.append(drawer);

  shell.append(page, sheet, bar);
  root.replaceChildren(shell);

  function set(patch: Partial<OverviewState>): void {
    opts.onState({ ...state, ...patch });
  }

  // ---- Pieces -------------------------------------------------------------------------------------------------------
  const openLink = (cls: string, l: Lake, ...kids: (Node | string)[]): HTMLAnchorElement => {
    const a = el("a", cls);
    a.href = `#lakes/${encodeURIComponent(l.id)}`;
    a.append(...kids);
    a.addEventListener("click", (e) => {
      e.preventDefault();
      opts.onOpenLake(l.id);
    });
    return a;
  };

  const areaText = (l: Lake): { value: string; sub: string } => {
    if (l.lake_state === "no_lake") return { value: "—", sub: "no lake" };
    const r = latestReadingOnTrack(l, minObs);
    if (!r) return { value: "—", sub: "no reading yet" };
    if (l.status.status === "Not measurable") return { value: r.area.toFixed(3), sub: "info only" };
    if (isFrozen(l)) return { value: r.area.toFixed(3), sub: `last open water ${shortDate(r.date)}` };
    const c = l.status.change_km2;
    return { value: r.area.toFixed(3), sub: typeof c === "number" && Number.isFinite(c) ? `${signed(c)} km²` : "" };
  };

  const stat = (label: string, value: string, sub: string): HTMLElement => {
    const d = el("span", "ovp-stat");
    d.append(el("span", "ovp-stat-label", label), el("span", "ovp-stat-value", value));
    if (sub) d.append(el("span", "ovp-stat-sub", sub));
    return d;
  };

  function lakeCard(l: Lake): HTMLElement {
    const li = openLink("ovp-lake", l);
    li.dataset.id = l.id;
    li.dataset.status = statusSlug(l.status.status);
    if (state.sel === l.id) li.dataset.selected = "true";
    const name = el("span", "ovp-lake-name", l.name);
    const sub = el("span", "ovp-lake-sub", [l.district, suparcoShort(l)].filter(Boolean).join(" · "));
    const who = el("span", "ovp-lake-who");
    who.append(name, sub);
    const status = el("span", "ovp-lake-status");
    const d = statusDisplay(l, file.constants);
    status.append(familyChip(d));
    if (d.tag) status.append(el("span", "ovp-since ov-tag", d.tag));
    const area = areaText(l);
    const share = shareState(l);
    const sharePct = share && typeof l.share_of_largest === "number" && Number.isFinite(l.share_of_largest)
      ? { value: `${share.pct}%`, sub: share.word }
      : { value: "—", sub: l.lake_state === "no_lake" ? "no lake" : "not available" };
    const latest = isoDay(l.status.latest_date);
    const stats = el("span", "ovp-stats");
    stats.append(
      stat("Area", area.value === "—" ? "—" : `${area.value} km²`, area.sub),
      stat("Of largest", sharePct.value, sharePct.sub),
      stat("Latest pass", latest ? shortDate(latest) : "—", latest && l.status.track ? `track ${l.status.track}` : ""),
    );
    li.append(who, status, stats);
    return li;
  }

  function attentionItem(l: Lake): HTMLElement {
    const item = el("article", "ovp-item");
    item.dataset.id = l.id;
    item.dataset.status = statusSlug(l.status.status);
    const m = levelMessage(l);
    const status = el("div", "ovp-lake-status");
    const d = statusDisplay(l, file.constants);
    status.append(familyChip(d));
    if (d.tag) status.append(el("span", "ovp-since ov-tag", d.tag));
    const name = openLink("ovp-item-name", l, l.name);
    const c = l.status.change_km2;
    const change = el("p", "ovp-change", typeof c === "number" && Number.isFinite(c) ? `${signed(c)} km² against the baseline` : m ? m.title : l.status.reason);
    const r = latestReadingOnTrack(l, minObs);
    const latest = isoDay(l.status.latest_date);
    const areaLine = el("p", "ovp-arealine", [r ? `Area ${r.area.toFixed(3)} km²` : "No reading yet", latest ? `latest pass ${shortDate(latest)}` : ""].filter(Boolean).join(" · "));

    const panelId = `ovp-msg-${l.id}`;
    const toggle = el("button", "ovp-toggle");
    toggle.type = "button";
    toggle.setAttribute("aria-controls", panelId);
    const label = el("span");
    const arrow = svg("path", { d: "" });
    const arrowSvg = svg("svg", { viewBox: "0 0 14 14", width: "14", height: "14", "aria-hidden": "true", class: "ovp-arrow" });
    arrowSvg.append(arrow);
    toggle.append(label, arrowSvg);
    const panel = el("dl", "ovp-message");
    panel.id = panelId;
    const part = (h: string, t: string): void => {
      const d = el("div");
      d.append(el("dt", undefined, h), el("dd", undefined, t));
      panel.append(d);
    };
    if (m) {
      part("What changed", m.what);
      part("How sure", m.since ? `${m.how_sure} ${m.since}` : m.how_sure);
      part("What it is not", m.not);
      part("What to do", m.do);
    } else {
      part("What the data show", l.status.reason);
    }
    const show = (): void => {
      const open = expanded.has(l.id);
      toggle.setAttribute("aria-expanded", String(open));
      label.textContent = `${open ? "Hide" : "Show"} ${m ? "first message" : "details"}`;
      arrow.setAttribute("d", open ? "M3 9 L7 5 L11 9" : "M3 5 L7 9 L11 5");
      panel.hidden = !open;
    };
    toggle.addEventListener("click", () => {
      if (expanded.has(l.id)) expanded.delete(l.id);
      else expanded.add(l.id);
      show();
    });
    show();
    item.append(status, name, change, areaLine, toggle, panel);
    return item;
  }

  function attentionCard(pinned: Lake[]): HTMLElement {
    const sec = el("section", "ovp-attention");
    sec.dataset.role = "ovp-attention";
    sec.setAttribute("aria-labelledby", "ovp-attn-h");
    const h = el("h2", "ovp-h", `Needs attention (${pinned.length})`);
    h.id = "ovp-attn-h";
    sec.append(h);
    for (const l of pinned) sec.append(attentionItem(l));
    // One button for each authority that has a verified page, for the provinces of the lakes above.
    const seen = new Set<string>();
    const authorities: { id: string; label: string; url: string }[] = [];
    for (const l of pinned) {
      const a = authorityFor(l.province);
      if (a?.url && !seen.has(a.id)) {
        seen.add(a.id);
        authorities.push({ id: a.id, label: a.label, url: a.url });
      }
    }
    if (authorities.length) {
      const box = el("div", "ovp-contact");
      box.append(el("p", "ovp-contact-text", "If people on the ground report the lake changing:"));
      const row = el("div", "ovp-contact-row");
      authorities.forEach((a, i) => {
        const link = el("a", `ovp-btn${i ? "" : " ovp-btn-primary"}`, a.label);
        link.href = a.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.dataset.action = "authority";
        row.append(link);
      });
      box.append(row);
      sec.append(box);
    }
    return sec;
  }

  // ---- Draw ---------------------------------------------------------------------------------------------------
  function draw(): void {
    for (const b of chipButtons) b.setAttribute("aria-pressed", String(state.show === b.dataset.filter));
    if (search.value !== state.q) search.value = state.q;
    if (!SORTS.some((s) => s.key === state.sort)) {
      // A sort set from the address (area, share, elevation) that this control has no choice for.
      let extra = sort.querySelector<HTMLOptionElement>("option[data-extra]");
      if (!extra) {
        extra = el("option");
        extra.dataset.extra = "true";
        sort.append(extra);
      }
      extra.value = state.sort;
      extra.textContent = state.sort === "share" ? "% of largest extent" : state.sort.charAt(0).toUpperCase() + state.sort.slice(1);
    }
    sort.value = state.sort;

    const { pinned, rows } = arrange(lakes, state, minObs);
    shown.textContent = `${pinned.length + rows.length} shown`;
    attentionSlot.replaceChildren(...(pinned.length ? [attentionCard(pinned)] : []));

    const body: HTMLElement[] = rows.slice(0, showAll ? rows.length : FIRST_LAKES).map(lakeCard);
    if (!showAll && rows.length > FIRST_LAKES) {
      const more = el("button", "ovp-btn ovp-more", `Show all ${pinned.length + rows.length} lakes`);
      more.type = "button";
      more.addEventListener("click", () => {
        showAll = true;
        draw();
      });
      body.push(more);
    }
    if (!pinned.length && !rows.length) {
      const p = el("p", "ovp-empty", "No watched lake matches. Try another count or clear the search.");
      p.dataset.role = "ov-empty";
      body.push(p);
    }
    list.replaceChildren(...body);
    syncMap();
  }

  // ---- Map: made when first opened, kept (hidden) after -----------------------------------------------------------
  let panel: DrawerPanel | null = null;
  let mappedOnce: Promise<MappedLakesFile | null> | null = null;
  function syncMap(): void {
    const open = state.map && !!opts.mapDrawer;
    sheet.hidden = !open;
    shell.dataset.map = String(open);
    if (open) mapBtn.setAttribute("aria-current", "page");
    else mapBtn.removeAttribute("aria-current");
    if (open) listBtn.removeAttribute("aria-current");
    else listBtn.setAttribute("aria-current", "page");
    if (open && !panel && opts.mapDrawer) {
      const load = opts.loadMapped ?? (() => loadMappedLakes());
      panel = createDrawerPanel(drawer, {
        lakes,
        minObservable: minObs,
        factory: opts.mapDrawer,
        loadMapped: () => (mappedOnce ??= load()),
        onSelect: (id) => set({ sel: id }),
        onClose: () => set({ map: false }),
        onOpenLake: opts.onOpenLake,
      });
    }
    panel?.setSelection(state.sel);
  }

  draw();

  return {
    update(s: OverviewState): void {
      state = s;
      draw();
    },
    destroy(): void {
      panel?.destroy();
      root.replaceChildren();
    },
  };
}
