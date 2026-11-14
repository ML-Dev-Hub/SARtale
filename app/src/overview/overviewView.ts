import "./overview.css";
import { formatDate } from "../format";
import { renderOverviewPhone } from "./overviewPhone";
import { isoDay, OV_CREDITS, OV_FOOTER, shortDate, signed, suparcoShort } from "./text";
export { OV_CREDITS, OV_FOOTER, suparcoShort };
import { droppedLine, isFrozen, levelMessage, type HeadlineCounts, type Lake, type LakesFile } from "../lakes";
import { statusSlug } from "../lakeLocator";
import { shareState } from "../share";
import { familyCounts, frozenBreakdown, statusDisplay } from "../statusDisplay";
import { createDrawerPanel, type DrawerPanel } from "./drawerPanel";
import { loadMappedLakes } from "./mappedLakes";
import { familyChip, statusChip, statusMark, el, svg } from "./marks";
export { statusChip, statusMark };
import {
  arrange, latestReadingOnTrack, nextRefresh, SORT_FOR_COLUMN, sparklinePath, trendPoints,
  type MapDrawerFactory, type MappedLakesFile, type OverviewFilter, type OverviewState, type SortKey,
} from "./model";

export interface OverviewOptions {
  file: LakesFile;
  state: OverviewState;
  onState(s: OverviewState): void;
  onOpenLake(id: string): void;
  isPhone?: boolean;
  /** The map drawer (Task 15); the overview leaves `ov-drawer` empty without it. */
  mapDrawer?: MapDrawerFactory;
  /** Reads the mapped lakes; called once, when the drawer first opens. Defaults to data/mapped_lakes.json. */
  loadMapped?: () => Promise<MappedLakesFile | null>;
}

export interface OverviewHandle {
  update(s: OverviewState): void;
  destroy(): void;
}

const COUNT_KEYS: (keyof HeadlineCounts)[] = [
  "watched", "alert", "watch", "decrease", "forming", "needs_attention", "open_water", "frozen", "no_lake", "above_largest", "suparco_listed", "changed",
];

/** True when the file's headline counts are all there and are whole numbers (older builds have none). */
export function validCounts(c: unknown): c is HeadlineCounts {
  if (typeof c !== "object" || c === null) return false;
  const o = c as Record<string, unknown>;
  return COUNT_KEYS.every((k) => typeof o[k] === "number" && Number.isInteger(o[k]) && (o[k] as number) >= 0);
}

/** "A", "A and B", "A, B and 2 more". */
export function nameList(names: string[], max = 2): string {
  if (names.length <= 1) return names.join("");
  if (names.length <= max) return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `${names.slice(0, max).join(", ")} and ${names.length - max} more`;
}

const COLUMNS: { col: keyof typeof SORT_FOR_COLUMN; label: string; num: boolean }[] = [
  { col: "lake", label: "Lake · district · SUPARCO", num: false },
  { col: "status", label: "Status", num: false },
  { col: "area", label: "Area (km²)", num: true },
  { col: "share", label: "% of largest extent", num: true },
  { col: "trend", label: "Trend (status track)", num: false },
  { col: "latest", label: "Latest pass", num: false },
  { col: "elevation", label: "Elev. (m)", num: true },
];

const SORT_NAMES: Record<SortKey, string> = {
  status: "status", name: "name", area: "area", change: "change against the baseline", share: "% of largest extent", latest: "latest pass", elevation: "elevation",
};

const FILTER_CHIPS: { filter: OverviewFilter; label: string }[] = [
  { filter: "all", label: "All" },
  { filter: "attention", label: "Needs attention" },
  { filter: "frozen", label: "Frozen" },
  { filter: "breakup", label: "Ice breaking up" },
  { filter: "unmeasured", label: "Not measured" },
  { filter: "no-lake", label: "No lake now" },
  { filter: "suparco", label: "SUPARCO-listed" },
];

