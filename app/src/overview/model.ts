import { FROZEN_STATUSES, hasLakeNow, isTrendPass, sortLakes, type Lake, type LakeStatusName } from "../lakes";
import { statusDisplay } from "../statusDisplay";

export type OverviewFilter = "all" | "attention" | "alert" | "watch" | "open" | "frozen" | "breakup" | "unmeasured" | "above" | "changed" | "no-lake" | "suparco";
export type SortKey = "status" | "name" | "area" | "change" | "share" | "latest" | "elevation";

export interface OverviewState {
  show: OverviewFilter;
  district: string | null;
  q: string;
  sort: SortKey;
  dir: "asc" | "desc";
  map: boolean;
  sel: string | null;
}

export const DEFAULT_STATE: OverviewState = { show: "all", district: null, q: "", sort: "status", dir: "asc", map: false, sel: null };

const FILTERS: OverviewFilter[] = ["all", "attention", "alert", "watch", "open", "frozen", "breakup", "unmeasured", "above", "changed", "no-lake", "suparco"];
const SORT_KEYS: SortKey[] = ["status", "name", "area", "change", "share", "latest", "elevation"];

/** The sort each column header sets; the trend column sorts by the change. */
export const SORT_FOR_COLUMN: Record<"lake" | "status" | "area" | "share" | "trend" | "latest" | "elevation", SortKey> = {
  lake: "name", status: "status", area: "area", share: "share", trend: "change", latest: "latest", elevation: "elevation",
};

/** The mapped inventory (data/mapped_lakes.json), drawn on the overview's map drawer. */
export interface MappedLake {
  id: string;
  lon: number;
  lat: number;
  km2: number;
  year: number | null;
  source: "hkhpk2020" | "himag" | "osm";
  suparco: { id: number; match: "probable" } | null;
}

export interface MappedLakesFile {
  version: number;
  built: string;
  notice: { odbl: string; cc_by: string };
  sources: { id: string; name: string; licence: string; attribution: string; url: string }[];
  lakes: MappedLake[];
}

export type MapDrawerFactory = (
  el: HTMLElement,
  opts: { lakes: Lake[]; loadMapped: () => Promise<MappedLakesFile | null>; onPick(id: string): void },
) => { highlight(id: string | null): void; setMappedVisible(on: boolean): void; destroy(): void };

/** Reads the query after `#lakes?`. Only unknown show, sort, dir and map values fall back; a district is kept as given. */
export function parseOverviewHash(query: string): OverviewState {
  const p = new URLSearchParams(query.replace(/^\?/, ""));
  const show = p.get("show") as OverviewFilter;
  const [key, dir] = (p.get("sort") ?? "").split(/-(?=[^-]*$)/);
  return {
    show: FILTERS.includes(show) ? show : DEFAULT_STATE.show,
    district: p.get("district") || null,
    q: p.get("q") ?? "",
    sort: SORT_KEYS.includes(key as SortKey) ? (key as SortKey) : DEFAULT_STATE.sort,
    dir: dir === "asc" || dir === "desc" ? dir : DEFAULT_STATE.dir,
    map: p.get("map") === "1",
    sel: p.get("sel") || null,
  };
}

/** The query for `#lakes?`, defaults left out. */
export function overviewQuery(s: OverviewState): string {
  const e = encodeURIComponent;
  const parts: string[] = [];
  if (s.show !== DEFAULT_STATE.show) parts.push(`show=${e(s.show)}`);
  if (s.district) parts.push(`district=${e(s.district)}`);
  if (s.q) parts.push(`q=${e(s.q)}`);
  if (s.sort !== DEFAULT_STATE.sort || s.dir !== DEFAULT_STATE.dir) parts.push(`sort=${e(`${s.sort}-${s.dir}`)}`);
  if (s.map) parts.push("map=1");
  if (s.sel) parts.push(`sel=${e(s.sel)}`);
  return parts.join("&");
}

/** Alert: growing, Watch, Decrease noted, or a site where Sentinel-2 shows water that may be a lake forming. */
export function needsAttention(l: Lake): boolean {
  const s = l.status.status;
  return s === "Alert: growing" || s === "Watch" || s === "Decrease noted" || l.lake_state === "lake_forming_check";
}

const isFrozenLake = (l: Lake): boolean => FROZEN_STATUSES.includes(l.status.status as LakeStatusName);

