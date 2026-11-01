import { describe, expect, test } from "vitest";
import manifestJson from "../public/data/manifest.json";
import placesJson from "../public/data/overlays/places.geojson?raw";
import sitesJson from "../public/data/sites.json";
import { cardFor, findBannedClaims } from "./content";
import { FORECAST_FLAG, INTERFERENCE_FLAG } from "./fixtures";
import { sitesForManifest } from "./sites";
import { maturityBanner } from "./timeline";
import type { Manifest, Site } from "./types";

const manifest = manifestJson as unknown as Manifest;
const sites = sitesJson as unknown as Site[];
// Paths relative to app/public/data, listed by Vite so no Node typings are needed.
const dataFiles = Object.keys(import.meta.glob("../public/data/**/*", { query: "?url" })).map((p) => p.replace("../public/data/", ""));

const REAL_DATES = [
  "2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
  "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18",
];

describe("the data the app ships (app/public/data)", () => {
  const built = manifest.dates.map((d) => d.date);

  test("is the calibrated manifest: real granule IDs, a dB stretch, every acquisition listed", () => {
    expect(manifest.maturity).toBe("Provisional");
    expect(built.length).toBeGreaterThanOrEqual(5);
    expect(built).toEqual(REAL_DATES.filter((d) => built.includes(d))); // real dates, in order; the rest arrive with the rebuild
    for (const d of manifest.dates) {
      expect(d.granule).toMatch(/^NISAR_L2_PR_GCOV_\d{3}_084_A_019_4005_DHDH_A_\d{8}T\d{6}_\d{8}T\d{6}_P05023_[A-Z]_F_J_001$/);
      expect(d.granule).toContain(d.date.replaceAll("-", "") + "T");
    }
    expect(manifest.crid).toBe("P05023");
    expect(manifest.gap).toEqual({ start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" });
    expect(manifest.bounds).toEqual([71.2, 33.8, 73.4, 34.8]);
    expect(manifest.acquisitions).toEqual(REAL_DATES);
    expect(manifest.analysis_m).toBe(30);
    expect(manifest.pixel_m).toBeGreaterThan(30);
    expect(manifest.pixel_m).toBeLessThan(100);
    for (const pol of ["HH", "HV"] as const) {
      const [lo, hi] = manifest.stretch_db![pol];
      expect(lo).toBeLessThan(hi);
      expect(lo).toBeGreaterThan(-40);
      expect(hi).toBeLessThan(15);
    }
  });

  test("the banner reads Provisional NISAR data", () => {
    expect(maturityBanner(manifest)).toEqual({ kind: "provisional", text: "Provisional NISAR data" });
  });

  test("flags exactly 2 Jul and 14 Jul, with the wording the app fixes", () => {
    const flagged = manifest.dates.filter((d) => d.flag);
    expect(flagged.map((d) => d.date)).toEqual(["2026-07-02", "2026-07-14"]);
    expect(flagged[0].flag).toBe(INTERFERENCE_FLAG);
    expect(flagged[1].flag).toBe(FORECAST_FLAG);
  });

  test("the composite is three built dates and never 2 July", () => {
    expect(manifest.composite_dates).toHaveLength(3);
    for (const d of manifest.composite_dates!) expect(built).toContain(d);
    expect(manifest.composite_dates).not.toContain("2026-07-02");
  });

  test("every frame file the manifest names exists, and nothing else is in frames/", () => {
    const named = [manifest.composite!, ...manifest.dates.flatMap((d) => Object.values(d.frames))];
    expect(named).toHaveLength(2 * built.length + 1);
    expect(dataFiles.filter((f) => f.startsWith("frames/")).sort()).toEqual([...named].sort());
  });

  test("no synthetic demo content or preview leftovers ship", () => {
    expect(JSON.stringify(manifestJson)).not.toMatch(/synthetic|demo|preview/i);
    expect(dataFiles.some((f) => /demo|synthetic/i.test(f))).toBe(false);
    const frames = dataFiles.filter((f) => f.startsWith("frames/"));
    expect(dataFiles.sort()).toEqual([...frames, "manifest.json", "overlays/places.geojson", "sites.json"].sort());
  });

  test("the site curves belong to this manifest and cover every built date", () => {
    expect(sitesForManifest(sites, manifest)).toHaveLength(sites.length);
    for (const s of sites) expect(s.series.map((p) => p.date)).toEqual(built);
  });

  test("every site has a written card, whose dates are built dates", () => {
    for (const s of sites) {
      const c = cardFor(s.id);
      expect(c.evidence, s.id).not.toBe("placeholder");
      expect(c.dates.length, s.id).toBeGreaterThan(0);
      for (const d of c.dates) expect(built, `${s.id} ${d}`).toContain(d);
    }
  });

  test("every value a card quotes equals the curve", () => {
    for (const s of sites) {
      for (const q of cardFor(s.id).quotes ?? []) {
        const point = s.series.find((p) => p.date === q.date);
        expect(point, `${s.id} ${q.date}`).toBeDefined();
        const value = q.pol === "HH" ? point!.hh_db : point!.hv_db;
        expect(value?.toFixed(1), `${s.id} ${q.date} ${q.pol}`).toBe(q.db);
        expect(cardFor(s.id).observation, `${s.id}: ${q.db} dB is in the sentence`).toContain(`${q.db} dB`);
      }
    }
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
