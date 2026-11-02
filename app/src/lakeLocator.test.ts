import { describe, expect, it } from "vitest";
import { isUserMove } from "./lakeLocator";

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
