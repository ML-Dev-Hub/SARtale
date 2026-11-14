import { describe, expect, it } from "vitest";
import { makeFile, makeLake } from "../fixtures";
import { limitsList, sourceRows } from "./sources";

const file = makeFile([makeLake()]);
const probable = makeLake({ suparco: { id: 116, match: "probable", source: "s" } });
const official = makeLake({ suparco: { id: 116, match: "official", source: "s" } });
const row = (l: ReturnType<typeof makeLake>, k: string): string => sourceRows(l, file).find((r) => r.k === k)!.v;

describe("sourceRows", () => {
  it("lists the sources in order and degrades missing ones", () => {
    const rows = sourceRows(makeLake(), file);
    expect(rows.map((r) => r.k)).toEqual(["Coordinates", "Outline", "Sentinel-2 check", "SUPARCO match", "Method", "Latency for this lake", "Elevation", "District"]);
    expect(rows.find((r) => r.k === "Elevation")!.v).toBe("—");
    expect(rows.find((r) => r.k === "District")!.v).toBe("—");
  });
  it("never calls a probable match official", () => expect(row(probable, "SUPARCO match")).toContain("our match by map position and area"));
  it("names an official match as official", () => expect(row(official, "SUPARCO match")).toContain("from SUPARCO's official list"));
  it("says when no SUPARCO ID matches", () => expect(row(makeLake(), "SUPARCO match")).toBe("No SUPARCO PDGL ID matches this lake by map position and area."));
  it("describes a lake with no outline as a search circle", () => expect(row(makeLake({ outline_source: null, area_label: "water area in the search window (300 m circle)" }), "Outline")).toBe("Search circle of 0.3 km (no mapped outline)"));
  it("words the latency from the number of tracks that pass", () => {
    expect(row(makeLake(), "Latency for this lake")).toBe("1 track (055A) passes over this lake, so a change shows here 12–24 days after it begins");
  });
  it("gives elevation and district with their sources", () => {
    const l = makeLake({ elevation_m: 2512.4, elevation_source: "Copernicus DEM", district: "Hunza", province: "GB" });
    expect(row(l, "Elevation")).toBe("2,512 m (Copernicus DEM)");
    expect(row(l, "District")).toBe("Hunza, Gilgit-Baltistan");
  });
  it("joins the lake's limits and the method's limits", () => {
    const l = makeLake({ limits: ["Own limit."] });
    expect(limitsList(l, file)[0]).toBe("Own limit.");
    expect(limitsList(l, file).length).toBeGreaterThan(1);
  });
});
