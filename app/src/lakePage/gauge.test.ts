// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { frozenFixture, makeFile, makeLake } from "../fixtures";
import type { Lake } from "../lakes";
import { createLakePage } from "./lakePage";
import { gaugeGeometry, gaugeInput, renderGauge, type GaugeInput } from "./gauge";

vi.mock("../contacts", () => ({ authorityFor: () => null }));

afterEach(() => {
  document.body.innerHTML = "";
});

const g = (over: Partial<GaugeInput> = {}): GaugeInput => ({ change: 0, noise: 0.005, band: 0.01, floorApplied: false, hollow: false, ...over });
const frozen = frozenFixture("shazore");

function page(lake: Lake): HTMLElement {
  const el = document.createElement("div");
  document.body.append(el);
  createLakePage(el, { file: makeFile([lake]), lakeId: lake.id, onRoute: vi.fn() });
  return el;
}
const roles = (el: HTMLElement): string[] => [...el.querySelectorAll<HTMLElement>("section")].filter((s) => !s.parentElement?.closest("section")).map((s) => s.dataset.role!);
const cardText = (): string => page(frozen).querySelector('[data-role="lp-freeze"]')!.textContent!;

describe("the change gauge", () => {
  it("a change exactly on the band edge is nudged at most 2 px outward", () => {
    const up = gaugeGeometry(g({ change: 0.01 }), 400);
    expect(up.markerX! - up.x(0.01)).toBeGreaterThan(0); expect(up.markerX! - up.x(0.01)).toBeLessThanOrEqual(2); expect(up.nudged).toBe(true);
    const down = gaugeGeometry(g({ change: -0.01 }), 400);
    expect(down.x(-0.01) - down.markerX!).toBeGreaterThan(0); expect(down.x(-0.01) - down.markerX!).toBeLessThanOrEqual(2);
  });
  it("a change just inside the band is nudged inward", () => {
    const i = gaugeGeometry(g({ change: 0.00999 }), 400);
    expect(i.markerX!).toBeLessThan(i.x(0.01));
    expect(i.label).toContain("within threshold (rounded values shown)");
  });
  it("a change well away from the edge is not nudged", () => {
    const m = gaugeGeometry(g({ change: 0.002 }), 400);
    expect(m.nudged).toBe(false);
    expect(m.markerX).toBeCloseTo(m.x(0.002), 6);
  });
  it("uses the pipeline's threshold for the band", () => expect(gaugeInput(makeLake({ status: { ...makeLake().status, threshold_km2: 0.0123 } }), 2)!.band).toBe(0.0123));
  it("falls back to the factor times the noise when the build has no threshold", () => expect(gaugeInput(makeLake(), 2)!.band).toBeCloseTo(0.01, 10));
  it("a change beyond ±4 × noise shows an arrow and the exact value", () => {
    const o = gaugeGeometry(g({ change: -0.031 }), 400);
    expect(o.overflow).toBe("left"); expect(o.markerX).toBeNull(); expect(o.label).toBe("−0.0310 km² · beyond this scale");
  });
  it("says minimum noise used when the floor applied", () => {
    const el = document.createElement("div");
    renderGauge(el, makeLake({ status: { ...makeLake().status, noise_floor_applied: true } }), 2);
    expect(el.textContent).toContain("minimum noise used");
  });
  it("draws the copy, the numbers and an svg with the exact numbers in its label", () => {
    const el = document.createElement("div");
    renderGauge(el, makeLake(), 2);
    expect(el.textContent).toContain("Latest valid 055A reading minus the median of up to 6 earlier valid 055A readings");
    expect(el.textContent).toContain("Newest pass, 9 Nov 2026 (055A): baseline 0.130 km² · change +0.001 km² (+1%) · noise 0.005 km²");
    expect(el.textContent).toContain("zone observable on this pass 100%");
    expect(el.textContent).toContain("water area in the search window");
    expect(el.querySelector("svg")!.getAttribute("aria-label")).toContain("+0.0010 square kilometres");
  });
  it("the large number is the change with its percent, and the area sits on the line below", () => {
    const l = makeLake({ status: { ...makeLake().status, change_km2: -0.0088, baseline_km2: 0.142 } });
    const el = document.createElement("div");
    renderGauge(el, l, 2);
    expect(el.querySelector(".lp-gauge-value")!.textContent).toBe("−0.009 km² (−6%)");
    const area = el.querySelector(".lp-gauge-areaname")!;
    expect(area.textContent).toMatch(/^Area 0\.\d{3} km²/);
    expect(area.textContent).toContain("water area in the search window");
    expect(el.querySelector(".lp-gauge-value")!.compareDocumentPosition(area) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it("the large number has no percent when the baseline is zero", () => {
    const el = document.createElement("div");
    renderGauge(el, makeLake({ status: { ...makeLake().status, baseline_km2: 0 } }), 2);
    expect(el.querySelector(".lp-gauge-value")!.textContent).toBe("+0.001 km²");
  });
  it("no gauge while frozen; the frozen card has no 'open again'", () => {
    expect(gaugeInput(frozen, 2)).toBeNull();
    expect(cardText()).not.toMatch(/open again/i);
  });
  it("a lake without a baseline shows no gauge and no error", () => {
    const l = makeLake({ status: { ...makeLake().status, baseline_km2: null } });
    expect(gaugeInput(l, 2)).toBeNull(); expect(roles(page(l))).not.toContain("lp-gauge");
  });
  it("the page shows the gauge for an open lake and the frozen card, not the gauge, for a frozen one", () => {
    const open = page(makeLake());
    expect(roles(open)).toContain("lp-gauge");
    expect(open.querySelector('[data-role="lp-gauge"] h2')!.textContent).toBe("Change against baseline · 9 Nov 2026");
    const f = page(frozen);
    expect(roles(f)).toContain("lp-freeze");
    expect(roles(f)).not.toContain("lp-gauge");
  });
  it("the frozen card carries the headline, the facts, the latest reading and the last open-water pass", () => {
    const t = cardText();
    expect(t).toContain("Frozen: by air temperature since 18 Oct; no clear image");
    expect(t).toContain("Air temperature");
    expect(t).toContain("Latest reading 0.226 km² on 30 Oct 2026");
  });
  it("shows no percent when the baseline is zero", () => {
    const el = document.createElement("div");
    renderGauge(el, makeLake({ status: { ...makeLake().status, baseline_km2: 0 } }), 2);
    expect(el.textContent).toContain("change +0.001 km² · noise");
    expect(el.textContent).not.toMatch(/Infinity|NaN|%\)/);
  });
  it("leaves out the last open-water pass when the pipeline gives none", () => {
    expect(cardText()).not.toContain("Last open-water pass");
    const withLast = frozenFixture("shazore", "Frozen (likely)", { last_open: { date: "2026-09-18", track: "084A", area_km2: 0.159, status: "No change", change_km2: 0, noise_km2: 0.005, looks: 7, images: null } });
    expect(page(withLast).textContent).toContain("18 Sep 2026 · 0.159 km² · track 084A");
  });
  it("a Not yet validated lake draws a hollow marker", () => {
    const l = makeLake({ status: { ...makeLake().status, status: "Not yet validated against Sentinel-2" } });
    const el = document.createElement("div");
    renderGauge(el, l, 2);
    expect(el.querySelector(".lp-g-hollow")).not.toBeNull();
  });
});
