import type { Manifest } from "./types";
import type { Lake, LakesFile, LakeStatusName } from "./lakes";

/** Test fixture only. Not shipped data. */
export const fixtureManifest: Manifest = {
  stack: "fixture",
  crid: "none",
  maturity: "Provisional",
  bounds: [0, 0, 1, 1],
  dates: [
    { date: "2026-07-02", granule: "g1", frames: { HH: "frames/2026-07-02_HH.webp", HV: "frames/2026-07-02_HV.webp" } },
    { date: "2026-07-14", granule: "g2", frames: { HH: "frames/2026-07-14_HH.webp", HV: "frames/2026-07-14_HV.webp" } },
    { date: "2026-07-26", granule: "g3", frames: { HH: "frames/2026-07-26_HH.webp", HV: "frames/2026-07-26_HV.webp" } },
  ],
  composite: "frames/composite_HH.webp",
  stretch_db: { HH: [0, 1], HV: [0, 1] },
};

export const INTERFERENCE_FLAG =
  "Likely radio interference in HV over the western area. Do not read this as surface change.";
export const FORECAST_FLAG = "Forecast-orbit product; positions may be less precise.";

/** Test fixture only: the shape of the real browse-preview manifest, with the two flagged dates. */
export const previewManifest: Manifest = {
  ...fixtureManifest,
  stack: "fixture-preview",
  maturity: "Provisional preview",
  dates: [
    { ...fixtureManifest.dates[0], flag: INTERFERENCE_FLAG },
    { ...fixtureManifest.dates[1], flag: FORECAST_FLAG },
    fixtureManifest.dates[2],
  ],
  composite_dates: ["2026-07-26", "2026-09-12", "2026-10-18"],
  stretch_db: null,
  pixel_m: 174,
};

/** Test fixture only: a calibrated manifest with a change layer, 2 Jul excluded and 14 Jul flagged. */
export const changeManifest: Manifest = {
  ...fixtureManifest,
  stack: "fixture-change",
  dates: previewManifest.dates,
  change: {
    method: "m",
    reference: "r",
    library: "numpy",
    version: "0",
    threshold: 3.5,
    scale_max: 7,
    baseline_dates: ["2026-07-26"],
    excluded: [{ date: "2026-07-02", reason: "Likely radio interference in HV on this date." }],
    removed_offsets_db: { "2026-07-14": { HH: -0.6, HV: -0.6 }, "2026-07-26": { HH: 0.1, HV: 0.1 } },
    date_notes: { "2026-07-26": "The cause is unexplained." },
    frames: { "2026-07-14": "frames/change_2026-07-14.webp", "2026-07-26": "frames/change_2026-07-26.webp" },
    step: {
      method: "m",
      reference: "r",
      pixel_m: 90,
      dates: ["2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31"],
      split_dates: ["2026-08-19"],
      min_segment: 2,
      min_step_db: 3,
      min_stability: 3.5,
      control_p99_db: 1,
      control_p99_stability: 0,
      shuffled_p99_db: 3,
      shuffled_p99_stability: 3,
      scatter_floor_db: 0.5,
      flagged_share: 0.01,
      frame: "frames/step_date.webp",
      classes: [{ date: "2026-07-26", up: [255, 200, 120], down: [214, 96, 16] }],
    },
  },
};

/** Test fixture only: the shape of a calibrated manifest. */
export const calibratedManifest: Manifest = {
  ...fixtureManifest,
  stack: "fixture-calibrated",
  stretch_db: { HH: [-12.9, 2.2], HV: [-21, -6] },
  pixel_m: 68,
  analysis_m: 30,
};

function fixtureLake(id: string, status: LakeStatusName, latest: string | null, extra: Partial<Lake> = {}): Lake {
  const measured = status === "Growing" || status === "Shrinking" || status === "Stable";
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
      change_km2: status === "Growing" ? 0.031 : status === "Shrinking" ? -0.04 : measured ? 0.001 : null,
      noise_km2: measured ? 0.005 : null,
      reason: `Fixture reason for ${id}.`,
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

/** Test fixture only: one lake per status, two growing on different dates, and a control. */
export const fixtureLakes: LakesFile = {
  version: 1,
  built: "2026-11-02T00:00:00Z",
  notes: "fixture",
  crid: "P05023",
  cloud_window: ["2026-06-17", "2026-08-04"],
  constants: { drop_db: 3, min_looks: 3, min_observable: 0.5, noise_floor_km2: 0.005, change_factor: 2, speckle_box: 3, outlier_z: 3.5 },
  lakes: [
    fixtureLake("control", "Not seen this pass", "2026-10-30", { role: "control" }),
    fixtureLake("hidden", "Not observable", null),
    fixtureLake("stable", "Stable", "2026-10-23"),
    fixtureLake("grow-old", "Growing", "2026-10-11"),
    fixtureLake("few", "Not enough NISAR looks yet", "2026-10-23"),
    fixtureLake("shrink", "Shrinking", "2026-10-23"),
    fixtureLake("grow-new", "Growing", "2026-10-23", { area_label: "water area inside the outline" }),
  ],
  checks: [],
};
