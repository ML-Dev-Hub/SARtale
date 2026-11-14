// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { formatDate } from "../format";
import { frozenFixture, makeLake } from "../fixtures";
import { lakeChartData, statusTrackPasses } from "../lakeWatchView";
import { historyHeading, readingRows, renderHistory } from "./history";

const pass = (date: string, track: string, area: number | null, crid: string, extra: object = {}) => ({
  date, track, area_km2: area, observable_share: 1, excluded: null as string | null, crid, z: 0.2, baseline_km2: 0.13, noise_km2: 0.005, ...extra,
});
const dates = ["2026-07-02", "2026-07-14", "2026-07-26", "2026-08-07", "2026-08-19", "2026-09-12", "2026-10-16", "2026-10-28"];
const twoTrack = makeLake({
  series: [
    ...dates.map((d, i) => (i === 3 ? pass(d, "055A", null, "P05023", { excluded: "Too little of the lake zone seen" }) : pass(d, "055A", 0.13 + i / 1000, i >= 6 ? "P05036" : "P05023"))),
    ...["2026-07-05", "2026-07-17", "2026-07-29", "2026-08-10"].map((d) => pass(d, "156A", 0.2, "P05023")),
  ],
});
const frozen = frozenFixture("shazore");

describe("lakeChartData for the history chart", () => {
  it("draws the status track only, with a rail for unusable passes", () => {
    const d = lakeChartData(twoTrack, 0, 2, { statusTrackOnly: true });
    expect(d.series.filter((s) => !s.rail && !s.band && !s.frozen && !s.version && !s.level && !s.excluded).map((s) => s.label)).toEqual(["055A"]);
    expect(d.series.find((s) => s.rail)!.values.filter((v) => v !== null)).toHaveLength(1);
    expect(d.x).toHaveLength(8);
  });
  it("marks the first reading on a new processing version", () => {
    const v = lakeChartData(twoTrack, 0, 2, { statusTrackOnly: true }).series.find((s) => s.version)!;
    expect(v.label).toBe("First reading on P05036");
    expect(v.values.filter((x) => x !== null)).toHaveLength(1);
  });
  it("greys frozen passes and drops the band while frozen", () => {
    const d = lakeChartData(frozen, 0, 2, { statusTrackOnly: true });
    expect(d.series.some((s) => s.frozen)).toBe(true);
    expect(d.series.some((s) => s.band)).toBe(false);
  });
  it("keeps the band while open", () => {
    expect(lakeChartData(twoTrack, 0, 2, { statusTrackOnly: true }).series.filter((s) => s.band).map((s) => s.band)).toEqual(["hi", "lo"]);
  });
  it("leaves the default chart unchanged", () => {
    expect(lakeChartData(twoTrack, 0, 2).series.map((s) => s.label)).toContain("156A");
  });
});

describe("readingRows", () => {
  it("lists the newest six readings and shows all on request", () => {
    expect(readingRows(twoTrack, false)).toHaveLength(6);
    expect(readingRows(twoTrack, true)).toHaveLength(8);
    expect(readingRows(twoTrack, false)[0].d).toBe(formatDate(statusTrackPasses(twoTrack).at(-1)!.date));
  });
  it("gives a reason for a pass left out, and dashes for what is missing", () => {
    const r = readingRows(twoTrack, true).find((x) => x.d === formatDate("2026-08-07"))!;
    expect(r.area).toBe("—");
    expect(r.note).toContain("Too little of the lake zone seen");
  });
  it("says a frozen pass is not an open-water reading", () => {
    expect(readingRows(frozen, true)[0].note).toContain("frozen");
  });
});

describe("renderHistory", () => {
  const mount = (lake = twoTrack, createChart = vi.fn(() => ({ destroy() {} }))) => {
    const el = document.createElement("div");
    const ok = renderHistory(el, lake, { minObservable: 0.5, factor: 2, createChart });
    return { el, ok, createChart };
  };
  it("names the track and the months", () => {
    expect(historyHeading(twoTrack)).toBe("History on track 055A, July to October 2026");
  });
  it("mounts the chart on the status track and says other tracks are not drawn", () => {
    const { el, createChart } = mount();
    expect(createChart).toHaveBeenCalledTimes(1);
    expect(el.textContent).toContain("Only 055A readings are drawn: each track sees the lake from its own angle, so readings from 156A are compared only with their own track.");
    expect(el.textContent).toContain("Largest valid reading on 055A, 2026 season");
  });
  it("shows six rows, then all on request", () => {
    const { el } = mount();
    expect(el.querySelectorAll('[role="row"]')).toHaveLength(7);
    const btn = el.querySelector<HTMLButtonElement>("button.lp-showall")!;
    expect(btn.textContent).toBe("Show all 8 readings");
    btn.click();
    expect(el.querySelectorAll('[role="row"]')).toHaveLength(9);
    expect(el.querySelector("button.lp-showall")!.textContent).toBe("Show only the newest 6");
  });
  it("says why no band is drawn while frozen", () => {
    expect(mount(frozen).el.textContent).toContain("No reference band is drawn");
  });
  it("draws nothing for a lake with no readings", () => {
    expect(mount(makeLake({ series: [] })).ok).toBe(false);
  });
  it("still lists readings without a chart factory", () => {
    const el = document.createElement("div");
    expect(renderHistory(el, twoTrack, { minObservable: 0.5, factor: 2 })).toBe(true);
    expect(el.querySelectorAll('[role="row"]')).toHaveLength(7);
  });
});
