import { formatDate } from "./format";

/** The alert levels a measured lake can have (pipeline: lakestatus.assess), highest first. */
export type LevelName = "Alert: growing" | "Watch" | "Decrease noted" | "No change";

export type LakeStatusName =
  | LevelName
  | "Not seen this pass"
  | "Not observable"
  | "Not measurable"
  | "Not yet validated against Sentinel-2"
  | "Not enough NISAR looks yet"
  | "No lake now"
  | "Lake may be forming"
  | "Frozen (likely)"
  | "Frozen (seen by Sentinel-2)"
  | "Break-up likely";

export const LEVELS: LevelName[] = ["Alert: growing", "Watch", "Decrease noted", "No change"];
export const ALERT: LevelName = "Alert: growing";

/**
 * The initial message a Watch, an Alert or a Decrease noted carries, written by the pipeline from the decision values
 * (lakestatus.level_message): what changed, how sure, what it is not, what to do. `text` joins them.
 */
export interface LevelMessage {
  level: LevelName;
  title: string;
  what: string;
  how_sure: string;
  not: string;
  do: string;
  /** Since when the level stands and the newest pass's z (and a newer pass that could not be read). */
  since?: string;
  text: string;
}

/** A pass that set the lake's level, with what it was measured against. */
export interface LevelPass {
  date: string;
  track: string;
  crid?: string | null;
  area_km2: number;
  baseline_km2: number;
  noise_km2: number;
  z: number;
  new_version?: boolean;
}

/** The freeze check's state (pipeline: sartale.freeze). Only frozen_likely, frozen_s2 and breakup_likely are statuses. */
export type FreezeState = "open" | "frozen_likely" | "frozen_s2" | "breakup_likely" | "not_assessed";

/**
 * Is the lake probably frozen? From NASA POWER daily air temperature moved to the lake's height, a clear Sentinel-2
 * scene of the last 7 days when one exists, and radar only at break-up. Absent in older builds and at sites with no lake
 * now.
 */
export interface LakeFreeze {
  state: FreezeState | string;
  /** When the current state began (freeze-up, break-up, release, or the Sentinel-2 scene); null when not known. */
  since: string | null;
  /** The newest day of NASA POWER air temperature used. */
  temp_through: string | null;
  checked?: string;
  cold_run_days: number | null;
  warm_run_days: number | null;
  fdd_since_sep: number | null;
  t2m_mean_7d: number | null;
  t2m_min_mean_7d?: number | null;
  /** The clearest Sentinel-2 scene of the last 7 days over the lake zone; null when none was clear or none was searched. */
  s2: { date: string; s2_id?: string; snow_share: number; water_share: number; clear_share?: number; target_clear_share?: number; water_over?: string } | null;
  /** The Sentinel-2 reading that set the current state (frozen_s2, or open by Sentinel-2); it holds until other evidence. */
  s2_evidence?: LakeFreeze["s2"];
  /** The freeze-up date, kept through break-up. */
  freeze_up?: string | null;
  /** What released an open lake this season, and when: radar back in its summer range, Sentinel-2 water, or (only for a lake without a radar summer level) the warm days. */
  released_by?: "radar" | "s2" | "air" | null;
  released_on?: string | null;
  /** Set when NASA POWER was stale or could not be read: the last check stands, from this date. */
  not_refreshed_since?: string | null;
  refresh_problem?: string | null;
  /** True when Sentinel-2 was searched (only for a cold or frozen lake). */
  s2_searched?: boolean;
  /** The radar pass that showed the ice-out signature, when break-up came from radar. */
  breakup_pass?: { date: string; track: string; contrast_hh_change_db: number; contrast_hv_change_db: number; core_dark_share: number; summer_core_dark_share: number } | null;
  /** How many passes were taken while the lake was frozen or breaking up. */
  frozen_passes?: number;
  reason: string;
}

/**
 * What recent imagery shows at a site: a lake, a dark area not confirmed as a lake, no lake now, or (at a site with no
 * lake) water in the latest Sentinel-2 check, so a lake may be forming. Absent in older builds: a lake.
 */
export type LakeState = "lake" | "unconfirmed" | "no_lake" | "lake_forming_check";

/**
 * The dated Sentinel-2 check of a site with no lake now: the newest scene whose lake zone was clear of cloud, snow and
 * ice, and how much of the zone held water.
 */
export interface AbsenceCheck {
  /** Date of the Sentinel-2 scene. */
  date: string;
  s2_id: string;
  /** Share of the lake zone's clear pixels that were water, 0 to 1. */
  water_share: number;
  water_km2: number;
  /** Share of the zone seen clear of cloud, shadow, snow and ice. */
  zone_valid_share: number;
  /** Share of the zone under snow or ice (absent in older builds). */
  snow_share?: number;
  /** The run that found the scene. */
  checked: string;
  /** The last run that searched (absent in older builds). */
  searched?: string;
  /** True when no clear, snow-free scene has come for over a week since `date` (absent in older builds). */
  no_view_since?: boolean;
  /** The site's state: two qualifying scenes at least 5 days apart above `threshold` set it (absent in older builds). */
  forming?: boolean;
  /** One scene on the other side of the threshold, waiting for a second before the state changes. */
  pending_scene?: { date: string; s2_id: string; water_share: number } | null;
  /** The two scenes that set the current state. */
  confirmed?: { date: string; s2_id: string; water_share: number }[] | null;
  /** The site's forming share the state was worked out with. */
  threshold?: number;
  rule?: string;
  /** Older builds only: the open-water season the check was limited to. */
  season?: string;
  source?: string;
}

