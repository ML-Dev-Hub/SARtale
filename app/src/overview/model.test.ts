import { describe, expect, it } from "vitest";
import { makeFile, makeLake } from "../fixtures";
import type { Lake } from "../lakes";
import {
  DEFAULT_STATE, SORT_FOR_COLUMN, arrange, latestReadingOnTrack, matches, needsAttention, nextRefresh, overviewQuery,
  parseOverviewHash, sparklinePath, trendPoints,
} from "./model";
import type { OverviewFilter } from "./model";

const lake = (id: string, over: Partial<Lake> = {}, status: Partial<Lake["status"]> = {}): Lake => {
  const l = makeLake({ id, name: id, ...over });
  return { ...l, status: { ...l.status, ...status } };
};

const file = makeFile([
  lake("alert_lake", {}, { status: "Alert: growing", level: "Alert: growing", latest_date: "2026-11-09" }),
  lake("forming_site", { lake_state: "lake_forming_check" }, { status: "Lake may be forming", level: null }),
  lake("watch_lake", {}, { status: "Watch", level: "Watch" }),
  lake("decrease_lake", {}, { status: "Decrease noted", level: "Decrease noted" }),
  lake("passu", { district: "Hunza", share_of_largest: 0.96, elevation_m: 2500, previous_status: "Watch" }),
  lake("shazore", { district: "Chitral", share_of_largest: null, elevation_m: null }, { status: "Frozen (likely)", level: null }),
  lake("shisper", { district: "Nagar", lake_state: "no_lake", share_of_largest: null }, { status: "No lake now", level: null }),
  lake("karambar_lake", { district: "Ghizer", suparco: { id: 116, match: "probable", source: "PDGL" }, share_of_largest: 0.97, above_largest: true, elevation_m: 4000 }),
]);

describe("overview hash state", () => {
  it("unknown show, sort and map values fall back to the defaults", () => {
    expect(parseOverviewHash("show=bogus&district=&sort=x-up&map=7")).toEqual(DEFAULT_STATE);
  });
  it("an unknown district is kept and matches no lake", () => {
    const s = parseOverviewHash("district=Nowhere");
    expect(s.district).toBe("Nowhere");
    expect(arrange(file.lakes, s)).toEqual({ pinned: [], rows: [] });
  });
  it("a district with a space and a search with & survive a round trip", () => {
    const s = { ...DEFAULT_STATE, district: "Upper Dir", q: "a&b #1" };
    expect(parseOverviewHash(overviewQuery(s))).toEqual(s);
  });
  it("defaults are omitted", () => expect(overviewQuery(DEFAULT_STATE)).toBe(""));
  it("a full state round trips and writes the sort as key-dir", () => {
    const s = { show: "above" as const, district: "Hunza", q: "x", sort: "area" as const, dir: "desc" as const, map: true, sel: "passu" };
    expect(overviewQuery(s)).toBe("show=above&district=Hunza&q=x&sort=area-desc&map=1&sel=passu");
    expect(parseOverviewHash(overviewQuery(s))).toEqual(s);
  });
});

