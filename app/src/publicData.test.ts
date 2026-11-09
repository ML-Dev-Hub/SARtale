import { describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { findBannedClaims } from "./content";
import { MATURITY } from "./app";
import type { LakesFile } from "./lakes";

const lakes = lakesJson as unknown as LakesFile;
// Paths relative to app/public/data, listed by Vite so no Node typings are needed.
const dataFiles = Object.keys(import.meta.glob("../public/data/**/*", { query: "?url" })).map((p) => p.replace("../public/data/", ""));

describe("the data the app ships (app/public/data)", () => {
  test("is lakes.json, requests.json and the lake images lakes.json names, nothing else", () => {
    // Derived from lakes.json, so a rebuild with more lakes keeps passing.
    const images = lakes.lakes
      .flatMap((l) => (l.images ? [l.images.latest_hh, l.images.water] : []))
      .filter((p): p is string => typeof p === "string");
    expect(dataFiles.sort()).toEqual(["lakes.json", "requests.json", ...images].sort());
  });

  test("names its NISAR processing versions and collections, with the cloud window and the method constants", () => {
    // every CRID used, sorted and comma-joined; the provisional release (P05023) is in every build that keeps June
    expect(lakes.crid).toMatch(/^P\d{5}(, P\d{5})*$/);
    expect(lakes.crid.split(", ")).toContain("P05023");
    const crids = new Set(lakes.lakes.flatMap((l) => l.series.map((p) => p.crid)));
    expect([...crids].sort().join(", ")).toBe(lakes.crid);
    expect(lakes.collections).toContain("NISAR_L2_GCOV_PROVISIONAL_V1");
    expect(MATURITY).toBe("Provisional NISAR data"); // the label stays while any provisional pass is used
    expect(lakes.cloud_window).toEqual(["2026-06-17", "2026-08-04"]);
    expect(lakes.constants.change_factor).toBeGreaterThan(1);
    expect(lakes.lakes.length).toBeGreaterThan(0);
  });

  test("every lake names where its coordinates come from", () => {
    for (const l of lakes.lakes) expect(l.coord_source, l.id).toMatch(/\S/);
  });

  test("has no banned claims", () => {
    expect(findBannedClaims(JSON.stringify(lakesJson))).toEqual([]);
  });
});