/** A SUPARCO PDGL list entry matched to a lake. A "possible" match is never shown (suparcoLine). */
export interface SuparcoRef {
  id: number;
  match: "probable" | "possible" | "official";
  source: string;
}

/** The largest extent a lake is known to have had, and where that comes from. */
export interface LargestExtent {
  km2: number;
  source: string;
  year: number | null;
}

/** The picture files of one pass (paths under data/), null where a picture could not be drawn. */
export interface PassAssets {
  hh: string | null;
  water: string | null;
  valid: string | null;
}

/** The headline numbers of the overview (pipeline: lakesummary.headline_counts). */
export interface HeadlineCounts {
  watched: number;
  alert: number;
  watch: number;
  decrease: number;
  forming: number;
  needs_attention: number;
  open_water: number;
  frozen: number;
  no_lake: number;
  above_largest: number;
  suparco_listed: number;
  changed: number;
}

/** The radar grid a lake's pictures are drawn on. */
export interface LakeGrid {
  key: string;
  pixel_m: number;
  width: number;
  height: number;
  zone: string;
}

export interface LakeStatus {
  /** A level, or why there is none. Older builds (before the levels) used other words, shown as they are. */
  status: LakeStatusName | string;
  track: string | null;
  latest_date: string | null;
  looks: number;
  change_km2: number | null;
  noise_km2: number | null;
  reason: string;
  /** The lake's level when the status is one (absent in older builds; null otherwise). */
  level?: LevelName | null;
  /** The first pass of the current level. */
  level_since?: string | null;
  /** The passes that set the level: two for an Alert or a Decrease noted, one for a Watch. */
  level_passes?: LevelPass[];
  /** The CUSUM of the z values after the latest pass. */
  cusum?: { up: number; down: number } | null;
  /** The latest compared pass: z and the baseline it was measured against. */
  z?: number | null;
  baseline_km2?: number | null;
  /** Set when every track's latest pass is its first on a processing version its baseline lacks: no Alert until a second. */
  alerts_paused?: { crid: string | null; track: string; date: string; tracks?: string[] } | null;
  /** Set when the latest pass alone is its track's first on a new processing version: it cannot count toward an Alert. */
  first_on_version?: { crid: string | null; track: string; date: string } | null;
  /** A newer pass of some track that could not be read while a level stands (it never hides the level). */
  newest_unread?: { date: string; track: string; why: string } | null;
  message?: LevelMessage | null;
  /** The change a pass must pass to count: the change factor times the noise (absent before the overview build). */
  threshold_km2?: number | null;
  /** Whether the noise floor set the noise (null when the status did not come from a compared pass). */
  noise_floor_applied?: boolean | null;
  /** The pass_id of the status track's pass on the latest date. */
  latest_pass_id?: string | null;
}

