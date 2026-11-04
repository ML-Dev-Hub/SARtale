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
