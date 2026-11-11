import { formatDate } from "./format";

export type LakeStatusName =
  | "Growing"
  | "Stable"
  | "Shrinking"
  | "Change not confirmed yet"
  | "Not seen this pass"
  | "Not observable"
  | "Not enough NISAR looks yet"
  | "No lake now";

/** What recent imagery shows at a site: a lake, a dark area not confirmed as a lake, or no lake now (absent in older builds: a lake). */
export type LakeState = "lake" | "unconfirmed" | "no_lake";

export interface LakeStatus {
  status: LakeStatusName;
  track: string | null;
  latest_date: string | null;
  looks: number;
  change_km2: number | null;
  noise_km2: number | null;
  reason: string;
  /** For "Change not confirmed yet": the processing version of the latest pass that its baseline lacks. */
  new_crid?: string | null;
}

export interface LakeSeriesPoint {
  date: string;
  track: string;
  area_km2: number | null;
  observable_share: number | null;
  excluded: string | null;
  /** NISAR processing version (composite release ID) of the pass, e.g. "P05036" (absent in older builds). */
  crid?: string;
}

export interface Lake {
  id: string;
  name: string;
  lon: number;
  lat: number;
  role: "watch" | "control" | "story";
  coord_source: string;
  outline_source: string | null;
  area_label: string;
  /** Absent in older builds, where every site is a lake. */
  lake_state?: LakeState;
  /** What shows the lake state and when; set unless lake_state is "lake". */
  lake_state_source?: string | null;
  downstream: string | null;
  downstream_source: string | null;
  status: LakeStatus;
  cloud_window_looks: number;
  directions: string[];
  limits: string[];
  series: LakeSeriesPoint[];
  excluded: { pass: string; reason: string }[];
  /** `date`/`track`: the pictured pass, the status track's latest valid pass (absent in older builds). */
  images: { latest_hh: string | null; water: string | null; date?: string | null; track?: string | null } | null;
  bounds: [number, number, number, number] | null;
}

export interface LakeCheck {
  lake: string;
  nisar_date: string;
  nisar_track: string;
  s2_date: string;
  s2_id: string;
  days_apart: number;
  s2_window_cloud_pct: number;
  scope: string;
  /** The open-water season the pair was chosen in, e.g. "15 Jun–30 Sep" (absent in older builds). */
  season?: string;
  radar_km2: number;
  optical_km2: number;
  area_error_pct: number | null;
  iou: number | null;
  zone_valid_share: number;
  window_radar_km2: number;
  window_optical_km2: number;
  window_area_error_pct: number | null;
  window_iou: number | null;
}

/** A check row the pipeline wrote without measurements, e.g. {"lake": "x", "note": "no clear Sentinel-2 scene within 3 days"}. */
export interface LakeCheckNote {
  lake: string;
  note: string;
}

/**
 * True for a pass the trend may use: not left out, has an area, and saw at least `minObservable` of the lake zone.
 * The pipeline's status uses the same rule (lakestatus.is_valid).
 */
export function isTrendPass(p: Lake["series"][number], minObservable: number): boolean {
  return p.excluded === null && p.area_km2 !== null && p.observable_share !== null && p.observable_share >= minObservable;
}

/** True for a check row that carries the dates and numbers the app shows. */
export function isMeasuredCheck(c: unknown): c is LakeCheck {
  const r = c as Partial<LakeCheck> | null;
  return !!r && typeof r.lake === "string" && typeof r.nisar_date === "string" && typeof r.s2_date === "string"
    && typeof r.radar_km2 === "number" && typeof r.optical_km2 === "number" && typeof r.days_apart === "number";
}

/** Keeps only measured rows in `checks` and moves the rest to `check_notes`, so one unmeasured row cannot break a view. */
export function splitChecks(f: LakesFile): LakesFile {
  const rows = f.checks as unknown[];
  const notes = rows
    .filter((c) => !isMeasuredCheck(c))
    .map((c) => c as Partial<LakeCheckNote>)
    .filter((c): c is LakeCheckNote => typeof c?.lake === "string" && typeof c.note === "string");
  return { ...f, checks: rows.filter(isMeasuredCheck), check_notes: notes };
}

export interface LakesFile {
  version: number;
  built: string;
  notes: string;
  /** Every NISAR processing version used, sorted and joined with ", ", e.g. "P05023, P05036". */
  crid: string;
  /** CMR collections the passes came from (absent in older builds). */
  collections?: string[];
  cloud_window: [string, string];
  constants: {
    drop_db: number;
    min_looks: number;
    min_observable: number;
    noise_floor_km2: number;
    change_factor: number;
    speckle_box: number;
    /** Robust z-score limit of the second pass screen (absent in older builds). */
    outlier_z?: number;
  };
  lakes: Lake[];
  checks: LakeCheck[];
  /** Check rows without measurements; filled by splitChecks. */
  check_notes?: LakeCheckNote[];
}

export const STATUS_ORDER: LakeStatusName[] = [
  "Growing",
  "Shrinking",
  "Change not confirmed yet",
  "Not seen this pass",
  "Stable",
  "Not enough NISAR looks yet",
  "Not observable",
  "No lake now",
];

