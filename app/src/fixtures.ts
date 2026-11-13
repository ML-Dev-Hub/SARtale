import type { Lake, LakesFile, LakeStatus, LakeStatusName, LevelMessage, LevelName } from "./lakes";

const LEVEL_NAMES: string[] = ["Alert: growing", "Watch", "Decrease noted", "No change"];

/** The message the pipeline writes for a level (lakestatus.level_message), in the fixture's own numbers. */
export function fixtureMessage(level: LevelName, name: string): LevelMessage {
  const title = level === "Alert: growing" ? `Alert: growing. The radar water area of ${name} rose on two passes in a row.`
    : level === "Decrease noted" ? `Decrease noted. The radar water area of ${name} fell on two passes in a row.`
    : `Watch: one radar pass of ${name} is beyond 2× noise.`;
  const m = {
    level,
    title,
    what: `Radar water area of ${name}: 0.161 km² on 23 Oct 2026 (156A), +0.031 km² (+24%) against its baseline of 0.130 km² from earlier 156A passes.`,
    how_sure: level === "Watch" ? "One pass only (z = +2.4, noise ±0.013 km²), so it is not confirmed; the next pass shows whether it holds."
      : "Two passes in a row beyond 2× their track's noise: z = +2.2 and +2.4 (noise ±0.013 and ±0.013 km²).",
    not: level === "Decrease noted"
      ? "Information only, not an Alert: the radar sees a drawdown onto wet sediment at only about a tenth to a fifth of its size, so the real change can be much larger. Check optical imagery. This is not an outburst forecast. Radar sees a lake drawing down onto wet sediment poorly, and a change shows here 5–12 days after it begins."
      : "This is not an outburst forecast. Radar sees a lake drawing down onto wet sediment poorly, and a change shows here 5–12 days after it begins.",
    since: `${level} since 23 Oct 2026; the newest pass, 23 Oct 2026 (156A), reads z = +2.4.`,
    do: "Check recent optical imagery (Sentinel-2 or Landsat) or the site. Contact GBDMA or PDMA. Official warnings come from PMD, NDMA, GBDMA and PDMA.",
    text: "",
  };
  m.text = [m.title, m.what, m.how_sure, m.since, m.not, m.do].join(" ");
  return m;
}

function fixtureLake(id: string, status: LakeStatusName, latest: string | null, extra: Partial<Lake> = {}): Lake {
  const measured = LEVEL_NAMES.includes(status);
  const level = measured ? (status as LevelName) : null;
  const change = status === "Alert: growing" || status === "Watch" ? 0.031 : status === "Decrease noted" ? -0.04 : measured ? 0.001 : null;
  const levelFields: Partial<LakeStatus> = {
    level,
    level_since: level ? latest : null,
    level_passes: level && level !== "No change"
      ? [{ date: latest ?? "2026-10-23", track: "156A", area_km2: 0.161, baseline_km2: 0.13, noise_km2: 0.013, z: 2.4 }]
      : [],
    cusum: level ? { up: 0.4, down: 0 } : null,
    z: level ? (change as number) / 0.013 : null,
    baseline_km2: level ? 0.13 : null,
    alerts_paused: null,
    message: level && level !== "No change" ? fixtureMessage(level, `Fixture ${id}`) : null,
  };
  return {
    id,
    name: `Fixture ${id}`,
    lon: 74.5,
    lat: 36.5,
    role: "watch",
    coord_source: "fixture",
    outline_source: null,
    area_label: "water area in the search window",
    downstream: null,
    downstream_source: null,
    status: {
      status,
      track: measured ? "156A" : null,
      latest_date: latest,
      looks: measured ? 9 : 2,
      change_km2: change,
      noise_km2: measured ? 0.013 : null,
      reason: `Fixture reason for ${id}.`,
      ...levelFields,
    },
    cloud_window_looks: 7,
    directions: ["A"],
    limits: [],
    series: [],
    excluded: [],
    images: null,
    bounds: null,
    ...extra,
  };
}

/** Test fixture only: one lake per status (an Alert, a Watch, a Decrease noted, No change and the statuses without a level), and a control. */
export const fixtureLakes: LakesFile = {
  version: 1,
  built: "2026-11-02T00:00:00Z",
  notes: "fixture",
  crid: "P05023",
  cloud_window: ["2026-06-17", "2026-08-04"],
  constants: { drop_db: 3, min_looks: 3, min_observable: 0.5, noise_floor_km2: 0.005, change_factor: 2, speckle_box: 3, outlier_z: 3.5 },
  method: { id: "D17", water: "valid and HH at least 3 dB below the window-median HH" },
  lakes: [
    fixtureLake("control", "Not seen this pass", "2026-10-30", { role: "control" }),
    fixtureLake("hidden", "Not observable", null),
    fixtureLake("stable", "No change", "2026-10-23"),
    fixtureLake("grow-old", "Watch", "2026-10-11"),
    fixtureLake("few", "Not enough NISAR looks yet", "2026-10-23"),
    fixtureLake("shrink", "Decrease noted", "2026-10-23"),
    fixtureLake("grow-new", "Alert: growing", "2026-10-23", { area_label: "water area inside the outline" }),
  ],
  checks: [],
};

