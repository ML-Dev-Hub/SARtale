import { describe, expect, it } from "vitest";
import { makeLake } from "./fixtures";
import { SENTINEL2_URL_CHECKED, sentinel2Url } from "./links";

describe("links", () => {
  it("sentinel2Url puts the lake at the centre", () => {
    expect(sentinel2Url(makeLake({ lat: 36.458, lon: 74.881 }))).toContain("lat=36.4580&lng=74.8810");
  });
  it("opens the Copernicus browser at zoom 13", () => {
    expect(sentinel2Url(makeLake({ lat: 36.5, lon: 74.5 }))).toBe("https://browser.dataspace.copernicus.eu/?zoom=13&lat=36.5000&lng=74.5000");
  });
  it("records the date the parameters were checked", () => expect(SENTINEL2_URL_CHECKED).toMatch(/^\d{4}-\d{2}-\d{2}$/));
});
