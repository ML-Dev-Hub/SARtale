import { formatDate } from "./timeline";

export type LakeStatusName =
  | "Growing"
  | "Stable"
  | "Shrinking"
  | "Not seen this pass"
  | "Not observable"
  | "Not enough NISAR looks yet";

export interface LakeStatus {
  status: LakeStatusName;
  track: string | null;
  latest_date: string | null;
  looks: number;
  change_km2: number | null;
  noise_km2: number | null;
  reason: string;
}

export interface LakeSeriesPoint {
  date: string;
  track: string;
  area_km2: number | null;
  observable_share: number | null;
  excluded: string | null;
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
  downstream: string | null;
  downstream_source: string | null;
  status: LakeStatus;
  cloud_window_looks: number;
  directions: string[];
  limits: string[];
  series: LakeSeriesPoint[];
  excluded: { pass: string; reason: string }[];
  images: { latest_hh: string | null; water: string | null } | null;
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

export interface LakesFile {
  version: number;
  built: string;
  notes: string;
  crid: string;
  cloud_window: [string, string];
  constants: {
    drop_db: number;
    min_looks: number;
    min_observable: number;
    noise_floor_km2: number;
    change_factor: number;
    speckle_box: number;
  };
  lakes: Lake[];
  checks: LakeCheck[];
}

export const STATUS_ORDER: LakeStatusName[] = [
  "Growing",
  "Shrinking",
  "Not seen this pass",
  "Stable",
  "Not enough NISAR looks yet",
  "Not observable",
];

function isLakesFile(v: unknown): v is LakesFile {
  const f = v as LakesFile;
  return !!f && Array.isArray(f.lakes) && Array.isArray(f.checks) && f.lakes.every((l) => !!l && typeof l.id === "string" && !!l.status);
}

/** Loads data/lakes.json. Returns null if it is absent or unusable; Lake Watch then says "No lake data in this build". */
export async function loadLakes(url: string): Promise<LakesFile | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const json: unknown = await res.json();
    return isLakesFile(json) ? json : null;
  } catch {
    return null;
  }
}

function rank(l: Lake): number {
  const i = STATUS_ORDER.indexOf(l.status.status);
  return i < 0 ? STATUS_ORDER.length : i;
}

/** Status order, then newest latest_date first. Control lakes go last. Returns a new array. */
export function sortLakes(lakes: Lake[]): Lake[] {
  return [...lakes].sort((a, b) => {
    const ca = a.role === "control" ? 1 : 0;
    const cb = b.role === "control" ? 1 : 0;
    if (ca !== cb) return ca - cb;
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    const da = a.status.latest_date ?? "";
    const db = b.status.latest_date ?? "";
    return da < db ? 1 : da > db ? -1 : 0;
  });
}

const km2 = (v: number) => v.toFixed(3);

/** One plain sentence for a lake's status. Never shows a zero area for a lake that was not measured. */
export function statusSentence(lake: Lake): string {
  const s = lake.status;
  const scope = lake.area_label.includes("search window") ? " in the search window" : "";
  const measured = s.change_km2 !== null && s.noise_km2 !== null && s.track !== null;
  if (!measured) {
    const latest = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
    return `${s.status}${scope}: ${s.reason}${latest}`;
  }
  const change = s.change_km2 as number;
  const sign = change > 0 ? "+" : change < 0 ? "-" : "";
  const when = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
  return `${s.status}: ${sign}${km2(Math.abs(change))} km²${scope} since earlier ${s.track} passes (noise ±${km2(s.noise_km2 as number)} km²), ${s.looks} looks${when}`;
}

/**
 * The lake the story shows in depth: among role "watch" lakes, the one with the most valid looks, ties going to the
 * newest latest look, and after that to file order. Chosen at runtime from the data, never named in the copy.
 */
export function featuredLake(file: LakesFile | null | undefined): Lake | null {
  let best: Lake | null = null;
  for (const l of file?.lakes ?? []) {
    if (l.role !== "watch") continue;
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

/** The headline count: valid looks in the cloud window, and how many lakes had at least one. */
export function cloudHeadline(file: LakesFile): string {
  const looks = file.lakes.reduce((n, l) => n + l.cloud_window_looks, 0);
  const watched = file.lakes.filter((l) => l.cloud_window_looks > 0).length;
  return `Between SUPARCO's 16 Jun image and its 5 Aug update, NISAR made ${looks} valid looks across ${watched} lakes.`;
}

/** The numbers and dates that copy quotes, taken from lakes.json so the words cannot drift from the data. */
export function lakeTokens(file: LakesFile): Record<string, string> {
  const c = file.constants;
  return {
    drop_db: String(c.drop_db),
    speckle_box: String(c.speckle_box),
    min_looks: String(c.min_looks),
    min_observable: String(c.min_observable),
    min_observable_pct: String(Math.round(c.min_observable * 100)),
    noise_floor_km2: String(c.noise_floor_km2),
    change_factor: String(c.change_factor),
    cloud_start: formatDate(file.cloud_window[0]),
    cloud_end: formatDate(file.cloud_window[1]),
    cloud_looks: String(file.lakes.reduce((n, l) => n + l.cloud_window_looks, 0)),
    cloud_lakes: String(file.lakes.filter((l) => l.cloud_window_looks > 0).length),
    lake_count: String(file.lakes.length),
    crid: file.crid,
    notes: file.notes,
  };
}