/** The site's lake state, "lake" for builds made before the field existed. */
export function lakeState(l: Lake): LakeState {
  return l.lake_state ?? "lake";
}

/** True unless recent imagery shows no lake at the site (an empty ice-dammed basin kept to watch for a lake forming). */
export function hasLakeNow(l: Lake): boolean {
  return lakeState(l) !== "no_lake";
}

/** The sites that hold a lake now: what the lake counts and the cloud-window looks are made of. */
export function lakesNow(file: LakesFile): Lake[] {
  return file.lakes.filter(hasLakeNow);
}

/** Valid looks in the cloud window at the sites that hold a lake now. */
export function cloudLooks(file: LakesFile): number {
  return lakesNow(file).reduce((n, l) => n + l.cloud_window_looks, 0);
}

/** How many sites that hold a lake now had at least one valid look in the cloud window. */
export function cloudLakes(file: LakesFile): number {
  return lakesNow(file).filter((l) => l.cloud_window_looks > 0).length;
}

/** "7 lakes", or "5 lakes and 2 sites with no lake now" when the list keeps empty basins. */
export function watchList(file: LakesFile): string {
  const lakes = lakesNow(file).length;
  const empty = file.lakes.length - lakes;
  const head = `${lakes} ${lakes === 1 ? "lake" : "lakes"}`;
  return empty ? `${head} and ${empty} ${empty === 1 ? "site" : "sites"} with no lake now` : head;
}

function isLakesFile(v: unknown): v is LakesFile {
  const f = v as LakesFile;
  return !!f && Array.isArray(f.lakes) && Array.isArray(f.checks) && f.lakes.every((l) => !!l && typeof l.id === "string" && !!l.status);
}

/**
 * Loads data/lakes.json. Returns null if it is absent or unusable; Lake Watch then says "No lake data in this build".
 * `no-cache` makes the browser check with the server every time (a cheap ETag check), so a weekly data update shows
 * up on the next load instead of after the browser's cache runs out.
 */
export async function loadLakes(url: string, fetchFn: typeof fetch = (...a) => fetch(...a)): Promise<LakesFile | null> {
  try {
    const res = await fetchFn(url, { cache: "no-cache" });
    if (!res.ok) return null;
    const json: unknown = await res.json();
    return isLakesFile(json) ? splitChecks(json) : null;
  } catch {
    return null;
  }
}

function rank(l: Lake): number {
  const i = STATUS_ORDER.indexOf(l.status.status);
  return i < 0 ? STATUS_ORDER.length : i;
}

/** Status order, then newest latest_date first, then name. Control lakes go last. Returns a new array. */
export function sortLakes(lakes: Lake[]): Lake[] {
  return [...lakes].sort((a, b) => {
    const ca = a.role === "control" ? 1 : 0;
    const cb = b.role === "control" ? 1 : 0;
    if (ca !== cb) return ca - cb;
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    const da = a.status.latest_date ?? "";
    const db = b.status.latest_date ?? "";
    if (da !== db) return da < db ? 1 : -1;
    return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  });
}

const km2 = (v: number) => v.toFixed(3);

/** One plain sentence for a lake's status. Never shows a zero area for a lake that was not measured. `changeFactor` is lakes.json constants.change_factor. */
export function statusSentence(lake: Lake, changeFactor: number): string {
  const s = lake.status;
  const measured = s.change_km2 !== null && s.noise_km2 !== null && s.track !== null;
  if (!measured) {
    const latest = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
    return `${s.status}: ${s.reason}${latest}`;
  }
  const scope = lake.area_label.includes("search window") ? " in the search window" : "";
  const shown = km2(Math.abs(s.change_km2 as number));
  // Round first, then pick the sign, so a change that rounds to zero never prints as "-0.000".
  const sign = Number(shown) === 0 ? "" : (s.change_km2 as number) > 0 ? "+" : "-";
  const when = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
  const pending = s.status === "Change not confirmed yet"
    ? `; first pass on NISAR processing version ${s.new_crid ?? "new"}, so the change waits for a second pass on that version`
    : "";
  return `${s.status}: ${sign}${shown} km²${scope} since earlier ${s.track} passes (noise ±${km2(s.noise_km2 as number)} km²; change must exceed ${changeFactor}× noise), ${s.looks} looks${when}${pending}`;
}

/**
 * The lake the story shows in depth: among role "watch" lakes that recent imagery confirms (not "no lake now", not
 * "unconfirmed"), the one with the most valid looks, ties going to the newest latest look, and after that to file
 * order. Chosen at runtime from the data, never named in the copy.
 */