const OV_NOTES = "Area: NISAR radar water area on the lake's status track, from its newest valid open-water pass, with the change against the baseline of earlier passes on that track; \"info only\" marks a lake whose radar water did not pass the Sentinel-2 check. % of largest extent: that area against the largest mapped outline (Hi-MAG 2008–2017, HKH-PK-2020, OpenStreetMap); \"Above\" means it is larger by more than twice the radar noise, \"Within noise\" that it is larger by less than that, and \"noise unknown\" that the noise could not be set. No share is given where the radar water failed the Sentinel-2 check, the outline lies mostly outside the radar window, or there is no outline. Trend: the valid readings of the status track; for a frozen lake it stops at the last open-water reading. SUPARCO numbers are our match by map position and area to SUPARCO's published PDGL IDs; SUPARCO does not publish coordinates.";

function createDesktopOverview(root: HTMLElement, opts: OverviewOptions): OverviewHandle {
  const file = opts.file;
  const lakes = file.lakes;
  const minObs = file.constants.min_observable;
  let state = opts.state;
  const expanded = new Set<string>();

  const wrap = el("div", "ov");
  wrap.dataset.role = "ov";

  // ---- Title, as-of line and actions --------------------------------------------------------------------------
  const head = el("div", "ov-head");
  const titles = el("div", "ov-titles");
  titles.append(el("h1", "ov-title", `Lake Watch: ${lakes.length} watched ${lakes.length === 1 ? "lake" : "lakes"}`));
  const asof = el("p", "ov-asof");
  asof.dataset.role = "ov-asof";
  const parts: [string, string, string][] = [];
  const built = isoDay(file.built);
  if (built) parts.push(["As of ", formatDate(built), " (data built)"]);
  const newest = isoDay(file.newest_pass) ?? lakes.map((l) => isoDay(l.status.latest_date)).filter((d): d is string => !!d).sort().pop() ?? null;
  if (newest) parts.push(["latest NISAR pass ", formatDate(newest), ""]);
  if (built && Number.isFinite(Date.parse(file.built))) parts.push(["next refresh ", `Mon ${formatDate(nextRefresh(file.built))}`, ""]);
  parts.forEach(([pre, value, post], i) => {
    if (i) asof.append(" · ");
    asof.append(pre, el("strong", undefined, value), post);
  });
  titles.append(asof);
  const actions = el("div", "ov-actions");
  actions.dataset.role = "ov-actions";
  let mapToggle: HTMLButtonElement | null = null;
  if (opts.mapDrawer) {
    mapToggle = el("button", "ov-btn");
    mapToggle.type = "button";
    mapToggle.dataset.role = "ov-map-toggle";
    mapToggle.setAttribute("aria-controls", "ov-drawer");
    // The state is kept here first, so the drawer opens at once whether or not the host echoes it back.
    mapToggle.addEventListener("click", () => {
      state = { ...state, map: !state.map };
      opts.onState(state);
      draw();
    });
    actions.append(mapToggle);
  }
  head.append(titles, actions);
  wrap.append(head);

  const dropped = droppedLine(file);
  if (dropped) {
    const p = el("p", "ov-note", dropped);
    p.dataset.role = "ov-dropped";
    p.setAttribute("role", "status");
    wrap.append(p);
  }

  // ---- Headline counts (only from a build that has them) --------------------------------------------------------
  const tileButtons: HTMLButtonElement[] = [];
  if (validCounts(file.counts)) {
    const c = file.counts;
    const of = (s: string) => lakes.filter((l) => l.status.status === s);
    const fam = familyCounts(lakes);
    const frozenSub = (): string => {
      const b = frozenBreakdown(lakes);
      const parts: [number, string][] = ([[b.seen, "seen by Sentinel-2"], [b.temperature, "by air temperature"]] as [number, string][]).filter(([n]) => n);
      return parts.map(([n, t]) => `${n} ${t}`).join(", ");
    };
    const prevBuilt = isoDay(file.previous_build?.built);
    const tiles: { filter: OverviewFilter; label: string; value: number; sub: string; mark?: string }[] = [
      { filter: "all", label: "Lakes watched", value: c.watched, sub: typeof file.mapped_count === "number" && Number.isFinite(file.mapped_count) ? `${file.mapped_count} more mapped, not watched yet` : "" },
      { filter: "alert", label: "Alert: growing", value: c.alert, sub: c.alert ? nameList(of("Alert: growing").map((l) => l.name)) : "None in this build", mark: "Alert: growing" },
      { filter: "watch", label: "Watch", value: c.watch, sub: c.watch ? nameList(of("Watch").map((l) => l.name)) : "None in this build", mark: "Watch" },
      { filter: "open", label: "Open water", value: c.open_water, sub: "A lake now, not frozen", mark: "No change" },
      { filter: "frozen", label: "Frozen", value: fam.frozen, sub: frozenSub(), mark: "Frozen (likely)" },
      { filter: "above", label: "Above largest extent", value: c.above_largest, sub: "Above the largest mapped outline by more than radar noise" },
      { filter: "no-lake", label: "No lake now", value: c.no_lake, sub: nameList(lakes.filter((l) => l.lake_state === "no_lake").map((l) => l.name)), mark: "No lake now" },
      { filter: "changed", label: "Changed since last build", value: c.changed, sub: prevBuilt ? `Since the ${formatDate(prevBuilt)} build` : "" },
    ];
    const sec = el("section", "ov-tiles");
    sec.dataset.role = "ov-tiles";
    sec.setAttribute("aria-label", "Headline counts. Each count is a filter.");
    for (const t of tiles) {
      const b = el("button", "ov-tile");
      b.type = "button";
      b.dataset.filter = t.filter;
      const label = el("span", "ov-tile-label");
      if (t.mark) label.append(statusMark(t.mark, 14));
      label.append(el("span", undefined, t.label));
      b.append(label, el("span", "ov-tile-value", String(t.value)));
      if (t.sub) b.append(el("span", "ov-tile-sub", t.sub));
      b.addEventListener("click", () => set({ show: state.show === t.filter && t.filter !== "all" ? "all" : t.filter }));
      tileButtons.push(b);
      sec.append(b);
    }
    wrap.append(sec);
  }

  // ---- Filters --------------------------------------------------------------------------------------------------
  const filters = el("section", "ov-filters");
  filters.dataset.role = "ov-filters";
  filters.setAttribute("aria-label", "Filters");
  const group = el("div", "ov-chips");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "Show");
  const chipButtons: HTMLButtonElement[] = [];
  const filterCount = (f: OverviewFilter): number => {
    const a = arrange(lakes, { ...state, show: f, district: null, q: "" }, minObs);
    return a.pinned.length + a.rows.length;
  };
  for (const f of FILTER_CHIPS) {
    const b = el("button", "ov-filter");
    b.type = "button";
    b.dataset.filter = f.filter;
    b.append(f.label, " ", el("span", "ov-filter-count", String(filterCount(f.filter))));
    b.addEventListener("click", () => set({ show: f.filter }));
    chipButtons.push(b);
    group.append(b);
  }
  const districtLabel = el("label", "ov-field", "District");
  const district = el("select", "ov-select");
  district.dataset.role = "ov-district";
  district.addEventListener("change", () => set({ district: district.value || null }));
  districtLabel.append(district);
  const searchLabel = el("label", "ov-field", "Find");
  const search = el("input", "ov-search");
  search.type = "search";
  search.dataset.role = "ov-search";
  search.placeholder = "Lake name, ID or PDGL number";
  search.value = state.q;
  search.addEventListener("input", () => set({ q: search.value }));
  searchLabel.append(search);
  const shown = el("span", "ov-shown");
  shown.dataset.role = "ov-shown";
  shown.setAttribute("role", "status");
  filters.append(group, districtLabel, searchLabel, shown);
  wrap.append(filters);

  // ---- Table (and the map drawer's place beside it) ---------------------------------------------------------------
  const main = el("div", "ov-main");
  const tableWrap = el("section", "ov-table-wrap");
  tableWrap.setAttribute("aria-label", "Watched lakes");
  const table = el("div", "ov-table");
  table.dataset.role = "ov-table";
  table.setAttribute("role", "table");
  tableWrap.append(table);
  const drawer = el("aside", "ov-drawer");
  drawer.dataset.role = "ov-drawer";
  drawer.hidden = true;
  main.append(tableWrap, drawer);
  wrap.append(main);

  wrap.append(el("p", "ov-notes", OV_NOTES));
  const footer = el("footer", "ov-footer");
  footer.dataset.role = "ov-footer";
  footer.append(el("p", "ov-footer-main", OV_FOOTER), el("p", "ov-credits", OV_CREDITS));
  wrap.append(footer);

  root.replaceChildren(wrap);

  function set(patch: Partial<OverviewState>): void {
    opts.onState({ ...state, ...patch });
  }

  // ---- Cells --------------------------------------------------------------------------------------------------
  function cell(cls: string, ...kids: (Node | string)[]): HTMLElement {
    const c = el("div", `ov-cell ${cls}`);
    c.setAttribute("role", "cell");
    c.append(...kids);
    return c;
  }

  function nameCell(l: Lake, pinned: boolean): HTMLElement {
    const c = cell("ov-c-lake");
    const name = el("button", "ov-name", l.name);
    name.type = "button";
    name.title = l.name;
    name.addEventListener("click", () => opts.onOpenLake(l.id));
    const sub = [l.district, suparcoShort(l)].filter(Boolean).join(" · ");
    const subEl = el("span", "ov-sub", sub);
    subEl.title = sub;
    const line = el("div", "ov-nameline");
    line.append(name);
    c.append(line, subEl);
    if (opts.mapDrawer) {
      const locate = el("button", "ov-locate", "On map");
      locate.type = "button";
      locate.hidden = !state.map;
      locate.setAttribute("aria-pressed", String(state.sel === l.id));
      locate.setAttribute("aria-label", `Show ${l.name} on the map`);
      locate.addEventListener("click", () => set({ sel: l.id }));
      line.append(locate);
    }
    if (pinned) {
      const m = levelMessage(l);
      const headline = el("span", "ov-headline", m ? m.title : l.status.reason);
      headline.title = m ? m.title : l.status.reason;
      c.append(headline);
    }
    return c;
  }

  function statusCell(l: Lake): HTMLElement {
    const d = statusDisplay(l, file.constants);
    const c = cell("ov-c-status", familyChip(d));
    if (d.tag) {
      const tag = el("span", "ov-sub ov-tag", d.tag);
      tag.title = d.tag;
      c.append(tag);
    }
    return c;
  }

  function areaCell(l: Lake): HTMLElement {
    if (l.lake_state === "no_lake") return cell("ov-c-num", el("span", "ov-num", "—"), el("span", "ov-sub", "no lake"));
    const r = latestReadingOnTrack(l, minObs);
    if (!r) return cell("ov-c-num", el("span", "ov-num", "—"), el("span", "ov-sub", "no reading yet"));
    const sub = isFrozen(l)
      ? `last open water ${shortDate(r.date)}`
      : typeof l.status.change_km2 === "number" && Number.isFinite(l.status.change_km2) ? `${signed(l.status.change_km2)} km²` : "";
    const c = cell("ov-c-num", el("span", "ov-num", r.area.toFixed(3)));
    if (l.status.status === "Not measurable") {
      // The method shows this area as information only: the radar water did not pass the Sentinel-2 check.
      c.dataset.info = "true";
      const info = el("span", "ov-sub", "info only");
      info.title = l.status.reason;
      c.append(info);
      return c;
    }
    if (sub) {
      const s = el("span", "ov-sub", sub);
      if (!isFrozen(l)) s.title = "Change against the baseline of earlier passes on this track";
      c.append(s);
    }
    return c;
  }

  function shareCell(l: Lake): HTMLElement {
    const v = l.share_of_largest;
    if (typeof v !== "number" || !Number.isFinite(v)) {
      const dash = el("span", "ov-num", "—");
      const why = l.share_note ?? (l.lake_state === "no_lake" ? "No lake now" : "No largest extent for this lake in this build");
      dash.title = why;
      return cell("ov-c-num", dash, el("span", "ov-sub", l.lake_state === "no_lake" ? "no lake" : "not available"));
    }
    const st = shareState(l)!;
    const { pct, above } = st;
    const line = el("span", "ov-share");
    const bar = el("span", "ov-bar");
    bar.setAttribute("aria-hidden", "true");
    const fill = el("span", `ov-bar-fill${above ? " ov-bar-above" : ""}`);
    fill.style.width = `${(Math.min(pct, 150) / 150) * 100}%`;
    bar.append(fill, el("span", "ov-bar-tick"));
    line.append(bar, el("span", "ov-num", `${pct}%`));
    const sub = el("span", "ov-sub", st.word);
    if (st.title) sub.title = st.title;
    return cell("ov-c-num", line, sub);
  }

  function trendCell(l: Lake): HTMLElement {
    if (l.lake_state === "no_lake") return cell("ov-c-trend", el("span", "ov-sub", "no lake"));
    const pts = trendPoints(l, minObs);
    const d = sparklinePath(pts, 96, 22);
    if (!d) return cell("ov-c-trend", el("span", "ov-sub", "too few readings"));
    const s = svg("svg", { viewBox: "0 0 100 24", width: "100", height: "24", role: "img", class: `ov-trend${isFrozen(l) ? " ov-trend-frozen" : ""}` });
    const first = new Date(pts[0].t).toISOString().slice(0, 10);
    const last = new Date(pts[pts.length - 1].t).toISOString().slice(0, 10);
    s.setAttribute("aria-label", `Area on track ${l.status.track}: ${pts.length} readings from ${shortDate(first)} to ${shortDate(last)}${isFrozen(l) ? ", up to the last open-water reading" : ""}`);
    const g = svg("g", { transform: "translate(2 1)" });
    g.append(svg("path", { d, class: "ov-spark" }));
    const end = /(-?[\d.]+) (-?[\d.]+)$/.exec(d);
    if (end) g.append(svg("circle", { cx: end[1], cy: end[2], r: "2.4", class: "ov-spark-end" }));
    s.append(g);
    return cell("ov-c-trend", s);
  }

  function latestCell(l: Lake): HTMLElement {
    const d = isoDay(l.status.latest_date);
    if (!d) return cell("ov-c-latest", el("span", "ov-num", "—"));
    const c = cell("ov-c-latest", el("span", "ov-num", shortDate(d)));
    if (l.status.track) c.append(el("span", "ov-sub", `track ${l.status.track}`));
    return c;
  }

  function elevationCell(l: Lake): HTMLElement {
    const v = l.elevation_m;
    return cell("ov-c-num", typeof v === "number" && Number.isFinite(v) ? Math.round(v).toLocaleString("en-US") : "—");
  }

  function row(l: Lake, pinned: boolean): HTMLElement {
    const r = el("div", `ov-row${pinned ? " ov-row-pinned" : ""}`);
    r.setAttribute("role", "row");
    r.dataset.role = pinned ? "ov-pinned" : "ov-row";
    r.dataset.id = l.id;
    if (state.sel === l.id) r.dataset.selected = "true";
    if (pinned) r.dataset.status = statusSlug(l.status.status);
    if (opts.mapDrawer && state.map) {
      r.addEventListener("click", (e) => {
        if (!(e.target as Element).closest("button, a")) set({ sel: l.id });
      });
    }
    r.append(nameCell(l, pinned), statusCell(l), areaCell(l), shareCell(l), trendCell(l), latestCell(l), elevationCell(l));
    return r;
  }

  /** The lake's first message, folded under its pinned row: what changed, how sure, what it is not, what to do. */
  function message(l: Lake): HTMLElement {
    const box = el("div", "ov-message");
    box.dataset.role = "ov-message";
    box.dataset.id = l.id;
    box.setAttribute("role", "row");
    const inner = el("div", "ov-message-cell");
    inner.setAttribute("role", "cell");
    inner.setAttribute("aria-colspan", "7");
    box.append(inner);
    const m = levelMessage(l);
    const panelId = `ov-msg-${l.id}`;
    const btn = el("button", "ov-toggle");
    btn.type = "button";
    btn.setAttribute("aria-controls", panelId);
    const label = el("span");
    const arrow = svg("path", { d: "" });
    const arrowSvg = svg("svg", { viewBox: "0 0 14 14", width: "12", height: "12", "aria-hidden": "true", class: "ov-toggle-arrow" });
    arrowSvg.append(arrow);
    btn.append(label, arrowSvg);
    const panel = el("div", "ov-message-panel");
    panel.id = panelId;
    const part = (h: string, t: string) => {
      const p = el("div", "ov-message-part");
      p.append(el("span", "ov-message-head", h), el("span", undefined, t));
      panel.append(p);
    };
    if (m) {
      part("What changed", m.what);
      part("How sure", m.since ? `${m.how_sure} ${m.since}` : m.how_sure);
      part("What it is not", m.not);
      part("What to do", m.do);
    } else {
      part("What the data show", l.status.reason);
    }
    inner.append(btn, panel);
    const show = (): void => {
      const open = expanded.has(l.id);
      box.setAttribute("aria-expanded", String(open));
      btn.setAttribute("aria-expanded", String(open));
      label.textContent = `${open ? "Hide" : "Show"} ${m ? "first message" : "details"}`;
      arrow.setAttribute("d", open ? "M3 9 L7 5 L11 9" : "M3 5 L7 9 L11 5");
      panel.hidden = !open;
    };
    btn.addEventListener("click", () => {
      if (expanded.has(l.id)) expanded.delete(l.id);
      else expanded.add(l.id);
      show();
    });
    show();
    return box;
  }

  function headerRow(): HTMLElement {
    const r = el("div", "ov-row ov-row-head");
    r.setAttribute("role", "row");
    for (const c of COLUMNS) {
      const key = SORT_FOR_COLUMN[c.col];
      const active = state.sort === key;
      const h = el("div", `ov-cell ov-th${c.num ? " ov-th-num" : ""}`);
      h.setAttribute("role", "columnheader");
      h.setAttribute("aria-sort", active ? (state.dir === "asc" ? "ascending" : "descending") : "none");
      const b = el("button", `ov-sort${active ? " ov-sort-active" : ""}`);
      b.type = "button";
      b.dataset.sort = key;
      // The arrow sits in the label's text flow, glued to its last word, so it stays with the label when it wraps.
      const text = el("span", "ov-sort-label");
      const words = c.label.split(" ");
      const last = el("span", "ov-sort-last", words.pop()!);
      if (words.length) text.append(`${words.join(" ")} `);
      const arrow = svg("svg", { viewBox: "0 0 14 14", width: "12", height: "12", "aria-hidden": "true", class: "ov-sort-arrow" });
      arrow.append(svg("path", { d: active ? (state.dir === "asc" ? "M3 9 L7 5 L11 9" : "M3 5 L7 9 L11 5") : "M4 5.5 L7 2.5 L10 5.5 M4 8.5 L7 11.5 L10 8.5" }));
      last.append("\u00a0", arrow);
      text.append(last);
      b.append(text);
      if (c.col === "trend") b.title = "Sorts by the change against the baseline of the status track";
      b.addEventListener("click", () => set({ sort: key, dir: active && state.dir === "asc" ? "desc" : "asc" }));
      h.append(b);
      r.append(h);
    }
    return r;
  }

  // ---- Draw ---------------------------------------------------------------------------------------------------
  function draw(): void {
    for (const b of tileButtons) b.setAttribute("aria-pressed", String(state.show === b.dataset.filter));
    for (const b of chipButtons) b.setAttribute("aria-pressed", String(state.show === b.dataset.filter));

    const counts = new Map<string, number>();
    for (const l of lakes) if (l.district) counts.set(l.district, (counts.get(l.district) ?? 0) + 1);
    if (state.district && !counts.has(state.district)) counts.set(state.district, 0);
    const opts2 = [el("option", undefined, "All districts")];
    opts2[0].value = "";
    for (const name of [...counts.keys()].sort()) {
      const o = el("option", undefined, `${name} (${counts.get(name)})`);
      o.value = name;
      opts2.push(o);
    }
    district.replaceChildren(...opts2);
    district.value = state.district ?? "";
    if (search.value !== state.q) search.value = state.q;

    const { pinned, rows } = arrange(lakes, state, minObs);
    shown.textContent = `Showing ${pinned.length + rows.length} of ${lakes.length} watched lakes`;
    table.setAttribute("aria-label", `Watched lakes, sorted by ${SORT_NAMES[state.sort]}, ${state.dir === "asc" ? "ascending" : "descending"}. Lakes that need attention are pinned first.`);
    const body: HTMLElement[] = [headerRow()];
    if (pinned.length) {
      const g = el("div", "ov-pinned-group");
      g.setAttribute("role", "rowgroup");
      g.setAttribute("aria-label", "Needs attention");
      const labelRow = el("div", "ov-group-label");
      labelRow.setAttribute("role", "row");
      const labelCell = el("div", "ov-group-label-cell", `Needs attention (${pinned.length})`);
      labelCell.setAttribute("role", "rowheader");
      labelCell.setAttribute("aria-colspan", "7");
      labelCell.dataset.role = "ov-pinned-label";
      labelRow.append(labelCell);
      g.append(labelRow);
      for (const l of pinned) g.append(row(l, true), message(l));
      body.push(g);
    }
    if (rows.length) {
      const g = el("div", "ov-rows");
      g.setAttribute("role", "rowgroup");
      for (const l of rows) g.append(row(l, false));
      body.push(g);
    }
    if (!pinned.length && !rows.length) {
      const p = el("p", "ov-empty", "No watched lake matches these filters.");
      p.dataset.role = "ov-empty";
      body.push(p);
    }
    table.replaceChildren(...body);
    syncDrawer();
  }

  // ---- Map drawer: made when first opened, kept (hidden) after ------------------------------------------------------
  let panel: DrawerPanel | null = null;
  let mappedOnce: Promise<MappedLakesFile | null> | null = null;
  function syncDrawer(): void {
    if (!opts.mapDrawer || !mapToggle) return;
    drawer.hidden = !state.map;
    drawer.id = "ov-drawer";
    wrap.dataset.map = String(state.map);
    mapToggle.textContent = state.map ? "Hide map" : "Show map";
    mapToggle.setAttribute("aria-expanded", String(state.map));
    if (state.map && !panel) {
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

/** Widths up to this are a phone: the overview gets its own layout (overviewPhone.ts). */
export const PHONE_QUERY = "(max-width: 760px)";

/**
 * The overview: the table layout, or on a phone its own layout. `isPhone` fixes the choice (tests); without it the layout
 * follows the screen width and is drawn again, with the current state, when that crosses the phone width.
 */
export function createOverview(root: HTMLElement, opts: OverviewOptions): OverviewHandle {
  let state = opts.state;
  const mq = opts.isPhone === undefined ? window.matchMedia?.(PHONE_QUERY) : undefined;
  const phoneNow = (): boolean => opts.isPhone ?? mq?.matches ?? false;
  const mount = (phone: boolean): OverviewHandle => {
    const o = { ...opts, state, onState: (s: OverviewState) => { state = s; opts.onState(s); } };
    return phone ? renderOverviewPhone(root, o) : createDesktopOverview(root, o);
  };
  let phone = phoneNow();
  let inner = mount(phone);
  const onChange = (): void => {
    if (phoneNow() === phone) return;
    phone = !phone;
    inner.destroy();
    inner = mount(phone);
  };
  mq?.addEventListener?.("change", onChange);
  return {
    update(s) {
      state = s;
      inner.update(s);
    },
    destroy() {
      mq?.removeEventListener?.("change", onChange);
      inner.destroy();
    },
  };
}