export interface LakeSeriesPoint {
  date: string;
  track: string;
  area_km2: number | null;
  observable_share: number | null;
  excluded: string | null;
  /** NISAR processing version (composite release ID) of the pass, e.g. "P05036" (absent in older builds). */
  crid?: string;
  /**
   * For a pass left out of the trend: the area it read, so the chart can mark it (area_km2 is null for such a pass).
   * Null when the pass had no valid pixel in the zone; absent on passes that were used and in older builds.
   */
  diagnostic_km2?: number | null;
  /** Taken while the lake was probably frozen or breaking up: its area is kept but enters no comparison (absent in older builds). */
  frozen?: boolean;
  /** The pass against its own track: (area − baseline) / noise; null until the track has enough earlier passes. */
  z?: number | null;
  baseline_km2?: number | null;
  noise_km2?: number | null;
  /** The level this pass set (absent in older builds; null when it set none). */
  level_contrib?: LevelName | null;
  /** A track's first pass on a processing version its baseline lacks: it can make a Watch, not an Alert. */
  new_version?: boolean;
  /** One of a track's first passes after the lake opened: it only rebuilds the baseline. */
  after_open?: boolean;
  /** Stable id of the pass, e.g. "2026-11-09_055A_P05036" (absent before the overview build). */
  pass_id?: string;
  /** The pass's pictures (absent when none were drawn). */
  assets?: PassAssets;
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
  /** For a site with no lake now: the last Sentinel-2 check (absent in older builds; null before the first check). */
  absence_checked?: AbsenceCheck | null;
  /** The lake's freeze check (absent in older builds and at sites with no lake now). */
  freeze?: LakeFreeze | null;
  /**
   * While the lake is frozen (or its pictured pass was taken while it was): its latest open-water pass on the status
   * track, with the assessment it had then and its own pictures (null when they could not be drawn). Absent otherwise.
   */
  last_open?: {
    date: string; track: string; crid?: string | null; area_km2: number; status: string; change_km2: number | null;
    noise_km2: number | null; looks: number; ref_km2?: number | null;
    images: { latest_hh: string | null; water: string | null; date?: string; track?: string } | null;
  } | null;
  /** The Sentinel-2 check the level rests on (lakes-check): under IoU 0.4 the lake is "Not measurable". */
  validation?: { iou: number; nisar_date?: string | null; s2_date?: string | null; s2_id?: string | null } | null;
  /** Height of the lake surface in metres, and where it comes from (absent in older builds). */
  elevation_m?: number | null;
  elevation_source?: string | null;
  downstream: string | null;
  downstream_source: string | null;
  /** The district, the province and the SUPARCO PDGL match (absent before the overview build; null where unknown). */
  district?: string | null;
  district_source?: string | null;
  province?: "GB" | "KP" | null;
  suparco?: SuparcoRef | null;
  largest_extent?: LargestExtent | null;
  /** The lake's radar area now as a share of its largest extent; null with `share_note` saying why. */
  share_of_largest?: number | null;
  above_largest?: boolean | null;
  share_note?: string | null;
  /** The status the previous build gave the lake. */
  previous_status?: string | null;
  grid?: LakeGrid | null;
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
 * True for a pass the trend may use: not left out, has an area, saw at least `minObservable` of the lake zone, and was
 * not taken while the lake was probably frozen. The pipeline's status uses the same rule (lakestatus.is_valid).
 */
export function isTrendPass(p: Lake["series"][number], minObservable: number): boolean {
  return p.excluded === null && p.area_km2 !== null && p.observable_share !== null && p.observable_share >= minObservable && !p.frozen;
}

/** The statuses that mean the lake is probably under ice (frozen or breaking up): no growing or shrinking verdict. */
export const FROZEN_STATUSES: LakeStatusName[] = ["Frozen (likely)", "Frozen (seen by Sentinel-2)", "Break-up likely"];

/** True when the lake's status is one of the frozen statuses. */
export function isFrozen(l: Lake): boolean {
  return FROZEN_STATUSES.includes(l.status.status as LakeStatusName);
}

/** True when the lake's pictured pass was taken while the lake was probably frozen (its water layer is then hidden). */
export function picturedPassFrozen(l: Lake): boolean {
  const im = l.images;
  if (!im?.date) return false;
  return l.series.some((p) => !!p.frozen && p.date === im.date && p.track === im.track);
}

/** What a radar area of a frozen lake is not (shown greyed beside it). */
export const FROZEN_AREA = "not an open-water measurement while frozen";

const pct = (v: number): string => `${Math.round(v * 100)}%`;
const degrees = (v: number): string => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)} °C`;

/**
 * How an open lake was released this season, as the pipeline's freeze.open_headline words it: never open water from
 * air temperature alone. Null when it never froze this season.
 */
export function openHeadline(f: LakeFreeze): string | null {
  const on = f.released_on ? formatDate(f.released_on) : null;
  if (!on) return null;
  if (f.released_by === "s2") return `Open water seen by Sentinel-2 on ${on}`;
  if (f.released_by === "radar") return `Radar back within its summer range on ${on}`;
  if (f.released_by === "air") return `No freeze signal in air temperature since ${on}. Open water not confirmed by radar or Sentinel-2`;
  return null;
}

/** The freeze state in a few words, for the freeze card's first line and the brief. */
export function freezeHeadline(f: LakeFreeze): string {
  const since = f.since ? ` since ${formatDate(f.since)}` : "";
  switch (f.state) {
    case "frozen_likely":
      return `Probably frozen${since} (air temperature)`;
    case "frozen_s2":
      return `Frozen${since}: snow or ice seen by Sentinel-2`;
    case "breakup_likely":
      return `Ice probably breaking up${since}`;
    case "not_assessed":
      return "Freeze not assessed";
    case "open":
      return openHeadline(f) ?? "Not frozen by the air-temperature rule";
    default:
      return `Freeze state: ${f.state}`;
  }
}

type S2Reading = NonNullable<LakeFreeze["s2"]>;

/** "snow or ice on 94% and water on 0% of the lake outline seen clear": both over the lake itself (older files: the zone). */
function s2Shares(s: S2Reading): string {
  return `snow or ice on ${pct(s.snow_share)} and water on ${pct(s.water_share)} of the ${s.water_over ?? "lake zone"} seen clear`;
}

/**
 * The freeze card's facts, one line each: the air-temperature run and its freezing degree-days, this week's Sentinel-2
 * view (or "none clear") and the last Sentinel-2 evidence when older, the radar pass at break-up, how many passes were
 * taken while frozen, and when the check could not be refreshed. Never claims the radar saw ice, or that the lake is
 * open from air temperature alone.
 */
export function freezeFacts(l: Lake): string[] {
  const f = l.freeze;
  if (!f) return [];
  const out: string[] = [];
  if (f.temp_through && f.state !== "not_assessed") {
    const height = l.elevation_m != null ? `, adjusted to the lake's height of ${Math.round(l.elevation_m).toLocaleString("en-GB")} m` : "";
    const run = f.cold_run_days ? `below 0 °C for ${f.cold_run_days} ${f.cold_run_days === 1 ? "day" : "days"} in a row`
      : f.warm_run_days ? `above 0 °C for ${f.warm_run_days} ${f.warm_run_days === 1 ? "day" : "days"} in a row`
      : "at 0 °C or without a value on the newest day";
    const mean = f.t2m_mean_7d != null ? `; 7-day mean ${degrees(f.t2m_mean_7d)}` : "";
    out.push(`Air temperature (NASA POWER to ${formatDate(f.temp_through)}${height}): daily mean ${run}${mean}.`);
    if (f.fdd_since_sep != null) out.push(`Freezing degree-days since 1 Sep: ${Math.round(f.fdd_since_sep)}.`);
  }
  if (f.s2) {
    out.push(`Sentinel-2 ${formatDate(f.s2.date)}${f.s2.s2_id ? ` (${f.s2.s2_id})` : ""}: ${s2Shares(f.s2)}.`);
  } else if (f.s2_searched) {
    out.push("Sentinel-2: none clear over the lake in the last 7 days.");
  } else if (f.state !== "not_assessed") {
    out.push("Sentinel-2: not checked (the lake is not cold).");
  }
  const ev = f.s2_evidence;
  if (ev && (!f.s2 || f.s2.date !== ev.date)) {
    out.push(`Last Sentinel-2 evidence, which still holds: ${formatDate(ev.date)}${ev.s2_id ? ` (${ev.s2_id})` : ""}, ${s2Shares(ev)}.`);
  }
  const b = f.breakup_pass;
  if (b) out.push(`Radar ${formatDate(b.date)} (${b.track}): lake core ${b.contrast_hh_change_db >= 0 ? "+" : ""}${b.contrast_hh_change_db.toFixed(1)} dB (HH) and ${b.contrast_hv_change_db >= 0 ? "+" : ""}${b.contrast_hv_change_db.toFixed(1)} dB (HV) against its summer level; ${pct(b.core_dark_share)} of it dark (summer ${pct(b.summer_core_dark_share)}).`);
  const n = f.frozen_passes ?? l.series.filter((p) => p.frozen).length;
  if (n) out.push(`${n} ${n === 1 ? "pass was" : "passes were"} taken while the lake was probably frozen: greyed below, ${FROZEN_AREA}, and left out of the comparison.`);
  if (f.not_refreshed_since) out.push(`Not refreshed since ${formatDate(f.not_refreshed_since)}${f.refresh_problem ? `: ${f.refresh_problem}` : ""}; the last check stands.`);
  return out;
}

