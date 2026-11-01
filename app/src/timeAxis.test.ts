// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { calibratedManifest, changeManifest, fixtureManifest } from "./fixtures";
import { buildAxis, mountAxis, nearestDate } from "./timeAxis";
import type { Manifest } from "./types";

const REAL_DATES = [
  "2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
  "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18",
];

/** The real shape: nine passes with uneven spacing and the gap between 26 Jul and 19 Aug. */
const REAL: Manifest = {
  ...calibratedManifest,
  dates: REAL_DATES.map((date) => ({ date, granule: "g", frames: { HH: `frames/${date}_HH.webp`, HV: `frames/${date}_HV.webp` } })),
  gap: { start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" },
};

afterEach(() => {
  document.body.innerHTML = "";
});

describe("the time axis", () => {
  test("places dates by real time, not by their order", () => {
    const a = buildAxis(REAL);
    const pos = Object.fromEntries(a.dates.map((d) => [d.date, d.pos]));
    // 26 Jul to 19 Aug is 24 days and 19 Aug to 31 Aug is 12, so the first step is twice as long.
    const long = pos["2026-08-19"] - pos["2026-07-26"];
    const short = pos["2026-08-31"] - pos["2026-08-19"];
    expect(long / short).toBeCloseTo(2, 5);
    // And the equal 12-day passes are equally spaced.
    expect(pos["2026-07-26"] - pos["2026-07-14"]).toBeCloseTo(pos["2026-07-14"] - pos["2026-07-02"], 5);
    expect(a.days).toBe(109);
    expect(a.dates.map((d) => d.index)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
    for (const d of a.dates) {
      expect(d.pos).toBeGreaterThan(0);
      expect(d.pos).toBeLessThan(1);
    }
  });

  test("draws the gap as a band between 26 Jul and 19 Aug, at its real width", () => {
    const a = buildAxis(REAL);
    const pos = Object.fromEntries(a.dates.map((d) => [d.date, d.pos]));
    expect(a.gap).not.toBeNull();
    expect(a.gap!.from).toBeGreaterThan(pos["2026-07-26"]);
    expect(a.gap!.to).toBeLessThan(pos["2026-08-19"]);
    // 22:03:25 on 27 Jul to 00:55:27 on 10 Aug is 13 days, 2 hours and 52 minutes.
    const days = (a.gap!.to - a.gap!.from) * 109;
    expect(days).toBeCloseTo(13 + (2 + 52 / 60) / 24, 2);
    expect(a.gap!.label).toBe("No data 27 Jul to 10 Aug");
  });

  test("a manifest with no gap draws none", () => {
    expect(buildAxis(fixtureManifest).gap).toBeNull();
  });

  test("flagged and excluded dates are marked on the model", () => {
    const a = buildAxis({
      ...REAL,
      dates: REAL.dates.map((d, i) => (i === 1 ? { ...d, flag: "Forecast-orbit product; positions may be less precise." } : d)),
      change: changeManifest.change,
    });
    const byDate = Object.fromEntries(a.dates.map((d) => [d.date, d]));
    expect(byDate["2026-07-14"].flag).toContain("Forecast-orbit");
    expect(byDate["2026-07-02"].excluded).toContain("interference");
    expect(byDate["2026-07-26"].flag).toBeUndefined();
  });

  test("month ticks sit where the months start", () => {
    const a = buildAxis(REAL);
    expect(a.months.map((m) => m.label)).toEqual(["Jul", "Aug", "Sep", "Oct"]);
    expect(a.months[1].pos).toBeCloseTo(30 / 109, 5);
  });

  test("passes imaged but not built are kept apart from the selectable dates", () => {
    const a = buildAxis({ ...REAL, acquisitions: [...REAL_DATES, "2026-10-30"] });
    expect(a.unused.map((u) => u.date)).toEqual(["2026-10-30"]);
    expect(a.dates).toHaveLength(9);
  });

  test("a click or touch on the axis picks the nearest date by time", () => {
    const a = buildAxis(REAL);
    const jul26 = a.dates[2].pos;
    const aug19 = a.dates[3].pos;
    expect(nearestDate(a, jul26 + (aug19 - jul26) * 0.4)).toBe(2);
    expect(nearestDate(a, jul26 + (aug19 - jul26) * 0.6)).toBe(3);
    expect(nearestDate(a, 0)).toBe(0);
    expect(nearestDate(a, 1)).toBe(8);
  });
});

describe("mounted axis", () => {
  function mount(disabled = false, manifest = REAL) {
    const track = document.createElement("div");
    const layer = document.createElement("div");
    layer.getBoundingClientRect = () => ({ left: 0, width: 1000, top: 0, height: 10, right: 1000, bottom: 10, x: 0, y: 0, toJSON() {} }) as DOMRect;
    track.append(layer);
    document.body.append(track);
    const picks: [number, boolean][] = [];
    const model = buildAxis(manifest);
    const handle = mountAxis(track, layer, model, { onPick: (i, f) => picks.push([i, f]), disabled: () => disabled });
    return { track, layer, picks, handle, model };
  }
  const ev = (type: string, x: number) => Object.assign(new Event(type, { bubbles: true }), { clientX: x, pointerId: 1, button: 0 });

  test("draws one dot per built date, a gap band and month ticks", () => {
    const { layer } = mount();
    expect(layer.querySelectorAll(".axis-dot:not(.unused)")).toHaveLength(9);
    expect(layer.querySelector(".axis-gap")).not.toBeNull();
    expect(layer.querySelectorAll(".axis-month")).toHaveLength(4);
  });

  test("flagged dots are marked and carry their caution", () => {
    const flag = "Likely radio interference in HV over the western area. Do not read this as surface change.";
    const { layer } = mount(false, { ...REAL, dates: REAL.dates.map((d, i) => (i === 0 ? { ...d, flag } : d)) });
    const dot = layer.querySelector<HTMLElement>('[data-date="2026-07-02"]')!;
    expect(dot.classList.contains("flagged")).toBe(true);
    expect(dot.title).toContain("Likely radio interference");
    expect(layer.querySelector('[data-date="2026-07-26"]')!.classList.contains("flagged")).toBe(false);
  });

  test("pressing on the axis picks a date, dragging keeps picking, releasing ends it", () => {
    const { track, picks, model } = mount();
    const x = (i: number) => model.dates[i].pos * 1000;
    track.dispatchEvent(ev("pointerdown", x(3)));
    track.dispatchEvent(ev("pointermove", x(4)));
    track.dispatchEvent(ev("pointerup", x(4)));
    expect(picks).toEqual([[3, false], [4, false], [4, true]]);
    track.dispatchEvent(ev("pointermove", x(6)));
    expect(picks).toHaveLength(3);
  });

  test("a disabled axis ignores the pointer", () => {
    const { track, picks } = mount(true);
    track.dispatchEvent(ev("pointerdown", 500));
    expect(picks).toEqual([]);
  });

  test("select, tint, exclusion and highlight change classes only", () => {
    const { layer, handle } = mount();
    handle.select(3);
    expect(layer.querySelector('[data-date="2026-08-19"]')!.classList.contains("current")).toBe(true);
    handle.select(4);
    expect(layer.querySelector('[data-date="2026-08-19"]')!.classList.contains("current")).toBe(false);
    handle.tint({ "2026-08-19": "rgb(214 96 16)" });
    const dot = layer.querySelector<HTMLElement>('[data-date="2026-08-19"]')!;
    expect(dot.style.getPropertyValue("--step")).toBe("rgb(214 96 16)");
    expect(dot.classList.contains("step")).toBe(true);
    handle.tint(null);
    expect(dot.classList.contains("step")).toBe(false);
    handle.highlight("2026-08-31");
    expect(layer.querySelector('[data-date="2026-08-31"]')!.classList.contains("lit")).toBe(true);
  });
});
