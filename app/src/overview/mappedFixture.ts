import type { MappedLakesFile } from "./model";

/** A valid mapped_lakes.json with three lakes, for tests. */
export const mappedFixture: MappedLakesFile = {
  version: 1,
  built: "2026-11-14T03:30:10Z",
  notice: { odbl: "OSM data under the ODbL 1.0, (c) OpenStreetMap contributors.", cc_by: "HKH-PK-2020 and Hi-MAG outlines under CC BY 4.0." },
  sources: [{ id: "osm", name: "OpenStreetMap", licence: "ODbL 1.0", attribution: "(c) OpenStreetMap contributors", url: "https://www.openstreetmap.org/copyright" }],
  lakes: [
    { id: "m0001", lon: 73.1, lat: 35.7, km2: 0.159, year: 2020, source: "hkhpk2020", suparco: { id: 129, match: "probable" } },
    { id: "m0002", lon: 72.8, lat: 35.8, km2: 0.05, year: null, source: "osm", suparco: null },
    { id: "m0003", lon: 74.2, lat: 36.4, km2: 0.4, year: 2014, source: "himag", suparco: null },
  ],
};
