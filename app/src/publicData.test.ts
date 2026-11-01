import { describe, expect, test } from "vitest";
import manifestJson from "../public/data/manifest.json";
import placesJson from "../public/data/overlays/places.geojson?raw";
import { findBannedClaims } from "./content";
import { FORECAST_FLAG, INTERFERENCE_FLAG } from "./fixtures";
import type { Manifest } from "./types";

const manifest = manifestJson as unknown as Manifest;
// Paths relative to app/public/data, listed by Vite so no Node typings are needed.
const dataFiles = Object.keys(import.meta.glob("../public/data/**/*", { query: "?url" })).map((p) => p.replace("../public/data/", ""));

const REAL_DATES = [
  "2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
  "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18",
];

describe("the data the app ships (app/public/data)", () => {
  test("is the real browse-preview manifest: 9 dates, real granule IDs, no dB stretch", () => {
    expect(manifest.maturity).toBe("Provisional preview");
    expect(manifest.stretch_db).toBeNull();
    expect(manifest.dates.map((d) => d.date)).toEqual(REAL_DATES);
    for (const d of manifest.dates) {
      expect(d.granule).toMatch(/^NISAR_L2_PR_GCOV_\d{3}_084_A_019_4005_DHDH_A_\d{8}T\d{6}_\d{8}T\d{6}_P05023_[A-Z]_F_J_001$/);
      expect(d.granule).toContain(d.date.replaceAll("-", "") + "T");
    }
    expect(manifest.crid).toBe("P05023");
    expect(manifest.gap).toEqual({ start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" });
    expect(manifest.bounds).toEqual([71.2, 33.8, 73.4, 34.8]);
    expect(manifest.acquisitions).toEqual(REAL_DATES);
    expect(manifest.pixel_m).toBeGreaterThan(150);
    expect(manifest.pixel_m).toBeLessThan(200);
  });

  test("flags exactly 2 Jul and 14 Jul, with the wording the brief fixes", () => {
    const flagged = manifest.dates.filter((d) => d.flag);
    expect(flagged.map((d) => d.date)).toEqual(["2026-07-02", "2026-07-14"]);
    expect(flagged[0].flag).toBe(INTERFERENCE_FLAG);
    expect(flagged[1].flag).toBe(FORECAST_FLAG);
  });

  test("the composite never uses 2 July", () => {
    expect(manifest.composite_dates).toEqual(["2026-07-26", "2026-09-12", "2026-10-18"]);
  });

  test("every frame file the manifest names exists", () => {
    const files = [manifest.composite!, ...manifest.dates.flatMap((d) => Object.values(d.frames))];
    expect(files).toHaveLength(19);
    for (const f of files) expect(dataFiles, f).toContain(f);
  });

  test("no synthetic demo content ships: no sites.json, nothing labelled demo or synthetic", () => {
    expect(dataFiles).not.toContain("sites.json");
    expect(JSON.stringify(manifestJson)).not.toMatch(/synthetic|demo/i);
    const frames = dataFiles.filter((f) => f.startsWith("frames/"));
    expect(frames).toHaveLength(19);
    expect(dataFiles.some((f) => /demo|synthetic/i.test(f))).toBe(false);
    expect(dataFiles.sort()).toEqual([...frames, "manifest.json", "overlays/places.geojson"].sort());
  });

  test("place labels are the six hand-entered points", () => {
    const places = JSON.parse(placesJson) as {
      type: string;
      features: { geometry: { type: string; coordinates: [number, number] }; properties: { name: string; anchor?: string } }[];
    };
    expect(places.type).toBe("FeatureCollection");
    const got = Object.fromEntries(places.features.map((f) => [f.properties.name, f.geometry.coordinates]));
    expect(got).toEqual({
      Peshawar: [71.56, 34.01],
      Nowshera: [71.98, 34.02],
      Charsadda: [71.73, 34.15],
      Mardan: [72.05, 34.2],
      Swabi: [72.47, 34.12],
      "Tarbela Reservoir": [72.7, 34.08],
    });
    for (const f of places.features) expect(f.geometry.type).toBe("Point");
    // Swabi is north-west of Tarbela and about 20 km away. Its label sits above its point and Tarbela's below its own,
    // so the two cannot overlap at any zoom.
    const anchors = Object.fromEntries(places.features.map((f) => [f.properties.name, f.properties.anchor]));
    expect(anchors["Swabi"]).toBe("bottom");
    expect(anchors["Tarbela Reservoir"]).toBe("top");
    expect(findBannedClaims(JSON.stringify(places))).toEqual([]);
  });
});
