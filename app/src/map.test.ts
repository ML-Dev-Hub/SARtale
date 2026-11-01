import { describe, expect, test } from "vitest";
import { cornersFromBounds, setComposite, setFrame, type MapLike } from "./map";
import { fixtureManifest as m } from "./fixtures";

function recordingMap(): MapLike & { calls: [string, unknown][] } {
  const calls: [string, unknown][] = [];
  return { calls, setImage: async (url, corners) => void calls.push([url, corners]) };
}

const mapThatFailsToLoad: MapLike = {
  setImage: () => Promise.reject(new Error("image 404")),
};

describe("map frames", () => {
  test("cornersFromBounds goes clockwise from top-left", () => {
    expect(cornersFromBounds([1, 2, 3, 4])).toEqual([[1, 4], [3, 4], [3, 2], [1, 2]]);
  });
  test("setFrame shows the frame image at the manifest corners", async () => {
    const map = recordingMap();
    await setFrame(map, m, "2026-07-14", "HH");
    expect(map.calls).toEqual([["data/frames/2026-07-14_HH.webp", cornersFromBounds(m.bounds)]]);
  });
  test("test_missing_overlay_reports_error", async () => {
    await expect(setFrame(mapThatFailsToLoad, m, "2026-07-02", "HH")).rejects.toThrow("overlay");
  });
  test("setComposite shows the composite and reports a missing one", async () => {
    const map = recordingMap();
    await setComposite(map, m);
    expect(map.calls[0][0]).toBe("data/frames/composite_HH.webp");
    await expect(setComposite(map, { ...m, composite: undefined })).rejects.toThrow("composite");
    await expect(setComposite(mapThatFailsToLoad, m)).rejects.toThrow("overlay");
  });
});
