// @vitest-environment jsdom
import { describe, expect, test } from "vitest";
import { findBannedClaims } from "./content";
import { fixtureLakes, frozenFixture, olderFile } from "./fixtures";
import type { Lake, LakesFile } from "./lakes";
import { checkLine, lakeChartData, messageBox, openingLake } from "./lakeWatchView";

// The lake's detail panel moved to the lake page (lakePage/lakePage.test.ts). What stays here is the data the page's
// blocks are built from.
const byId = (id: string) => fixtureLakes.lakes.find((l) => l.id === id)!;

describe("lakeChartData", () => {
  test("one chart series per track, excluded passes kept apart", () => {
    const pt = (date: string, track: string, area: number | null, excluded: string | null) => ({ date, track, area_km2: area, observable_share: 1, excluded });
    const lake: Lake = {
      ...fixtureLakes.lakes[2],
      // the producer's shape: an excluded pass has area_km2 null and keeps what it read as diagnostic_km2
      series: [pt("2026-07-01", "156A", 1.0, null), pt("2026-07-02", "64D", 2.0, null), { ...pt("2026-07-13", "156A", null, "bright"), diagnostic_km2: 9.0 }, pt("2026-07-25", "156A", 1.1, null), { ...pt("2026-07-30", "156A", null, "window has no valid HH pixels"), diagnostic_km2: null }],
    };
    const d = lakeChartData(lake);
    expect(d.series.filter((s) => !s.excluded).map((s) => s.label)).toEqual(["156A", "64D"]);
    const t156 = d.series.find((s) => s.label === "156A")!;
    expect(t156.values.filter((v) => v !== null)).toEqual([1.0, 1.1]);
    expect(d.series.find((s) => s.excluded)!.values.filter((v) => v !== null)).toEqual([9.0]);
  });

  test("test_chart_leaves_off_passes_that_saw_too_little_of_the_zone", () => {
    const pt = (date: string, area: number, share: number) => ({ date, track: "156A", area_km2: area, observable_share: share, excluded: null });
    const lake: Lake = { ...fixtureLakes.lakes[2], series: [pt("2026-07-01", 1.0, 0.9), pt("2026-07-13", 0.04, 0.06), pt("2026-07-25", 1.1, 0.5)] };
    expect(lakeChartData(lake, 0.5).series[0].values).toEqual([1.0, null, 1.1]);
    expect(lakeChartData(lake).series[0].values).toEqual([1.0, 0.04, 1.1]);
  });

  test("the chart marks the passes that set a level and draws the baseline ± 2 × noise band of the status track", () => {
    const p = (date: string, area: number, extra: object = {}) => ({ date, track: "156A", area_km2: area, observable_share: 1, excluded: null, ...extra });
    const series = [p("2026-09-01", 1.0), p("2026-09-13", 1.0), p("2026-09-25", 1.0),
      p("2026-10-07", 1.01, { z: 0.5, baseline_km2: 1.0, noise_km2: 0.02, level_contrib: "No change" }),
      p("2026-10-19", 1.2, { z: 9.5, baseline_km2: 1.0, noise_km2: 0.021, level_contrib: "Watch" }),
      { date: "2026-10-24", track: "063D", area_km2: 0.5, observable_share: 1, excluded: null }];
    const lake: Lake = { ...byId("grow-old"), series };
    const data = lakeChartData(lake, 0.5, 2);
    const hi = data.series.find((s) => s.band === "hi")!;
    const lo = data.series.find((s) => s.band === "lo")!;
    const set = data.series.find((s) => s.level)!;
    expect(hi.label).toBe("Baseline ± 2 × noise (156A), upper");
    expect(hi.values).toEqual([null, null, null, 1.04, 1.042, null]);
    expect(lo.values.map((v) => (v === null ? null : Number(v.toFixed(3))))).toEqual([null, null, null, 0.96, 0.958, null]);
    expect(set.values).toEqual([null, null, null, null, 1.2, null]);
    // without a level (older builds, frozen lakes) neither is drawn
    expect(lakeChartData(olderFile().lakes[0], 0.5, 2).series.some((s) => s.band || s.level)).toBe(false);
  });

  test("a frozen lake's frozen passes are their own grey series, left out of the track line", () => {
    const data = lakeChartData(frozenFixture("ice"));
    const ice = data.series.find((s) => s.frozen)!;
    expect(ice.label).toBe("Frozen passes (not open water)");
    expect(ice.values.filter((v) => v !== null)).toEqual([0.225, 0.226]);
    expect(data.series.find((s) => s.label === "084A")!.values.filter((v) => v !== null)).toHaveLength(5);
  });
});

describe("messageBox", () => {
  test("is the pipeline's message for a level, free of banned claims, and null without one", () => {
    for (const id of ["grow-new", "grow-old", "shrink"]) {
      const box = messageBox(byId(id))!;
      const m = byId(id).status.message!;
      expect(box.dataset.level).toBe(byId(id).status.status);
      expect(box.textContent).toContain(m.title);
      expect(box.textContent).toContain(m.what);
      expect(findBannedClaims(box.textContent!)).toEqual([]);
    }
    expect(messageBox(byId("stable"))).toBeNull();
  });
});

describe("openingLake", () => {
  const basin: Lake = {
    ...fixtureLakes.lakes[2],
    id: "basin",
    name: "Empty basin",
    lake_state: "no_lake",
    series: [{ date: "2026-07-25", track: "156A", area_km2: 0.97, observable_share: 1, excluded: null }],
  };
  const file: LakesFile = { ...fixtureLakes, lakes: [...fixtureLakes.lakes, basin] };

  test("is never a site with no lake now, even with the most dark area", () => {
    expect(openingLake(file.lakes).id).not.toBe("basin");
  });
});

describe("checkLine", () => {
  const c = { lake: "x", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "S2", days_apart: 0, s2_window_cloud_pct: 1, scope: "zone", radar_km2: 2.736, optical_km2: 4.585, area_error_pct: -40, iou: 0.5, zone_valid_share: 1, window_radar_km2: 3, window_optical_km2: 4, window_area_error_pct: null, window_iou: 0.4 };
  test("names the open-water season the pair was chosen in, when the row has one", () => {
    expect(checkLine({ ...c, season: "15 Jun–30 Sep" })).toMatch(/^One NISAR pass vs one Sentinel-2 scene \(open-water season 15 Jun–30 Sep\): NISAR 2\.736 km²/);
    expect(checkLine(c)).toMatch(/^One NISAR pass vs one Sentinel-2 scene: NISAR/);
  });
});
