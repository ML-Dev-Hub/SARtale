import { describe, expect, it } from "vitest";
import { isUserMove, statusSlug } from "./lakeLocator";

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