function passesFilter(l: Lake, show: OverviewFilter): boolean {
  switch (show) {
    case "all": return true;
    case "attention": return needsAttention(l);
    case "alert": return l.status.status === "Alert: growing";
    case "watch": return l.status.status === "Watch";
    case "open": return (l.lake_state === undefined || l.lake_state === "lake" || l.lake_state === "unconfirmed") && !isFrozenLake(l);
    case "frozen": return statusDisplay(l).family === "frozen";
    case "breakup": return statusDisplay(l).family === "breakup";
    case "unmeasured": return statusDisplay(l).family === "unmeasured";
    case "above": return l.above_largest === true;
    case "changed": return l.previous_status != null && l.previous_status !== l.status.status;
    case "no-lake": return l.lake_state === "no_lake";
    case "suparco": return l.suparco != null;
  }
}

/** True when the lake passes the filter, the district and the search (name, id, district, SUPARCO id). */
export function matches(l: Lake, s: OverviewState): boolean {
  if (!passesFilter(l, s.show)) return false;
  if (s.district !== null && l.district !== s.district) return false;
  const q = s.q.trim().toLowerCase();
  if (!q) return true;
  const hay = [l.name, l.id, l.district ?? "", l.suparco && l.suparco.match !== "possible" ? String(l.suparco.id) : ""];
  return hay.some((h) => h.toLowerCase().includes(q));
}

/** The status track's newest valid, non-frozen reading, or null. */
export function latestReadingOnTrack(l: Lake, minObservable: number): { date: string; area: number } | null {
  const pts = trendSeries(l, minObservable);
  const last = pts[pts.length - 1];
  return last ? { date: last.date, area: last.area_km2 as number } : null;
}

function trendSeries(l: Lake, minObservable: number): Lake["series"] {
  const track = l.status.track;
  if (track === null || !hasLakeNow(l)) return [];
  return l.series
    .filter((p) => p.track === track && isTrendPass(p, minObservable))
    .sort((a, b) => a.date.localeCompare(b.date));
}

/** The status track's valid, non-frozen readings as time and area, oldest first. */
export function trendPoints(l: Lake, minObservable: number): { t: number; v: number }[] {
  return trendSeries(l, minObservable).map((p) => ({ t: Date.parse(p.date), v: p.area_km2 as number }));
}

/** An SVG path through the points on their own scale; empty for fewer than two points. */
export function sparklinePath(pts: { t: number; v: number }[], w = 96, h = 24): string {
  if (pts.length < 2) return "";
  const pad = 1;
  const t0 = Math.min(...pts.map((p) => p.t)), t1 = Math.max(...pts.map((p) => p.t));
  const v0 = Math.min(...pts.map((p) => p.v)), v1 = Math.max(...pts.map((p) => p.v));
  const x = (t: number) => (t1 === t0 ? w / 2 : pad + ((t - t0) / (t1 - t0)) * (w - 2 * pad));
  const y = (v: number) => (v1 === v0 ? h / 2 : h - pad - ((v - v0) / (v1 - v0)) * (h - 2 * pad));
  return pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}`).join(" ");
}

function sortValue(l: Lake, key: Exclude<SortKey, "status">, minObservable: number): number | string | null {
  switch (key) {
    case "name": return l.name.toLowerCase();
    case "area": return latestReadingOnTrack(l, minObservable)?.area ?? null;
    case "change": return l.status.change_km2;
    case "share": return l.share_of_largest ?? null;
    case "latest": return l.status.latest_date;
    case "elevation": return l.elevation_m ?? null;
  }
}

const byId = (a: Lake, b: Lake): number => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

/** Matching needs-attention lakes pinned first (status order), then the rest by the chosen sort, nulls last either way. */
export function arrange(lakes: Lake[], s: OverviewState, minObservable: number): { pinned: Lake[]; rows: Lake[] } {
  const hits = lakes.filter((l) => matches(l, s));
  const pinned = sortLakes(hits.filter(needsAttention));
  const rest = hits.filter((l) => !needsAttention(l));
  const sign = s.dir === "asc" ? 1 : -1;
  if (s.sort === "status") {
    const ordered = sortLakes(rest);
    return { pinned, rows: s.dir === "asc" ? ordered : [...ordered].reverse() };
  }
  const key = s.sort;
  const rows = [...rest].sort((a, b) => {
    const va = sortValue(a, key, minObservable), vb = sortValue(b, key, minObservable);
    if (va === null && vb === null) return byId(a, b);
    if (va === null) return 1;
    if (vb === null) return -1;
    if (va === vb) return byId(a, b);
    return (va < vb ? -1 : 1) * sign;
  });
  return { pinned, rows };
}

/** The next Monday 03:00 UTC strictly after `builtIso` (refresh.yml cron "0 3 * * 1"), as YYYY-MM-DD. */
export function nextRefresh(builtIso: string): string {
  const built = Date.parse(builtIso);
  const d = new Date(built);
  let c = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 3);
  while (c <= built || new Date(c).getUTCDay() !== 1) c += 86_400_000;
  return new Date(c).toISOString().slice(0, 10);
}
