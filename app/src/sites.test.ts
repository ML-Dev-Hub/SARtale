import { afterEach, describe, expect, test, vi } from "vitest";
import demoManifest from "../demo-data/manifest.json";
import demoSitesJson from "../demo-data/sites.json";
import { findBannedClaims } from "./content";
import { loadSites, toChartSeries } from "./sites";
import type { Site } from "./types";

const siteWithGap: Site = {
  id: "gap",
  name: "Gap site",
  lon: 0.5,
  lat: 0.5,
  role: "demo",
  series: [
    { date: "2026-07-02", hh_db: -10, hv_db: -18, valid_fraction: 1 },
    { date: "2026-07-14", hh_db: -11, hv_db: null, valid_fraction: 0 },
    { date: "2026-07-26", hh_db: null, hv_db: -17, valid_fraction: 0.4 },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("toChartSeries", () => {
  test("test_series_gap_stays_null", () => {
    expect(toChartSeries(siteWithGap).hv[1]).toBeNull();
    expect(toChartSeries(siteWithGap).hh[2]).toBeNull();
  });

  test("values keep their order and x is UTC seconds", () => {
    const c = toChartSeries(siteWithGap);
    expect(c.hh).toEqual([-10, -11, null]);
    expect(c.hv).toEqual([-18, null, -17]);
    expect(c.x).toEqual([Date.UTC(2026, 6, 2) / 1000, Date.UTC(2026, 6, 14) / 1000, Date.UTC(2026, 6, 26) / 1000]);
  });

  test("rows given out of date order are sorted together", () => {
    const shuffled: Site = { ...siteWithGap, series: [siteWithGap.series[2], siteWithGap.series[0], siteWithGap.series[1]] };
    expect(toChartSeries(shuffled)).toEqual(toChartSeries(siteWithGap));
  });

  test("a site with no series gives empty arrays", () => {
    expect(toChartSeries({ ...siteWithGap, series: [] })).toEqual({ x: [], hh: [], hv: [] });
  });
});

describe("loadSites", () => {
  test("returns the list when sites.json exists", async () => {
    vi.stubGlobal("fetch", async () => new Response(JSON.stringify([siteWithGap])));
    expect(await loadSites("data/sites.json")).toEqual([siteWithGap]);
  });

  test("returns null when sites.json is absent", async () => {
    vi.stubGlobal("fetch", async () => new Response("nope", { status: 404 }));
    expect(await loadSites("data/sites.json")).toBeNull();
  });

  test("returns null when the response is not a list of sites (dev server answering with index.html)", async () => {
    vi.stubGlobal("fetch", async () => new Response("<!doctype html>"));
    expect(await loadSites("data/sites.json")).toBeNull();
  });

  test("returns null when the request fails", async () => {
    vi.stubGlobal("fetch", async () => {
      throw new Error("offline");
    });
    expect(await loadSites("data/sites.json")).toBeNull();
  });
});

describe("demo fixture sites.json (not served)", () => {
  test("covers exactly the manifest dates, has a gap, and uses invented names", () => {
    const manifestDates = demoManifest.dates.map((d) => d.date);
    const demo = demoSitesJson as Site[];
    expect(demo.length).toBeGreaterThan(0);
    for (const s of demo) {
      expect(s.name).toMatch(/^Demo site /);
      expect(s.series.map((p) => p.date)).toEqual(manifestDates);
    }
    expect(demo.some((s) => toChartSeries(s).hv.includes(null))).toBe(true);
    expect(findBannedClaims(JSON.stringify(demo))).toEqual([]);
  });
});
