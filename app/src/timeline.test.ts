import { describe, expect, test } from "vitest";
import { formatDate, frameUrl, maturityBanner, orderedDates } from "./timeline";
import { fixtureManifest as m } from "./fixtures";

describe("timeline", () => {
  test("frameUrl returns the file for a date and polarization", () => {
    expect(frameUrl(m, "2026-07-02", "HV")).toBe("data/frames/2026-07-02_HV.webp");
  });
  test("frameUrl throws for a date that is not in the manifest", () => {
    expect(() => frameUrl(m, "2026-01-01", "HH")).toThrow("2026-01-01");
  });
  test("orderedDates sorts oldest first", () => {
    const unsorted = { ...m, dates: [...m.dates].reverse() };
    expect(orderedDates(unsorted)[0]).toBe("2026-07-02");
  });
  test("provisional data shows the provisional label", () => {
    expect(maturityBanner(m)).toEqual({ kind: "provisional", text: "Provisional NISAR data" });
  });
  test("anything not Provisional shows the synthetic demo banner", () => {
    const b = maturityBanner({ ...m, maturity: "Synthetic demo" });
    expect(b).toEqual({ kind: "synthetic", text: "SYNTHETIC DEMO: NOT NISAR DATA" });
    expect(maturityBanner({ ...m, maturity: "" }).kind).toBe("synthetic");
  });
  test("formatDate avoids time zone shifts", () => {
    expect(formatDate("2026-07-02")).toBe("2 Jul 2026");
  });
});