describe("arrange", () => {
  it("needs-attention lakes are pinned whatever the sort", () => {
    const { pinned, rows } = arrange(file.lakes, { ...DEFAULT_STATE, sort: "name" });
    expect(pinned.map((l) => l.id)).toEqual(["alert_lake", "forming_site", "watch_lake", "decrease_lake"]);
    expect(rows.every((l) => !needsAttention(l))).toBe(true);
  });
  it("filters combine", () => expect(arrange(file.lakes, { ...DEFAULT_STATE, show: "frozen", district: "Chitral" }).rows.map((l) => l.id)).toEqual(["shazore"]));
  it("nulls sort last both ways", () => {
    const ids = (dir: "asc" | "desc") => arrange(file.lakes, { ...DEFAULT_STATE, sort: "share", dir }).rows.map((l) => l.id);
    expect(ids("asc").slice(-2)).toEqual(["shisper", "shazore"].sort());
    expect(ids("desc").slice(-2)).toEqual(["shisper", "shazore"].sort());
    expect(ids("asc")[0]).toBe("passu");
    expect(ids("desc")[0]).toBe("karambar_lake");
  });
  it("the trend header sorts by change", () => expect(SORT_FOR_COLUMN.trend).toBe("change"));
  it("each filter picks its lakes", () => {
    const ids = (show: OverviewFilter) => {
      const a = arrange(file.lakes, { ...DEFAULT_STATE, show });
      return [...a.pinned, ...a.rows].map((l) => l.id).sort();
    };
    expect(ids("attention")).toEqual(["alert_lake", "decrease_lake", "forming_site", "watch_lake"]);
    expect(ids("alert")).toEqual(["alert_lake"]);
    expect(ids("watch")).toEqual(["watch_lake"]);
    expect(ids("frozen")).toEqual(["shazore"]);
    expect(ids("no-lake")).toEqual(["shisper"]);
    expect(ids("above")).toEqual(["karambar_lake"]);
    expect(ids("suparco")).toEqual(["karambar_lake"]);
    expect(ids("changed")).toEqual(["passu"]);
    expect(ids("open")).not.toContain("shazore");
    expect(ids("open")).toContain("passu");
    expect(ids("all")).toHaveLength(8);
  });
  it("search covers name, id, district and SUPARCO id, ignoring case", () => {
    const hit = (q: string) => file.lakes.filter((l) => matches(l, { ...DEFAULT_STATE, q })).map((l) => l.id);
    expect(hit("HUNZA")).toEqual(["passu"]);
    expect(hit("116")).toEqual(["karambar_lake"]);
    expect(hit("shis")).toEqual(["shisper"]);
  });
  it("sorts by name, elevation and area with ties by id", () => {
    const rows = (sort: "name" | "elevation" | "area", dir: "asc" | "desc" = "asc") => arrange(file.lakes, { ...DEFAULT_STATE, sort, dir }).rows.map((l) => l.id);
    expect(rows("name")).toEqual(["karambar_lake", "passu", "shazore", "shisper"]);
    expect(rows("elevation", "desc").slice(0, 2)).toEqual(["karambar_lake", "passu"]);
    expect(rows("area")).toEqual(["karambar_lake", "passu", "shazore", "shisper"]);
  });
});

describe("nextRefresh", () => {
  it("is the Monday after the build", () => {
    expect(nextRefresh("2026-11-13T12:28:00Z")).toBe("2026-11-16");
    expect(nextRefresh("2026-11-16T03:30:00Z")).toBe("2026-11-23");
    expect(nextRefresh("2026-11-16T02:59:00Z")).toBe("2026-11-16");
    expect(nextRefresh("2026-11-16T03:00:00Z")).toBe("2026-11-23");
  });
});

describe("readings and sparkline", () => {
  const pt = (date: string, area: number | null, extra: Record<string, unknown> = {}) =>
    ({ date, track: "055A", area_km2: area, observable_share: 1, excluded: null, ...extra });
  it("the latest reading is on the status track, valid and not frozen", () => {
    const l = lake("x", {
      series: [
        pt("2026-10-01", 0.1), pt("2026-10-13", 0.2), pt("2026-10-25", 0.3, { frozen: true }), pt("2026-11-06", null),
        { ...pt("2026-11-08", 0.9), track: "084A" },
      ],
    });
    expect(latestReadingOnTrack(l)).toEqual({ date: "2026-10-13", area: 0.2 });
    expect(trendPoints(l).map((p) => p.v)).toEqual([0.1, 0.2]);
    expect(latestReadingOnTrack(lake("y", { series: [] }))).toBeNull();
  });
  it("a sparkline needs two points and scales to its own range", () => {
    expect(sparklinePath([])).toBe("");
    expect(sparklinePath([{ t: 0, v: 1 }])).toBe("");
    const d = sparklinePath([{ t: 0, v: 1 }, { t: 10, v: 3 }, { t: 20, v: 2 }]);
    expect(d.startsWith("M")).toBe(true);
    expect(d.match(/[ML]/g)).toHaveLength(3);
    expect(sparklinePath([{ t: 0, v: 5 }, { t: 1, v: 5 }])).toMatch(/^M/);
  });
});
