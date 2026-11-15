// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { frozenFixture, makeLake as baseLake } from "../fixtures";
import type { Lake } from "../lakes";
import { extentView, renderExtent } from "./extent";

const makeLake = (o: Partial<Lake> = {}): Lake => baseLake({ outline_source: "HKH-PK-2020", ...o });
const ext = { km2: 1, source: "Glacial lake inventory", year: 2020 };

describe("extentView", () => {
  it("says Above only when the pipeline says above", () => {
    const v = extentView(makeLake({ share_of_largest: 1.4, above_largest: true, largest_extent: ext }));
    expect("word" in v && v.word).toBe("Above");
    expect("pct" in v && v.pct).toBe("140%");
  });
  it("says Within below 100%", () => {
    const v = extentView(makeLake({ share_of_largest: 0.93, above_largest: false, largest_extent: ext }));
    expect("word" in v && v.word).toBe("Within");
  });
  it("says Within noise at 100% or more when not above", () => {
    const v = extentView(makeLake({ share_of_largest: 1.004, above_largest: false, largest_extent: ext }));
    expect("word" in v && v.word).toBe("Within noise");
  });
  it("says noise unknown, not Within, at 100% or more when the decision is null", () => {
    const v = extentView(makeLake({ share_of_largest: 1.03, above_largest: null, largest_extent: ext }));
    expect("word" in v && v.word).toBe("noise unknown");
  });
  it("below 100% the reading is inside the outline whatever the noise", () => {
    const v = extentView(makeLake({ share_of_largest: 0.9, above_largest: null, largest_extent: ext }));
    expect("word" in v && v.word).toBe("Within");
  });
  it("gives the pipeline's reason when there is no share", () => {
    expect(extentView(makeLake({ share_of_largest: null, share_note: "Not shown while the lake is frozen: the radar area is not an open-water measurement." })))
      .toEqual({ reason: expect.stringContaining("frozen") });
  });
});

describe("no value without a real basis", () => {
  it("a frozen lake shows only the reason", () => {
    const f = { ...frozenFixture("shazore"), outline_source: "HKH-PK-2020", share_of_largest: 0.9, above_largest: false, share_note: null };
    expect(extentView(f)).toEqual({ reason: expect.stringContaining("frozen") });
  });
  it("a circle zone (no outline) shows only the reason, and the pipeline's note wins", () => {
    const c = baseLake({ outline_source: null, share_of_largest: 0.9, above_largest: false });
    expect(extentView(c)).toEqual({ reason: expect.stringContaining("circle") });
    expect(extentView({ ...c, share_note: "Because." })).toEqual({ reason: "Because." });
  });
  it("km2 is shown to 3 decimals and an undated source is not repeated", () => {
    const el = document.createElement("div");
    renderExtent(el, makeLake({ share_of_largest: 1.4, above_largest: true, largest_extent: { km2: 0.1633, source: "OpenStreetMap outline (undated)", year: null } }));
    expect(el.textContent).toContain("Largest mapped outline: 0.163 km², OpenStreetMap outline (undated).");
    expect(el.textContent).not.toContain("undated), undated");
  });
});

describe("renderExtent", () => {
  it("shows the share, the source and year, and the caveat", () => {
    const el = document.createElement("div");
    renderExtent(el, makeLake({ share_of_largest: 0.93, above_largest: false, largest_extent: ext }));
    expect(el.textContent).toContain("93%");
    expect(el.textContent).toContain("Within");
    expect(el.textContent).toContain("Glacial lake inventory, 2020");
    expect(el.textContent).toContain("Radar area against the largest mapped outline");
    expect(el.textContent).toContain("NISAR, 055A");
  });
  it("says undated when the extent has no year", () => {
    const el = document.createElement("div");
    renderExtent(el, makeLake({ share_of_largest: 0.5, above_largest: false, largest_extent: { km2: 2, source: "s", year: null } }));
    expect(el.textContent).toContain("undated");
  });
  it("shows the share_note when there is no share", () => {
    const el = document.createElement("div");
    renderExtent(el, makeLake({ share_of_largest: null, share_note: "Not shown while the lake is frozen." }));
    expect(el.textContent).toContain("Not shown while the lake is frozen.");
  });
  it("shows a dash with no error for a lake with no extent fields", () => {
    const el = document.createElement("div");
    renderExtent(el, makeLake());
    expect(el.textContent).toContain("—");
  });
});
