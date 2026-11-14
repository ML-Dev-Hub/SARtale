import { describe, expect, it } from "vitest";
import shipped from "../public/data/lakes.json";
import { frozenFixture, makeLake } from "./fixtures";
import type { Lake, LakesFile } from "./lakes";
import { familyCounts, frozenBreakdown, statusDisplay, type Family } from "./statusDisplay";

const withStatus = (status: string, extra: Partial<Lake["status"]> = {}): Lake => {
  const l = makeLake();
  return { ...l, status: { ...l.status, status, ...extra } };
};

describe("statusDisplay", () => {
  const rows: Array<[string, Lake, Family, string, string, boolean]> = [
    ["Alert: growing", withStatus("Alert: growing", { level_since: "2026-11-09" }), "alert", "Alert: growing", "since 9 Nov", false],
    ["Watch", withStatus("Watch", { level_since: "2026-11-09" }), "watch", "Watch", "since 9 Nov", false],
    ["Decrease noted", withStatus("Decrease noted", { level_since: "2026-11-09" }), "decrease", "Decrease noted", "since 9 Nov", false],
    ["No change", withStatus("No change", { level_since: "2026-10-16" }), "nochange", "No change", "since 16 Oct", false],
    ["Frozen S2", frozenFixture("f", "Frozen (seen by Sentinel-2)"), "frozen", "Frozen", "Seen in Sentinel-2 since 18 Oct", false],
    ["Frozen likely", frozenFixture("f", "Frozen (likely)"), "frozen", "Frozen", "By air temperature since 18 Oct; no clear image", false],
    ["Break-up", frozenFixture("f", "Break-up likely"), "breakup", "Ice breaking up", "Air above 0 °C since 18 Oct", true],
    ["Not measurable", withStatus("Not measurable"), "unmeasured", "Not measured", "Radar and Sentinel-2 disagree; area for information only", true],
    ["Not validated", withStatus("Not yet validated against Sentinel-2"), "unmeasured", "Not measured", "Waiting for a clear Sentinel-2 scene to check the radar", false],
    ["Not observable", withStatus("Not observable"), "unmeasured", "Not measured", "Radar cannot see enough of the lake on this track", false],
    ["Not enough", withStatus("Not enough NISAR looks yet"), "unmeasured", "Not measured", "Fewer than 3 radar looks so far", false],
    ["Not seen", withStatus("Not seen this pass"), "unmeasured", "Not measured", "The newest pass did not see the lake", false],
    ["No lake", withStatus("No lake now"), "nolake", "No lake now", "No water in recent imagery", false],
    ["Forming", withStatus("Lake may be forming", { reason: "Water over 20% of the zone." }), "forming", "Lake may be forming", "Water over 20% of the zone.", false],
  ];
  it.each(rows)("%s", (_n, lake, family, chip, tag, dashed) => {
    const d = statusDisplay(lake, { min_looks: 3 });
    expect(d).toMatchObject({ family, chip, tag, dashed });
  });

  it("falls back to Not measured with the raw status for an unknown status", () => {
    const d = statusDisplay(withStatus("Something new"));
    expect(d.family).toBe("unmeasured");
    expect(d.tag).toBe("Something new");
  });

  it("leaves out the date when it is not known", () => {
    expect(statusDisplay(withStatus("Watch", { level_since: null })).tag).toBe("");
  });

  it("ranks the families in display order", () => {
    const lakes: Lake[] = [withStatus("Alert: growing"), withStatus("Watch"), withStatus("Decrease noted"), withStatus("Lake may be forming"),
      withStatus("No change"), withStatus("Not observable"), frozenFixture("b", "Break-up likely"), frozenFixture("f"), withStatus("No lake now")];
    const ranks = lakes.map((l) => statusDisplay(l).rank);
    expect(statusDisplay(lakes[0]).family).toBe("alert");
    expect(ranks).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it("family counts agree with the shipped counts", () => {
    const file = shipped as unknown as LakesFile;
    const c = familyCounts(file.lakes);
    expect(c.frozen + c.breakup).toBe(file.counts!.frozen);
    expect(c.nolake).toBe(file.counts!.no_lake);
    expect(c.watch).toBe(file.counts!.watch);
    expect(c.decrease).toBe(file.counts!.decrease);
    expect(c.alert).toBe(file.counts!.alert);
    const b = frozenBreakdown(file.lakes);
    expect(b.seen + b.temperature).toBe(c.frozen);
    expect(b).toEqual({ seen: 9, temperature: 7 });
  });
});
