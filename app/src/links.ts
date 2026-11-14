import type { Lake } from "./lakes";

/** The date the Copernicus Browser parameters below were checked to open the lake's place. */
export const SENTINEL2_URL_CHECKED = "2026-11-14";

/** The Copernicus Browser, centred on the lake at zoom 13, where an officer can pick a recent Sentinel-2 scene. */
export function sentinel2Url(l: Lake): string {
  return `https://browser.dataspace.copernicus.eu/?zoom=13&lat=${l.lat.toFixed(4)}&lng=${l.lon.toFixed(4)}`;
}