/** The newest pass with an area reading (frozen or not), or null. */
export function latestReading(l: Lake): LakeSeriesPoint | null {
  const read = l.series.filter((p) => p.area_km2 !== null).sort((a, b) => a.date.localeCompare(b.date) || a.track.localeCompare(b.track));
  return read.length ? read[read.length - 1] : null;
}

/** "Latest reading 0.225 km² on 30 Oct 2026 (084A): not an open-water measurement while frozen.", or null. */
export function frozenAreaLine(l: Lake): string | null {
  if (!isFrozen(l)) return null;
  const p = latestReading(l);
  if (!p) return null;
  return `Latest reading ${(p.area_km2 as number).toFixed(3)} km² on ${formatDate(p.date)} (${p.track}): ${FROZEN_AREA}.`;
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
  /** The water method and level rule that made the numbers, e.g. id "D17" (absent in older builds). */
  method?: { id: string; water?: string; [k: string]: unknown };
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
    /** The level rule (absent in older builds). */
    lee_box?: number;
    baseline_passes?: number;
    noise_passes?: number;
    noise_rel_floor?: number;
    cusum_k?: number;
    cusum_h?: number;
    after_open_passes?: number;
    min_validation_iou?: number;
    /** The freeze rule (absent in older builds). */
    lapse_c_per_km?: number;
    freeze_cold_run_days?: number;
    freeze_fdd?: number;
    breakup_warm_run_days?: number;
    thaw_warm_run_days?: number;
    breakup_contrast_db?: number;
    breakup_dark_drop?: number;
    s2_frozen_snow_share?: number;
    s2_open_water_share?: number;
    s2_freeze_days?: number;
    s2_freeze_clear?: number;
    power_stale_days?: number;
  };
  lakes: Lake[];
  checks: LakeCheck[];
  /** Check rows without measurements; filled by splitChecks. */
  check_notes?: LakeCheckNote[];
  /** Names of the sites the file lists but this version of the page cannot show; filled by keepValidLakes. */
  dropped_lakes?: string[];
  /** The overview's numbers, from the newest build (absent before the overview build). */
  counts?: HeadlineCounts;
  /** Date of the newest pass of any lake. */
  newest_pass?: string | null;
  /** What the previous build said, to show what changed. */
  previous_build?: { built: string | null; counts: HeadlineCounts; statuses: Record<string, string | null> } | null;
  /** Lakes in the mapped inventory. */
  mapped_count?: number | null;
}

