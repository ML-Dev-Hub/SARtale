import { afterEach, describe, expect, test, vi } from "vitest";
import demoManifest from "../demo-data/manifest.json";
import demoSitesJson from "../demo-data/sites.json";
import { findBannedClaims } from "./content";
import { loadSites, sitesForManifest, toChartSeries } from "./sites";
import type { Manifest, Site } from "./types";

const siteWithGap: Site = {
  id: "gap",
  name: "Gap site",
  lon: 0.5,
  lat: 0.5,
  role: "demo",
  stack: "084_A_019",
  crid: "P05023",
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

describe("sitesForManifest", () => {
  const real = { stack: "084_A_019", crid: "P05023" } as Manifest;
  const stamped = (stack: string, crid: string, id = "x"): Site => ({ ...siteWithGap, id, stack, crid });

  test("keeps sites stamped with the manifest's stack and crid", () => {
    const own = stamped("084_A_019", "P05023");
    expect(sitesForManifest([own], real)).toEqual([own]);
  });

  test("drops sites from another stack or another crid", () => {
    expect(sitesForManifest([stamped("063_D_071", "P05023")], real)).toBeNull();
    expect(sitesForManifest([stamped("084_A_019", "P05024")], real)).toBeNull();
  });

  test("drops sites with no stamp, as an older sites.json has", () => {
    const { stack: _s, crid: _c, ...bare } = siteWithGap;
    expect(sitesForManifest([bare as Site], real)).toBeNull();
  });

  test("keeps only the matching sites of a mixed file", () => {
    const own = stamped("084_A_019", "P05023", "own");
    expect(sitesForManifest([stamped("synthetic-demo", "none", "demo"), own], real)).toEqual([own]);
  });

  test("returns null for no sites at all, so the view says No site curves yet", () => {
    expect(sitesForManifest(null, real)).toBeNull();
    expect(sitesForManifest([], real)).toBeNull();
  });

  test("demo sites show beside the demo manifest and never beside the real one", () => {
    const demo = demoSitesJson as Site[];
    expect(sitesForManifest(demo, demoManifest as unknown as Manifest)).toHaveLength(demo.length);
    expect(sitesForManifest(demo, real)).toBeNull();
  });
});

describe("demo fixture sites.json (not served)", () => {
  test("covers exactly the manifest dates, has a gap, and uses invented names", () => {
    const manifestDates = demoManifest.dates.map((d) => d.date);
    const demo = demoSitesJson as Site[];
    expect(demo.length).toBeGreaterThan(0);
    for (const s of demo) {
      expect(s.name).toMatch(/^Demo site /);
      expect([s.stack, s.crid]).toEqual(["synthetic-demo", "none"]);
      expect(s.series.map((p) => p.date)).toEqual(manifestDates);
    }
    expect(demo.some((s) => toChartSeries(s).hv.includes(null))).toBe(true);
    expect(findBannedClaims(JSON.stringify(demo))).toEqual([]);
  });
});
