// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, test } from "vitest";

// uPlot reads matchMedia when it loads; jsdom has none. No canvas is created here.
beforeAll(() => {
  window.matchMedia ??= ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })) as never;
});

const ZONES = ["UTC", "America/New_York", "America/Los_Angeles", "Pacific/Auckland"];
// The app tsconfig has no Node types; the test runs in Node, so reach process through globalThis.
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } }).process.env;
const original = env.TZ;
afterEach(() => {
  if (original === undefined) delete env.TZ;
  else env.TZ = original;
});

const DATA = {
  x: [Date.UTC(2026, 6, 2) / 1000, Date.UTC(2026, 6, 14) / 1000],
  series: [
    { label: "Track 156A", values: [0.12, 0.13], excluded: false },
    { label: "Left out", values: [null, 0.2], excluded: true },
  ],
};

describe("lake chart options", () => {
  test.each(ZONES)("tzDate maps a UTC-midnight timestamp to the same calendar date in %s", async (zone) => {
    env.TZ = zone;
    const { lakeChartOptions, utcTzDate } = await import("./chart");
    const ts = Date.UTC(2026, 6, 2) / 1000;
    const d = utcTzDate(ts);
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([2026, 6, 2, 0]);
    expect(lakeChartOptions(300, DATA).tzDate!(ts).getDate()).toBe(2);
  });

  test("a track is a line, and left-out passes are markers with no line", async () => {
    const { lakeChartOptions } = await import("./chart");
    const [, track, out] = lakeChartOptions(300, DATA).series;
    expect([track.label, track.width, track.spanGaps]).toEqual(["Track 156A", 2, true]);
    expect([out.label, out.width]).toEqual(["Left out", 0]);
  });
});

describe("history chart marks", () => {
  const HIST = {
    x: [Date.UTC(2026, 6, 2) / 1000, Date.UTC(2026, 6, 14) / 1000, Date.UTC(2026, 6, 26) / 1000],
    series: [
      { label: "055A", values: [0.12, null, 0.13], excluded: false },
      { label: "No usable reading", values: [null, 0, null], excluded: false, rail: true },
      { label: "NISAR processing update", values: [null, null, 0.13], excluded: false, version: true },
    ],
  };

  test("axis fonts are at least 14 px", async () => {
    const { lakeChartOptions } = await import("./chart");
    for (const a of lakeChartOptions(300, HIST).axes!) {
      expect(Number(String(a.font).match(/(\d+)px/)![1])).toBeGreaterThanOrEqual(14);
      expect(Number(String(a.labelFont).match(/(\d+)px/)![1])).toBeGreaterThanOrEqual(14);
    }
  });

  test("the y axis says it is the radar water area", async () => {
    const { lakeChartOptions } = await import("./chart");
    expect(lakeChartOptions(300, HIST).axes![1].label).toBe("Radar water area (km²)");
  });

  test("unusable passes sit on their own rail scale, as rings with no line", async () => {
    const { lakeChartOptions } = await import("./chart");
    const o = lakeChartOptions(300, HIST);
    const rail = o.series[2];
    expect([rail.scale, rail.width, rail.points?.show]).toEqual(["rail", 0, true]);
    expect(o.scales!.rail).toBeDefined();
  });

  test("the version marker draws a line in a hook, not a series line", async () => {
    const { lakeChartOptions } = await import("./chart");
    const o = lakeChartOptions(300, HIST);
    expect([o.series[3].width, o.series[3].points?.show]).toEqual([0, false]);
    expect(o.hooks!.draw).toHaveLength(1);
  });

  test("a bridge series is dashed, the track does not span the gap, and rings take the level colour", async () => {
    const { lakeChartOptions } = await import("./chart");
    const o = lakeChartOptions(300, { x: HIST.x, series: [HIST.series[0], { label: "Line dashed", values: [0.12, null, 0.13], excluded: false, bridge: true }, { label: "Pass that set a Watch", values: [null, null, 0.13], excluded: false, level: true, levelName: "Watch" }] });
    expect([o.series[1].spanGaps, o.series[2].dash, o.series[2].spanGaps]).toEqual([false, [5, 5], true]);
    expect(o.series[3].points?.stroke).toBe("#ffc46b");
  });

  test("the plain chart has neither a rail scale nor a hook", async () => {
    const { lakeChartOptions } = await import("./chart");
    const o = lakeChartOptions(300, DATA);
    expect(o.scales!.rail).toBeUndefined();
    expect(o.hooks!.draw).toBeUndefined();
  });
});

test("x-axis dates read day month ('18 Jun'), in UTC", async () => {
  const { dayMonth, lakeChartOptions } = await import("./chart");
  expect(dayMonth(Date.UTC(2026, 5, 18) / 1000)).toBe("18 Jun");
  expect(dayMonth(Date.UTC(2026, 0, 1) / 1000)).toBe("1 Jan");
  const xAxis = lakeChartOptions(300, DATA).axes![0];
  const ts = Date.UTC(2026, 5, 18) / 1000;
  const out = (xAxis.values as unknown as (u: unknown, splits: number[]) => string[])({}, [ts, ts + 86400 * 12]);
  expect(out).toEqual(["18 Jun", "30 Jun"]);
});