export const STATUS_ORDER: LakeStatusName[] = [
  "Alert: growing",
  "Lake may be forming",
  "Watch",
  "Decrease noted",
  "Frozen (likely)",
  "Frozen (seen by Sentinel-2)",
  "Break-up likely",
  "Not seen this pass",
  "No change",
  "Not enough NISAR looks yet",
  "Not measurable",
  "Not yet validated against Sentinel-2",
  "Not observable",
  "No lake now",
];

/** True when the lake's status is a level (Alert: growing, Watch, Decrease noted, No change). */
export function hasLevel(l: Lake): boolean {
  return (LEVELS as string[]).includes(l.status.status);
}

/** True when the lake is at "Alert: growing". */
export function isAlert(l: Lake): boolean {
  return l.status.status === ALERT;
}

/** The lakes at "Alert: growing", for the banner. */
export function alertLakes(file: LakesFile | null | undefined): Lake[] {
  return (file?.lakes ?? []).filter(isAlert);
}

/** The initial message of a Watch, an Alert or a Decrease noted, or null (older builds, other statuses). */
export function levelMessage(l: Lake): LevelMessage | null {
  const m = l.status.message;
  return hasLevel(l) && m && m.level === l.status.status ? m : null;
}

/** The site's lake state, "lake" for builds made before the field existed. */
export function lakeState(l: Lake): LakeState {
  return l.lake_state ?? "lake";
}

/**
 * True for a site that holds a lake now (confirmed or not). False for an empty basin kept to watch for a lake forming,
 * and for one where Sentinel-2 has just shown water: that may be a lake forming, but it is not a measured lake until
 * the SARtale team reviews the site and adds it.
 */
export function hasLakeNow(l: Lake): boolean {
  const s = lakeState(l);
  return s !== "no_lake" && s !== "lake_forming_check";
}

/** True for a site with no lake now where the latest Sentinel-2 check found water. */
export function mayBeForming(l: Lake): boolean {
  return lakeState(l) === "lake_forming_check";
}

/**
 * "Last checked 17 Aug 2026 with Sentinel-2 (scene): water on 0.04% of the lake zone.", or null without a check. When no
 * clear, snow-free scene has come since, it says so (the pipeline's lakestatus.absence_sentence, word for word).
 */
