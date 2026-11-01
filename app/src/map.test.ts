import { describe, expect, test } from "vitest";
import { cornersFromBounds, setChangeOverlay, setComposite, setFrame, setStepOverlay, type MapLike } from "./map";
import { changeManifest, fixtureManifest as m } from "./fixtures";

function recordingMap(): MapLike & { calls: [string, unknown][] } {
  const calls: [string, unknown][] = [];
  return { calls, setImage: async (url, corners) => void calls.push([url, corners]) };
}

const mapThatFailsToLoad: MapLike = {
  setImage: () => Promise.reject(new Error("image 404")),
};

describe("change overlay", () => {
  const corners = cornersFromBounds(changeManifest.bounds);
  function overlayMap(fail = false): MapLike & { shown: (string | null)[] } {
    const shown: (string | null)[] = [];
    return {
      shown,
      setImage: async () => {},
      setOverlay: async (url, at) => {
        if (fail) throw new Error("image 404");
        expect(at).toEqual(corners);
        shown.push(url);
      },
    };
  }

  test("a scored date shows its frame", async () => {
    const map = overlayMap();
    await setChangeOverlay(map, changeManifest, "2026-07-14");
    expect(map.shown).toEqual(["data/frames/change_2026-07-14.webp"]);
  });
  test("an excluded date and null both clear the overlay", async () => {
    const map = overlayMap();
    await setChangeOverlay(map, changeManifest, "2026-07-02");
    await setChangeOverlay(map, changeManifest, null);
    expect(map.shown).toEqual([null, null]);
  });
  test("a frame that fails to load is reported", async () => {
    await expect(setChangeOverlay(overlayMap(true), changeManifest, "2026-07-14")).rejects.toThrow("change overlay");
  });
  test("the step map is one frame for the whole season, and a failure is reported", async () => {
    const map = overlayMap();
    await setStepOverlay(map, changeManifest);
    expect(map.shown).toEqual(["data/frames/step_date.webp"]);
    await expect(setStepOverlay(overlayMap(true), changeManifest)).rejects.toThrow("change overlay");
  });
  test("a map with no overlay support is left alone", async () => {
    await expect(setChangeOverlay({ setImage: async () => {} }, changeManifest, "2026-07-14")).resolves.toBeUndefined();
  });
});

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
  test("setFrame rejects, not throws, for a date with no HV frame", async () => {
    const noHv = {
      ...m,
      dates: m.dates.map((d) => (d.date === "2026-07-14" ? { ...d, frames: { HH: d.frames.HH } as typeof d.frames } : d)),
    };
    const map = recordingMap();
    let promise: Promise<void> | undefined;
    expect(() => { promise = setFrame(map, noHv, "2026-07-14", "HV"); }).not.toThrow();
    await expect(promise).rejects.toThrow("overlay");
    await expect(setFrame(map, noHv, "2026-01-01", "HH")).rejects.toThrow("overlay");
    expect(map.calls).toEqual([]);
  });
  test("setComposite shows the composite and reports a missing one", async () => {
    const map = recordingMap();
    await setComposite(map, m);
    expect(map.calls[0][0]).toBe("data/frames/composite_HH.webp");
    await expect(setComposite(map, { ...m, composite: undefined })).rejects.toThrow("composite");
    await expect(setComposite(mapThatFailsToLoad, m)).rejects.toThrow("overlay");
  });
});
