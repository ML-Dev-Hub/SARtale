// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { fixtureLakes } from "./fixtures";
import { isUserMove, markerElement, statusSlug } from "./lakeLocator";

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
