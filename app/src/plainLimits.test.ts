import { describe, expect, it } from "vitest";
import { changedLimits, plainLimit } from "./plainLimits";

const ZONE = "Track 164D comes in another UTM zone (EPSG:32642); its windows are resampled (nearest neighbour) onto the lake's grid (EPSG:32643).";
const MIX = "Track 084A mixes NISAR processing versions P05023 (provisional) and P05036 (standard). A calibration change between them can shift areas.";
const NOTES = "Areas are water within a lake's outline (buffered 200 m) or, without one, a search circle (1 km unless the lake sets a smaller one), by method D17 (Lee-filtered HH at least 3 dB below the window median); wet shore and sediment flats read as water, so a lake drawing down onto them barely changes its radar area; images are crops on the UTM grid, north up; they are pictures, not map overlays.";

describe("plainLimit", () => {
  it("rewrites the other-UTM-zone line without EPSG codes or resampling jargon", () => {
    expect(plainLimit(ZONE)).toBe("Track 164D is recorded on a neighbouring map grid; its pixels are shifted onto this lake's grid before measuring, which can move the outline edge by up to one pixel.");
  });
  it("rewrites the mixed-versions line without P-codes", () => {
    expect(plainLimit(MIX)).toBe("Track 084A mixes early (provisional) and later (standard) NISAR processing; the change between them can shift the measured area a little.");
  });
  it("rewrites the areas line without the method code", () => {
    expect(plainLimit(NOTES)).toBe("Area = radar-dark water inside the lake outline (plus 200 m) or a search circle. Wet shore and mud flats also look dark, so a lake that drains onto them barely changes its radar area. Images are pictures, not map overlays.");
  });
  it("leaves no technical tokens in any rewritten line", () => {
    for (const t of [ZONE, MIX, NOTES]) expect(plainLimit(t)).not.toMatch(/EPSG|nearest neighbour|D17|P0\d{4}|UTM/);
  });
  it("passes unknown lines through unchanged", () => {
    expect(plainLimit("Lakes below about 0.05 km² are limited by speckle.")).toBe("Lakes below about 0.05 km² are limited by speckle.");
    expect(plainLimit("Areas are water within a 1 km search circle.")).toBe("Areas are water within a 1 km search circle.");
  });
  it("changedLimits lists the original wording of lines that were rewritten, once each", () => {
    expect(changedLimits([ZONE, "plain", MIX, ZONE])).toEqual([ZONE, MIX]);
  });
});