export function featuredLake(file: LakesFile | null | undefined): Lake | null {
  let best: Lake | null = null;
  for (const l of file?.lakes ?? []) {
    if (l.role !== "watch" || lakeState(l) !== "lake") continue;
    if (!best) {
      best = l;
      continue;
    }
    const a = l.status.looks;
    const b = best.status.looks;
    if (a > b || (a === b && (l.status.latest_date ?? "") > (best.status.latest_date ?? ""))) best = l;
  }
  return best;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** "17 June" from "2026-06-17": day and full month, no year (the headline's own style). */
export function dayMonth(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}`;
}

/**
 * The headline count: valid looks in the cloud window, and how many lakes had at least one. SUPARCO's 2 Jul and 5 Aug
 * updates both say cloud limited optical imagery; the 5 Aug one still used images from 6 Jul to 5 Aug, so the
 * headline must not imply SUPARCO had no images in between.
 */
export function cloudHeadline(file: LakesFile): string {
  const looks = cloudLooks(file);
  const watched = cloudLakes(file);
  return `From ${dayMonth(file.cloud_window[0])} to ${dayMonth(file.cloud_window[1])}, while SUPARCO's updates reported cloud limiting optical imagery, NISAR made ${looks} valid looks across ${watched} lakes.`;
}

export const NOT_VALIDATED = "Not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.";

/** 0.0049 -> "0.005", 0.0138 -> "0.014", 0.1137 -> "0.11": two significant figures, at least three decimals below 0.01. */
const iouText = (v: number): string => (v < 0.01 ? v.toFixed(3) : String(Number(v.toPrecision(2))));

/** "IoU 0.013–0.09" from the `checks` rows, or null when none has an IoU. */
export function iouRange(checks: LakeCheck[]): string | null {
  const ious = checks.map((c) => c.iou).filter((v): v is number => v !== null);
  if (!ious.length) return null;
  const lo = Math.min(...ious);
  const hi = Math.max(...ious);
  return lo === hi ? `IoU ${iouText(lo)}` : `IoU ${iouText(lo)}–${iouText(hi)}`;
}

/** How radar water overlapped optical water, worded from the IoU values; null when no check has an IoU. */
export function opticalOverlapPhrase(checks: LakeCheck[]): string | null {
  const rows = checks.filter((c) => c.iou !== null);
  if (!rows.length) return null;
  const hi = Math.max(...rows.map((c) => c.iou as number));
  const range = iouRange(rows)!;
  const lo = Math.min(...rows.map((c) => c.iou as number));
  if (hi < 0.5) return `overlapped optical water poorly at every lake checked (${range})`;
  if (lo < 0.5) return `overlapped optical water unevenly across the ${rows.length} lakes checked (${range})`;
  return `overlapped optical water with ${range} across the ${rows.length} lakes checked`;
}

/** One plain sentence on the Sentinel-2 cross-check, built from the `checks` rows; null when there are none with an IoU. */
export function opticalCheckSentence(checks: LakeCheck[]): string | null {
  const how = opticalOverlapPhrase(checks);
  if (!how) return null;
  const maxDays = Math.max(...checks.filter((c) => c.iou !== null).map((c) => c.days_apart));
  const when = maxDays === 0 ? "a same-day check" : `checks up to ${maxDays} days apart`;
  return `In ${when} against Sentinel-2, radar water ${how}; treat areas as indicative.`;
}

/**
 * The method's standing limits, shown for every lake whatever its own `limits` say: the build notes, what was not
 * validated, and how the Sentinel-2 cross-check went.
 */
export function methodLimits(file: LakesFile): string[] {
  const out = [file.notes, NOT_VALIDATED];
  const optical = opticalCheckSentence(file.checks);
  if (optical) out.push(optical);
  return out.filter((t) => !!t);
}

/** "processing version P05023", or "processing versions P05023 and P05036" when lakes.json lists more than one. */
export function processingVersions(crid: string): string {
  const ids = crid.split(",").map((s) => s.trim()).filter((s) => s);
  if (ids.length <= 1) return `processing version ${ids[0] ?? "unknown"}`;
  return `processing versions ${ids.slice(0, -1).join(", ")} and ${ids[ids.length - 1]}`;
}

/** The numbers and dates that copy quotes, taken from lakes.json so the words cannot drift from the data. */
export function lakeTokens(file: LakesFile): Record<string, string> {
  const c = file.constants;
  return {
    drop_db: String(c.drop_db),
    speckle_box: String(c.speckle_box),
    outlier_z: c.outlier_z === undefined ? "the limit in lakes.json" : String(c.outlier_z),
    min_looks: String(c.min_looks),
    min_observable: String(c.min_observable),
    min_observable_pct: String(Math.round(c.min_observable * 100)),
    noise_floor_km2: String(c.noise_floor_km2),
    change_factor: String(c.change_factor),
    cloud_start: formatDate(file.cloud_window[0]),
    cloud_end: formatDate(file.cloud_window[1]),
    cloud_looks: String(cloudLooks(file)),
    cloud_lakes: String(cloudLakes(file)),
    lake_count: String(lakesNow(file).length),
    site_count: String(file.lakes.length),
    watch_list: watchList(file),
    crid: file.crid,
    processing_versions: processingVersions(file.crid),
    notes: file.notes,
    iou_range: iouRange(file.checks) ?? "no IoU yet",
    optical_overlap: opticalOverlapPhrase(file.checks) ?? "has not been compared with optical water in this build",
  };
}
