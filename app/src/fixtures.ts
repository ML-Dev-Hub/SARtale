import type { Manifest } from "./types";

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

/** Test fixture only: the shape of a calibrated manifest. */
export const calibratedManifest: Manifest = {
  ...fixtureManifest,
  stack: "fixture-calibrated",
  stretch_db: { HH: [-12.9, 2.2], HV: [-21, -6] },
  pixel_m: 68,
  analysis_m: 30,
};