export function absenceLine(l: Lake): string | null {
  const a = l.absence_checked;
  if (!a) return null;
  const pct = a.water_share * 100;
  const shown = pct === 0 ? "0%" : pct < 1 ? `${pct.toFixed(2)}%` : `${pct.toFixed(1)}%`;
  const searched = a.searched ?? a.checked;
  const since = a.no_view_since
    ? `; no clear, snow-free Sentinel-2 view of the zone since${searched ? ` (searched to ${formatDate(searched)})` : ""}`
    : "";
  return `Last checked ${formatDate(a.date)} with Sentinel-2 (${a.s2_id}): water on ${shown} of the lake zone${since}.`;
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

/**
 * "7 lakes", or "5 lakes and 2 sites with no lake now" when the list keeps empty basins, with "1 site where a lake may
 * be forming" when a check found water at one.
 */
export function watchList(file: LakesFile): string {
  const lakes = lakesNow(file).length;
  const forming = file.lakes.filter(mayBeForming).length;
  const empty = file.lakes.length - lakes - forming;
  const sites = (n: number) => `${n} ${n === 1 ? "site" : "sites"}`;
  const parts = [`${lakes} ${lakes === 1 ? "lake" : "lakes"}`];
  if (empty) parts.push(`${sites(empty)} with no lake now`);
  if (forming) parts.push(`${sites(forming)} where a lake may be forming`);
  return parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isNumOrNull = (v: unknown): boolean => v === null || isNum(v);
const isStrOrNull = (v: unknown): boolean => v === null || isStr(v);
const isIso = (v: unknown): boolean => isStr(v) && /^\d{4}-\d{2}-\d{2}$/.test(v);

function isPoint(p: unknown): boolean {
  return isObj(p) && isIso(p.date) && isStr(p.track) && isNumOrNull(p.area_km2)
    && (p.observable_share === null || isNum(p.observable_share)) && isStrOrNull(p.excluded)
    && (p.diagnostic_km2 === undefined || isNumOrNull(p.diagnostic_km2))
    && (p.frozen === undefined || typeof p.frozen === "boolean")
    && ["z", "baseline_km2", "noise_km2"].every((k) => p[k] === undefined || isNumOrNull(p[k]));
}

/** A freeze object the card can read: a state and a reason, numbers or null where it shows them. Absent or null is fine. */
function isFreeze(f: unknown): boolean {
  if (f === undefined || f === null) return true;
  if (!isObj(f)) return false;
  const s2 = f.s2;
  return isStr(f.state) && isStr(f.reason) && (f.since === null || f.since === undefined || isIso(f.since))
    && (f.temp_through === null || f.temp_through === undefined || isIso(f.temp_through))
    && ["cold_run_days", "warm_run_days", "fdd_since_sep", "t2m_mean_7d"].every((k) => f[k] === undefined || isNumOrNull(f[k]))
    && isS2(s2) && isS2(f.s2_evidence) && (f.released_on === undefined || f.released_on === null || isIso(f.released_on))
    && (f.not_refreshed_since === undefined || f.not_refreshed_since === null || isIso(f.not_refreshed_since))
    && isBreakupPass(f.breakup_pass);
}

/** The last open-water pass the story page shows while a lake is frozen: absent, null, or with the numbers it draws. */
function isLastOpen(v: unknown): boolean {
  if (v === undefined || v === null) return true;
  if (!isObj(v)) return false;
  const im = v.images;
  return isIso(v.date) && isStr(v.track) && isNum(v.area_km2) && isStr(v.status) && isNumOrNull(v.noise_km2)
    && (im === null || im === undefined || (isObj(im) && isStrOrNull(im.latest_hh ?? null) && isStrOrNull(im.water ?? null)));
}

function isS2(s2: unknown): boolean {
  return s2 === null || s2 === undefined || (isObj(s2) && isIso(s2.date) && isNum(s2.snow_share) && isNum(s2.water_share));
}

/** The radar pass at break-up, which the card writes out with its numbers: an object with them, or nothing. */
function isBreakupPass(b: unknown): boolean {
  return b === null || b === undefined || (isObj(b) && isIso(b.date) && isStr(b.track)
    && ["contrast_hh_change_db", "contrast_hv_change_db", "core_dark_share", "summer_core_dark_share"].every((k) => isNum(b[k])));
}

/** A message the views can print: every part a string. Absent or null is fine. */
function isMessage(m: unknown): boolean {
  if (m === undefined || m === null) return true;
  return isObj(m) && ["level", "title", "what", "how_sure", "not", "do", "text"].every((k) => isStr(m[k]));
}

/**
 * A status the views can show: one this page knows, or, from an older build made before the levels (no `level` key),
 * any status text, shown as it is.
 */
function isStatus(s: unknown): boolean {
  if (!isObj(s)) return false;
  const known = STATUS_ORDER.includes(s.status as LakeStatusName);
  const older = !("level" in s) && isStr(s.status) && s.status.length > 0;
  return (known || older) && isStrOrNull(s.track)
    && (s.latest_date === null || isIso(s.latest_date)) && isNum(s.looks) && isNumOrNull(s.change_km2)
    && isNumOrNull(s.noise_km2) && isStr(s.reason) && isMessage(s.message)
    && (s.level_passes === undefined || (Array.isArray(s.level_passes) && s.level_passes.every((p) => isObj(p) && isIso(p.date) && isStr(p.track) && isNum(p.z))));
}

/** True for a lake entry with every field the views read (and a status this version of the page knows). */
export function isLake(l: unknown): boolean {
  if (!isObj(l)) return false;
  const images = l.images;
  const bounds = l.bounds;
  return isStr(l.id) && isStr(l.name) && isNum(l.lon) && isNum(l.lat) && ["watch", "control", "story"].includes(l.role as string)
    && isStr(l.coord_source) && isStr(l.area_label) && isStatus(l.status) && isNum(l.cloud_window_looks)
    && Array.isArray(l.directions) && Array.isArray(l.limits) && l.limits.every(isStr)
    && Array.isArray(l.series) && l.series.every(isPoint)
    && Array.isArray(l.excluded) && l.excluded.every((x) => isObj(x) && isStr(x.pass) && isStr(x.reason))
    && isFreeze(l.freeze) && isLastOpen(l.last_open)
    && (images === null || (isObj(images) && isStrOrNull(images.latest_hh ?? null) && isStrOrNull(images.water ?? null)))
    && (bounds === null || (Array.isArray(bounds) && bounds.length === 4 && bounds.every(isNum)));
}

/**
 * True when `v` has the file-level parts of lakes.json the views read, with finite numbers where they compute: version,
 * build time, notes, processing versions, cloud window, the method constants, and a list of lakes and of checks. A file
 * without them takes the "no lake data" path instead of breaking the whole page while it draws. Each lake is checked on
 * its own (`keepValidLakes`), so one entry this page cannot read (say a status from a newer pipeline) drops that lake
 * only.
 */
export function isLakesFile(v: unknown): v is LakesFile {
  if (!isObj(v)) return false;
  const c = v.constants;
  const w = v.cloud_window;
  return isNum(v.version) && isStr(v.built) && isStr(v.notes) && isStr(v.crid)
    && Array.isArray(w) && w.length === 2 && w.every(isIso)
    && isObj(c) && ["drop_db", "min_looks", "min_observable", "noise_floor_km2", "change_factor", "speckle_box"].every((k) => isNum(c[k]))
    && Array.isArray(v.lakes) && Array.isArray(v.checks);
}

const isSuparco = (v: unknown): boolean => isObj(v) && isNum(v.id) && ["probable", "possible", "official"].includes(v.match as string) && isStr(v.source);
const isExtent = (v: unknown): boolean => isObj(v) && isNum(v.km2) && isStr(v.source) && isNumOrNull(v.year);
const isAssets = (v: unknown): boolean => isObj(v) && ["hh", "water", "valid"].every((k) => isStrOrNull(v[k]));
const isGrid = (v: unknown): boolean => isObj(v) && isStr(v.key) && isStr(v.zone) && ["pixel_m", "width", "height"].every((k) => isNum(v[k]));

/**
 * The lake with each malformed optional field of the overview build set to null (a series point's malformed `assets`
 * or `pass_id` is removed), so one bad field costs only itself and never the lake.
 */
export function degradeLake(l: Lake): Lake {
  const o = l as unknown as Record<string, unknown>;
  const out: Record<string, unknown> = { ...o };
  const nullIfBad = (k: string, ok: (v: unknown) => boolean) => {
    if (o[k] !== undefined && o[k] !== null && !ok(o[k])) out[k] = null;
  };
  nullIfBad("suparco", isSuparco);
  nullIfBad("largest_extent", isExtent);
  nullIfBad("grid", isGrid);
  nullIfBad("district", isStr);
  nullIfBad("province", (v) => v === "GB" || v === "KP");
  nullIfBad("share_of_largest", isNum);
  nullIfBad("above_largest", (v) => typeof v === "boolean");
  nullIfBad("share_note", isStr);
  nullIfBad("previous_status", isStr);
  out.series = l.series.map((p) => {
    const r = { ...(p as unknown as Record<string, unknown>) };
    if (r.assets !== undefined && !isAssets(r.assets)) delete r.assets;
    if (r.pass_id !== undefined && !isStr(r.pass_id)) delete r.pass_id;
    return r;
  });
  return out as unknown as Lake;
}

/** The SUPARCO line of a lake: a "possible" match is never shown. */
export function suparcoLine(l: Lake): string {
  const s = l.suparco;
  if (!s || s.match === "possible") return "Not matched to a SUPARCO PDGL ID";
  return s.match === "probable" ? `SUPARCO PDGL ${s.id} (probable match)` : `SUPARCO PDGL ${s.id}`;
}

/** Keeps the lakes the views can draw and lists the others by name (or id) in `dropped_lakes`. */
export function keepValidLakes(f: LakesFile): LakesFile {
  const all = f.lakes as unknown[];
  const kept = (all.filter(isLake) as Lake[]).map(degradeLake);
  const dropped = all
    .filter((l) => !isLake(l))
    .map((l, i) => {
      const o = isObj(l) ? l : {};
      return isStr(o.name) ? o.name : isStr(o.id) ? o.id : `entry ${i + 1}`;
    });
  return dropped.length ? { ...f, lakes: kept, dropped_lakes: dropped } : { ...f, lakes: kept };
}

/** "1 site in the data could not be shown ...", or null when nothing was dropped. */
export function droppedLine(f: LakesFile): string | null {
  const n = f.dropped_lakes?.length ?? 0;
  if (!n) return null;
  const which = f.dropped_lakes!.join(", ");
  return `${n} ${n === 1 ? "site" : "sites"} in the data (${which}) could not be shown by this version of the page. Reload the page to see ${n === 1 ? "it" : "them"}.`;
}

/**
 * Loads data/lakes.json. Returns null if it is absent, unusable or slower than `timeoutMs`; Lake Watch then says "No
 * lake data in this build". `no-cache` makes the browser check with the server every time (a cheap ETag check), so a
 * weekly data update shows up on the next load instead of after the browser's cache runs out.
 */
export async function loadLakes(url: string, fetchFn: typeof fetch = (...a) => fetch(...a), timeoutMs = 20_000): Promise<LakesFile | null> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetchFn(url, { cache: "no-cache", signal: ctl.signal });
    if (!res.ok) return null;
    const json: unknown = await res.json();
    return isLakesFile(json) ? splitChecks(keepValidLakes(json)) : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Where a status from an older build (before the levels) sorts: with the level it is closest to. */
const OLDER_RANK: Record<string, LakeStatusName> = { Growing: "Watch", Shrinking: "Watch", Stable: "No change" };

function rank(l: Lake): number {
  const st = l.status.status;
  const i = STATUS_ORDER.indexOf((OLDER_RANK[st] ?? st) as LakeStatusName);
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

/** "+0.012" / "−0.012" (a true minus), rounded first so a change that rounds to zero has no sign. */
function signed(v: number, digits = 3): string {
  const shown = Math.abs(v).toFixed(digits);
  return Number(shown) === 0 ? shown : `${v > 0 ? "+" : "−"}${shown}`;
}

/**
 * One plain sentence for a lake's status. Never shows a zero area for a lake that was not measured. `changeFactor` is
 * lakes.json constants.change_factor. A level says how the latest pass compares with its own track's baseline; a
 * status from an older build (before the levels) keeps its old wording.
 */
export function statusSentence(lake: Lake, changeFactor: number): string {
  const s = lake.status;
  const measured = s.change_km2 !== null && s.noise_km2 !== null && s.track !== null;
  if (!measured) {
    const latest = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
    return `${s.status}: ${s.reason}${latest}`;
  }
  const scope = lake.area_label.includes("search window") ? " in the search window" : "";
  const when = s.latest_date ? `, latest ${formatDate(s.latest_date)}` : "";
  const change = s.change_km2 as number;
  const noise = s.noise_km2 as number;
  if (hasLevel(lake) && typeof s.z === "number" && typeof s.baseline_km2 === "number") {
    const pct = s.baseline_km2 ? Math.round((100 * change) / s.baseline_km2) : 0;
    const pctText = pct === 0 ? "0%" : `${pct > 0 ? "+" : "−"}${Math.abs(pct)}%`;
    const since = s.level_since && s.level_since !== s.latest_date ? `; since ${formatDate(s.level_since)}` : "";
    const paused = s.alerts_paused
      ? `; Alerts paused: every track's latest pass is its first on a new processing version`
      : s.first_on_version
        ? `; this pass is track ${s.first_on_version.track}'s first on processing version ${s.first_on_version.crid ?? "new"}: it cannot count toward an Alert (other tracks can)`
        : "";
    return `${s.status}: ${signed(change)} km² (${pctText})${scope} against the baseline of earlier ${s.track} passes, z = ${signed(s.z, 1)} (noise ±${km2(noise)} km²; a level needs ${changeFactor}× noise), ${s.looks} looks${when}${since}${paused}`;
  }
  return `${s.status}: ${signed(change)} km²${scope} since earlier ${s.track} passes (noise ±${km2(noise)} km²; change must exceed ${changeFactor}× noise), ${s.looks} looks${when}`;
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
  return `From ${dayMonth(file.cloud_window[0])} to ${dayMonth(file.cloud_window[1])}, NISAR made ${looks} valid looks across ${watched} lakes. SUPARCO's updates reported that cloud limited optical imagery in these weeks.`;
}

export const NOT_VALIDATED = "Not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.";

/**
 * What the levels cannot do, shown with every lake (method study of 11 Nov 2026). Older builds without levels show
 * none of these.
 */
export const LEVEL_LIMITS = [
  "A lake drawing down onto wet sediment is nearly invisible to the radar. Radar sees about a tenth to a fifth of such a decrease.",
  "An Alert comes 5–12 days after a change begins in Hunza (three tracks) and 8–12 days in Chitral (two tracks).",
  "This is slow-growth monitoring, not outburst warning: an outburst takes hours.",
  "False-alarm and miss rates are modelled from one season's pass-to-pass noise, not observed. No lake grew in the 2026 data. They will be estimated again after one more season.",
  "Lakes below about 0.05 km² are limited by speckle.",
];

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
  return `In ${when} against Sentinel-2, radar water ${how}. Treat areas as indicative.`;
}

/**
 * The method's standing limits, shown for every lake whatever its own `limits` say: the build notes, what was not
 * validated, and how the Sentinel-2 cross-check went.
 */
export function methodLimits(file: LakesFile): string[] {
  const out = [file.notes, NOT_VALIDATED];
  const optical = opticalCheckSentence(file.checks);
  if (optical) out.push(optical);
  if (file.method) out.push(...LEVEL_LIMITS);
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
    ...freezeTokens(c),
    ...levelTokens(file),
  };
}

/** The level rule's numbers, from lakes.json; none when an older build lacks them (its sentences are then left out). */
function levelTokens(file: LakesFile): Record<string, string> {
  const c = file.constants;
  const need = [c.lee_box, c.baseline_passes, c.noise_passes, c.noise_rel_floor, c.cusum_k, c.cusum_h, c.after_open_passes, c.min_validation_iou];
  if (!file.method || !need.every((v) => typeof v === "number")) return {};
  return {
    method_id: file.method.id,
    lee_box: String(c.lee_box),
    baseline_passes: String(c.baseline_passes),
    noise_passes: String(c.noise_passes),
    noise_rel_floor_pct: String(Math.round(c.noise_rel_floor! * 100)),
    cusum_k: String(c.cusum_k),
    cusum_h: String(c.cusum_h),
    after_open_passes: String(c.after_open_passes),
    min_validation_iou: String(c.min_validation_iou),
  };
}

/** The freeze rule's numbers, from lakes.json constants; none when an older build lacks them (its sentences are then left out). */
function freezeTokens(c: LakesFile["constants"]): Record<string, string> {
  const need = [c.lapse_c_per_km, c.freeze_cold_run_days, c.freeze_fdd, c.breakup_warm_run_days, c.thaw_warm_run_days,
    c.breakup_contrast_db, c.breakup_dark_drop, c.s2_frozen_snow_share, c.s2_open_water_share, c.s2_freeze_days,
    c.s2_freeze_clear, c.power_stale_days];
  if (!need.every((v) => typeof v === "number")) return {};
  return {
    lapse_c_per_km: String(Math.abs(c.lapse_c_per_km!)),
    freeze_cold_run_days: String(c.freeze_cold_run_days),
    freeze_fdd: String(c.freeze_fdd),
    breakup_warm_run_days: String(c.breakup_warm_run_days),
    thaw_warm_run_days: String(c.thaw_warm_run_days),
    breakup_contrast_db: String(c.breakup_contrast_db),
    breakup_dark_drop: String(c.breakup_dark_drop),
    s2_frozen_pct: String(Math.round(c.s2_frozen_snow_share! * 100)),
    s2_open_pct: String(Math.round(c.s2_open_water_share! * 100)),
    s2_freeze_days: String(c.s2_freeze_days),
    s2_freeze_clear_pct: String(Math.round(c.s2_freeze_clear! * 100)),
    power_stale_days: String(c.power_stale_days),
  };
}
