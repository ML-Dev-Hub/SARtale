import type { Lake, LakesFile, LakeStatusName } from "./lakes";


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
