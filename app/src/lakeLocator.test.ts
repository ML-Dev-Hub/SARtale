// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { fixtureLakes } from "./fixtures";
import { BASE_ASPECT, BASE_BOUNDS, isUserMove, locatorStyle, markerElement, statusSlug } from "./lakeLocator";

describe("BASE_ASPECT", () => {
  it("is the width over the height of the picture's bounds as MapLibre draws them (Web Mercator), not the file's pixel ratio", () => {
    const { west, east, south, north } = BASE_BOUNDS;
    const y = (lat: number): number => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
    const want = ((east - west) * Math.PI / 180) / (y(north) - y(south));
    expect(BASE_ASPECT).toBeCloseTo(want, 9);
    expect(BASE_ASPECT).toBeGreaterThan(1.45);
    expect(BASE_ASPECT).toBeLessThan(1.49);
  });
});

describe("isUserMove", () => {
  it("counts drag, scroll, pinch and +/- button moves (they carry the DOM event)", () => {
    expect(isUserMove({ type: "movestart", originalEvent: new Event("mousedown") })).toBe(true);
    expect(isUserMove({ type: "zoomstart", originalEvent: { type: "wheel" } })).toBe(true);
  });

  it("ignores programmatic moves such as Map.resize() and fitBounds", () => {
    expect(isUserMove({ type: "movestart" })).toBe(false);
    expect(isUserMove({ type: "movestart", originalEvent: undefined })).toBe(false);
    expect(isUserMove({ type: "zoomstart", originalEvent: null })).toBe(false);
    expect(isUserMove(undefined)).toBe(false);
    expect(isUserMove(null)).toBe(false);
  });
});

describe("statusSlug", () => {
  it("turns each status into the word the pills and the map pins both use", () => {
    expect(statusSlug("Stable")).toBe("stable");
    expect(statusSlug("Growing")).toBe("growing");
    expect(statusSlug("Not enough NISAR looks yet")).toBe("not-enough-nisar-looks-yet");
    expect(statusSlug("Not seen this pass")).toBe("not-seen-this-pass");
  });
});

describe("markerElement", () => {
  const base = fixtureLakes.lakes[2];
  const lake = (status: string, role: "watch" | "control" | "story" = "watch") => ({ ...base, name: `Lake ${status}`, role, status: { ...base.status, status } }) as typeof base;

  it("carries the status the pills use, for Stable, Growing and Not observable", () => {
    expect(markerElement(lake("Stable"), false).dataset.status).toBe("stable");
    expect(markerElement(lake("Growing"), false).dataset.status).toBe("growing");
    expect(markerElement(lake("Not observable"), false).dataset.status).toBe("not-observable");
  });

  it("is a named button, marks control lakes, and shows selection as an attribute", () => {
    const m = markerElement(lake("Stable", "control"), true);
    expect(m.tagName).toBe("BUTTON");
    expect(m.getAttribute("aria-label")).toBe("Lake Stable");
    expect(m.dataset.control).toBe("true");
    expect(m.hasAttribute("data-selected")).toBe(true);
    const w = markerElement(lake("Stable"), false);
    expect(w.dataset.control).toBe("false");
    expect(w.hasAttribute("data-selected")).toBe(false);
  });
});

describe("locatorStyle", () => {
  it("draws the MODIS picture over the lakes' bounding box, under the pins", () => {
    const style = locatorStyle() as { sources: { base: { type: string; url: string; coordinates: number[][] } }; layers: { id: string }[] };
    expect(style.sources.base.type).toBe("image");
    expect(style.sources.base.url).toMatch(/story\/north_map\.jpg$/);
    const { west, east, south, north } = BASE_BOUNDS;
    expect(style.sources.base.coordinates).toEqual([[west, north], [east, north], [east, south], [west, south]]);
    expect(style.layers.map((l) => l.id)).toEqual(["background", "base"]);
  });
});
