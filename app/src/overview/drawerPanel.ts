import { formatDate } from "../format";
import { isFrozen, suparcoLine, type Lake } from "../lakes";
import { displayForStatus, el, familyChip, familyMark, svg } from "./marks";
import { statusDisplay } from "../statusDisplay";
import { SOURCE_LABELS, watchThisLakeUrl } from "./mappedLakes";
import { latestReadingOnTrack, type MapDrawerFactory, type MappedLake, type MappedLakesFile } from "./model";

/** One status per family, in the order of the legend: Frozen and Not measured each appear once, Ice breaking up apart. */
export const LEGEND_STATUSES = [
  "Alert: growing", "Watch", "Decrease noted", "No change", "Lake may be forming", "Frozen (likely)",
  "Break-up likely", "No lake now", "Not observable",
];

export interface DrawerPanelOptions {
  lakes: Lake[];
  minObservable: number;
  factory: MapDrawerFactory;
  loadMapped(): Promise<MappedLakesFile | null>;
  /** A watched lake was picked on the map: the overview selects its row. */
  onSelect(id: string | null): void;
  onOpenLake(id: string): void;
  /** The "Close map" button. */
  onClose(): void;
}

export interface DrawerPanel {
  /** The overview's selected lake (or none); clears a picked grey dot when it changes. */
  setSelection(id: string | null): void;
  destroy(): void;
}

const isoDay = (v: string | null | undefined): string | null => (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v) ? v.slice(0, 10) : null);

function facts(rows: [string, string][]): HTMLElement {
  const dl = el("dl", "ov-facts");
  for (const [k, v] of rows) {
    const d = el("div");
    d.append(el("dt", undefined, k), el("dd", undefined, v));
    dl.append(d);
  }
  return dl;
}

