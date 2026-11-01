import { describe, expect, test } from "vitest";
import { fixtureManifest } from "./fixtures";
import { coverageSegments, gapSummary, stateLabel } from "./gap";
import type { Manifest } from "./types";

const GAP = { start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" };
const m: Manifest = { ...fixtureManifest, gap: GAP };

test("test_gap_is_labelled_no_observation", () => {
  expect(stateLabel("no-observation")).toBe("No observation");
});
test("observed is labelled Observed", () => {
  expect(stateLabel("observed")).toBe("Observed");
});
test("a date inside the gap is not observed", () => {
  const s = coverageSegments(m, "2026-08-01", "2026-08-01");
  expect(s[0].state).toBe("no-observation");
});
test("an acquisition date is observed", () => {
  expect(coverageSegments(m, "2026-07-26", "2026-07-26")[0].state).toBe("observed");
});

describe("coverageSegments", () => {
  test("returns one segment per calendar day, inclusive, in order", () => {
    const s = coverageSegments(m, "2026-07-01", "2026-07-04");
    expect(s.map((x) => x.date)).toEqual(["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"]);
    expect(s.map((x) => x.state)).toEqual(["no-observation", "observed", "no-observation", "no-observation"]);
  });

  test("days between passes are not part of the permanent gap", () => {
    const s = coverageSegments(m, "2026-07-03", "2026-07-03");
    expect(s[0]).toEqual({ date: "2026-07-03", state: "no-observation", inGap: false });
  });

  test("days inside the gap are marked inGap", () => {
    const s = coverageSegments(m, "2026-07-28", "2026-08-09");
    expect(s).toHaveLength(13);
    expect(s.every((x) => x.inGap && x.state === "no-observation")).toBe(true);
  });

  test("a manifest date inside the gap is still no observation", () => {
    const bad: Manifest = {
      ...m,
      dates: [...m.dates, { date: "2026-08-01", granule: "x", frames: { HH: "a", HV: "b" } }],
    };
    const s = coverageSegments(bad, "2026-08-01", "2026-08-01");
    expect(s[0].state).toBe("no-observation");
    expect(s[0].inGap).toBe(true);
  });

  test("a day only partly covered by the gap is not marked inGap, so a pass on it stays observed", () => {
    const edge: Manifest = {
      ...m,
      dates: [
        ...m.dates,
        { date: "2026-07-27", granule: "x", frames: { HH: "a", HV: "b" } },
        { date: "2026-08-10", granule: "y", frames: { HH: "a", HV: "b" } },
      ],
    };
    const s = coverageSegments(edge, "2026-07-27", "2026-08-10");
    expect(s[0]).toEqual({ date: "2026-07-27", state: "observed", inGap: false });
    expect(s[s.length - 1]).toEqual({ date: "2026-08-10", state: "observed", inGap: false });
  });

  test("a manifest with no gap has no inGap days", () => {
    const s = coverageSegments(fixtureManifest, "2026-07-01", "2026-08-30");
    expect(s.some((x) => x.inGap)).toBe(false);
  });

  test("an empty, reversed or invalid range returns []", () => {
    expect(coverageSegments(m, "2026-07-05", "2026-07-01")).toEqual([]);
    expect(coverageSegments(m, "nope", "2026-07-01")).toEqual([]);
    expect(coverageSegments(m, "2026-02-30", "2026-03-02")).toEqual([]);
  });

  test("works across a month and a year boundary", () => {
    const s = coverageSegments(m, "2026-12-30", "2027-01-02");
    expect(s.map((x) => x.date)).toEqual(["2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"]);
  });
});

describe("gapSummary", () => {
  test("is null when the manifest holds no gap", () => {
    expect(gapSummary(fixtureManifest)).toBeNull();
  });

  test("states the gap start and end from the manifest, with no data then", () => {
    const text = gapSummary(m)!;
    expect(text).toContain("27 Jul 2026, 22:03:25 UTC");
    expect(text).toContain("10 Aug 2026, 00:55:27 UTC");
    expect(text).toContain("NISAR has no data");
  });
});
