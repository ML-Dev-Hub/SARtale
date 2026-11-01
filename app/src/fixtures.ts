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