/** The map, the switch for the grey dots, the selected-lake card, the legend and the licence notices. */
export function createDrawerPanel(host: HTMLElement, opts: DrawerPanelOptions): DrawerPanel {
  const lakeById = new Map(opts.lakes.map((l) => [l.id, l]));
  let mapped: MappedLakesFile | null = null;
  const mappedById = new Map<string, MappedLake>();
  let selWatched: string | null = null;
  let selMapped: string | null = null;
  let gone = false;

  const header = el("div", "ov-drawer-head");
  const heading = el("h2", "ov-drawer-title", "Map");
  const close = el("button", "ov-btn", "Close map");
  close.type = "button";
  close.dataset.role = "ov-map-close";
  close.addEventListener("click", () => opts.onClose());
  header.append(heading, close);
  const mapEl = el("div", "ov-map");
  mapEl.dataset.role = "ov-map";
  mapEl.setAttribute("aria-label", "Map of the watched lakes");
  const switchRow = el("div", "ov-mapped-row");
  switchRow.dataset.role = "ov-mapped-row";
  switchRow.setAttribute("role", "status");
  switchRow.textContent = "Loading mapped lakes…";
  const card = el("div", "ov-card-slot");
  const legend = el("ul", "ov-legend");
  legend.dataset.role = "ov-legend";
  legend.setAttribute("aria-label", "Legend");
  for (const s of LEGEND_STATUSES) {
    const li = el("li");
    const d = displayForStatus(s);
    li.append(familyMark(d, 14), d.chip);
    legend.append(li);
  }
  const dot = svg("svg", { viewBox: "0 0 20 20", width: "14", height: "14", "aria-hidden": "true", class: "ov-mapped-dot" });
  dot.append(svg("circle", { cx: "10", cy: "10", r: "4" }));
  const dotItem = el("li");
  dotItem.append(dot, "Mapped, not watched yet");
  legend.append(dotItem);
  const notices = el("div", "ov-notices");
  notices.dataset.role = "ov-notices";
  host.replaceChildren(header, mapEl, switchRow, card, legend, notices);

  let once: Promise<MappedLakesFile | null> | null = null;
  const loadOnce = (): Promise<MappedLakesFile | null> => (once ??= opts.loadMapped());

  const handle = opts.factory(mapEl, {
    lakes: opts.lakes,
    loadMapped: loadOnce,
    onPick: (id) => {
      if (mappedById.has(id)) {
        selWatched = null; // the table's highlight goes; the host hears it as no selection
        selMapped = id;
        handle.highlight(id);
        drawCard();
        opts.onSelect(null);
      } else if (lakeById.has(id)) {
        selMapped = null;
        opts.onSelect(id);
      }
    },
  });

  function watchedCard(l: Lake): HTMLElement {
    const box = el("div", "ov-card");
    const head = el("div", "ov-card-head");
    const d = statusDisplay(l);
    head.append(el("h3", "ov-card-title", l.name), familyChip(d));
    if (d.tag) head.append(el("span", "ov-card-note", d.tag));
    const r = latestReadingOnTrack(l, opts.minObservable);
    const area = l.lake_state === "no_lake" ? "No lake now" : r ? `${r.area.toFixed(3)} km² (NISAR radar${isFrozen(l) ? ", last open water" : ""})` : "No reading yet";
    const ext = l.largest_extent;
    const day = isoDay(l.status.latest_date);
    const open = el("a", "ov-card-link", "Open lake history");
    open.href = `#lakes/${l.id}`;
    open.addEventListener("click", (e) => {
      e.preventDefault();
      opts.onOpenLake(l.id);
    });
    box.append(
      head,
      facts([
        ["District", l.district ?? "Not known"],
        ["SUPARCO list", suparcoLine(l)],
        ["Area", area],
        ["Largest recorded extent", ext ? `${ext.km2.toFixed(3)} km² (${ext.source}${ext.year ? ` ${ext.year}` : ""})` : "Not available"],
        ["Latest pass", day ? `${formatDate(day)}${l.status.track ? `, track ${l.status.track}` : ""}` : "None yet"],
        ["Elevation", typeof l.elevation_m === "number" && Number.isFinite(l.elevation_m) ? `${Math.round(l.elevation_m).toLocaleString("en-US")} m` : "Not known"],
      ]),
      open,
    );
    return box;
  }

  function mappedCard(m: MappedLake): HTMLElement {
    const box = el("div", "ov-card");
    const head = el("div", "ov-card-head");
    const tag = el("span", "ov-chip ov-chip-mapped");
    const d = svg("svg", { viewBox: "0 0 20 20", width: "12", height: "12", "aria-hidden": "true", class: "ov-mapped-dot" });
    d.append(svg("circle", { cx: "10", cy: "10", r: "4" }));
    tag.append(d, el("span", undefined, "Mapped, not watched yet"));
    head.append(el("h3", "ov-card-title", `Mapped lake ${m.id}`), tag);
    const watch = el("a", "ov-card-link", "Watch this lake");
    watch.href = watchThisLakeUrl(m);
    watch.target = "_blank";
    watch.rel = "noopener";
    box.append(
      head,
      facts([
        ["Outline", `${SOURCE_LABELS[m.source]}, ${m.year ?? "undated"}`],
        ["Outline area", `${m.km2.toFixed(3)} km²`],
        ["SUPARCO list", m.suparco ? `SUPARCO PDGL ${m.suparco.id} (probable match)` : "Not matched to a SUPARCO PDGL ID"],
        ["Position", `${m.lat.toFixed(4)}, ${m.lon.toFixed(4)}`],
      ]),
      el("p", "ov-card-note", "No radar reading yet. Watch this lake opens a lake request on GitHub with this point filled in; press Submit there."),
      watch,
    );
    return box;
  }

  function drawCard(): void {
    const m = selMapped ? mappedById.get(selMapped) : undefined;
    const l = selWatched ? lakeById.get(selWatched) : undefined;
    card.replaceChildren();
    if (m) card.append(mappedCard(m));
    else if (l) card.append(watchedCard(l));
    else card.append(el("p", "ov-card-hint", "Select a lake in the table or on the map to show it here."));
    (card.firstElementChild as HTMLElement).dataset.role = m || l ? "ov-card" : "ov-card-hint";
  }
  drawCard();

  void loadOnce().then((f) => {
    if (gone) return;
    mapped = f;
    if (!mapped) {
      switchRow.textContent = "Mapped lakes could not be loaded.";
      return;
    }
    for (const m of mapped.lakes) mappedById.set(m.id, m);
    const label = el("label", "ov-mapped-switch");
    const box = el("input");
    box.type = "checkbox";
    box.checked = true;
    box.dataset.role = "ov-mapped-switch";
    box.addEventListener("change", () => handle.setMappedVisible(box.checked));
    label.append(box, ` Show ${mapped.lakes.length} mapped lakes, not watched yet (grey dots)`);
    switchRow.replaceChildren(label);
    notices.replaceChildren(el("p", undefined, mapped.notice.odbl), el("p", undefined, mapped.notice.cc_by));
  });

  return {
    setSelection(id) {
      const changed = id !== selWatched;
      if (changed) selMapped = null;
      selWatched = id;
      handle.highlight(selMapped ?? id);
      if (changed) drawCard();
    },
    destroy() {
      gone = true;
      handle.destroy();
      host.replaceChildren();
    },
  };
}
