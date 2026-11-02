import { afterEach, describe, expect, test, vi } from "vitest";
import { fixtureLakes } from "./fixtures";
import { loadLakes, sortLakes, statusSentence, STATUS_ORDER } from "./lakes";

afterEach(() => vi.unstubAllGlobals());

describe("loadLakes", () => {
  test("test_loadLakes_returns_null_on_404", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 404 })));
    expect(await loadLakes("data/lakes.json")).toBeNull();
  });
  test("test_loadLakes_returns_null_on_bad_json", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => { throw new SyntaxError("bad"); } })));
    expect(await loadLakes("data/lakes.json")).toBeNull();
  });
  test("returns the file when it parses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => fixtureLakes })));
    expect((await loadLakes("data/lakes.json"))?.lakes.length).toBe(fixtureLakes.lakes.length);
  });
  test("returns null when the shape is wrong", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ lakes: "x" }) })));
    expect(await loadLakes("data/lakes.json")).toBeNull();
  });
});

describe("sortLakes", () => {
  test("test_sortLakes_puts_growing_first_and_controls_last", () => {
    const ids = sortLakes(fixtureLakes.lakes).map((l) => l.id);
    expect(ids).toEqual(["grow-new", "grow-old", "shrink", "stable", "few", "hidden", "control"]);
  });
  test("status order is the documented one", () => {
    expect(STATUS_ORDER[0]).toBe("Growing");
    expect(STATUS_ORDER[STATUS_ORDER.length - 1]).toBe("Not observable");
  });
  test("does not mutate its input", () => {
    const copy = [...fixtureLakes.lakes];
    sortLakes(fixtureLakes.lakes);
    expect(fixtureLakes.lakes).toEqual(copy);
  });
});

describe("statusSentence", () => {
  const by = (id: string) => fixtureLakes.lakes.find((l) => l.id === id)!;
  test("test_statusSentence_includes_date_looks_and_noise", () => {
    expect(statusSentence(by("grow-new"))).toBe(
      "Growing: +0.031 km² since earlier 156A passes (noise ±0.005 km²), 9 looks, latest 23 Oct 2026",
    );
    const s = statusSentence(by("shrink"));
    expect(s).toContain("-0.040 km²");
  });
  test("test_statusSentence_point_only_lake_says_search_window", () => {
    expect(statusSentence(by("shrink"))).toContain("in the search window");
    expect(statusSentence(by("grow-new"))).not.toContain("search window");
  });
  test("null-change statuses use the reason and never show 0 km²", () => {
    for (const id of ["few", "hidden", "control"]) {
      const s = statusSentence(by(id));
      expect(s).toContain(by(id).status.reason);
      expect(s).not.toMatch(/\b0 km²/);
    }
  });
});
