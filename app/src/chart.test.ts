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

describe("chart options", () => {
  test.each(ZONES)("tzDate maps a UTC-midnight timestamp to the same calendar date in %s", async (zone) => {
    env.TZ = zone;
    const { chartOptions, utcTzDate } = await import("./chart");
    const ts = Date.UTC(2026, 6, 2) / 1000;
    const d = utcTzDate(ts);
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([2026, 6, 2, 0]);
    expect(chartOptions(300).tzDate!(ts).getDate()).toBe(2);
  });

  test("lines do not span gaps, and both polarizations are labelled in dB", async () => {
    const { chartOptions } = await import("./chart");
    const o = chartOptions(300);
    expect(o.series.slice(1).map((s) => [s.label, s.spanGaps])).toEqual([["HH (dB)", false], ["HV (dB)", false]]);
  });
});