/**
 * A lakes.json made before the levels (Step 2b): no `method`, statuses "Stable" and "Growing" without level fields.
 * Built from the fixture by taking the new fields away.
 */
export function olderFile(): LakesFile {
  const old = (l: Lake, status: string): Lake => {
    const { level: _l, level_since: _s, level_passes: _p, cusum: _c, z: _z, baseline_km2: _b, alerts_paused: _a, message: _m, ...rest } = l.status;
    return { ...l, status: { ...rest, status } };
  };
  const { method: _method, ...file } = fixtureLakes;
  return {
    ...file,
    lakes: [old(fixtureLakes.lakes[2], "Stable"), old(fixtureLakes.lakes[6], "Growing"), old(fixtureLakes.lakes[5], "Shrinking")],
  };
}

/**
 * A lake the way lakes-freeze leaves a frozen one: five open-water passes, two passes flagged frozen that read it 40%
 * larger, a frozen status from air temperature (and, for "Frozen (seen by Sentinel-2)", a clear snow-covered scene).
 */
export function frozenFixture(id: string, status: "Frozen (likely)" | "Frozen (seen by Sentinel-2)" | "Break-up likely" = "Frozen (likely)", extra: Partial<Lake> = {}): Lake {
  const p = (date: string, area: number, frozen: boolean, crid = "P05023") => ({ date, track: "084A", area_km2: area, observable_share: 1, excluded: null, crid, frozen });
  const s2 = status === "Frozen (seen by Sentinel-2)" ? { date: "2026-11-08", s2_id: "S2A_43SCV_20261108_0_L2A", clear_share: 0.97, snow_share: 0.94, water_share: 0, water_over: "lake outline" } : null;
  const state = status === "Frozen (likely)" ? "frozen_likely" : status === "Frozen (seen by Sentinel-2)" ? "frozen_s2" : "breakup_likely";
  const reason = "Probably frozen since 18 Oct 2026, when the air at the lake met the freeze rule.";
  return fixtureLake(id, status, "2026-10-30", {
    elevation_m: 4188,
    elevation_source: "Copernicus DEM GLO-30",
    series: [p("2026-08-01", 0.158, false), p("2026-08-13", 0.162, false), p("2026-08-25", 0.16, false), p("2026-09-06", 0.161, false), p("2026-09-18", 0.159, false), p("2026-10-18", 0.225, true, "P05036"), p("2026-10-30", 0.226, true, "P05036")],
    status: { status, track: "084A", latest_date: "2026-10-30", looks: 7, change_km2: null, noise_km2: null, reason },
    freeze: {
      state, since: "2026-10-18", temp_through: "2026-11-10", checked: "2026-11-12", cold_run_days: 30, warm_run_days: 0, fdd_since_sep: 150.4,
      t2m_mean_7d: -5.8, t2m_min_mean_7d: -11.2, s2, s2_searched: true, breakup_pass: null, frozen_passes: 2, reason,
    },
    ...extra,
  });
}

/**
 * A lake the way lakebuild writes it on the first rebuild after an accept, before any NISAR window is
 * fetched (lakebuild._empty with _no_looks): no passes, no images, no bounds.
 */
export const requestedLake: Lake = {
  id: "requested_lake",
  name: "Requested lake",
  lon: 70.9,
  lat: 37.5,
  role: "watch",
  coord_source: "Requested 2026-11-06 (issue #7): a survey",
  outline_source: null,
  area_label: "water area in the search window",
  downstream: null,
  downstream_source: null,
  status: {
    status: "Not enough NISAR looks yet",
    track: null,
    latest_date: null,
    looks: 0,
    change_km2: null,
    noise_km2: null,
    reason: "No valid NISAR pass yet.",
  },
  cloud_window_looks: 0,
  directions: [],
  limits: ["no NISAR windows fetched yet"],
  series: [],
  excluded: [],
  images: { latest_hh: null, water: null, date: null, track: null },
  bounds: null,
};

/** A copy of a lakes file with requestedLake appended, as the rebuild after an accept leaves it. */
export function withRequestedLake(file: LakesFile): LakesFile {
  return { ...file, lakes: [...file.lakes, requestedLake] };
}
