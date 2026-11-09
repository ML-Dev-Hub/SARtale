import { afterEach, describe, expect, test, vi } from "vitest";
import { fixtureLakes } from "./fixtures";
import { lakeTokens, loadLakes, methodLimits, opticalCheckSentence, processingVersions, sortLakes, statusSentence, STATUS_ORDER } from "./lakes";

afterEach(() => vi.unstubAllGlobals());

describe("processingVersions", () => {
  test("names one processing version, or several joined with and", () => {
    expect(processingVersions("P05023")).toBe("processing version P05023");
    expect(processingVersions("P05023, P05036")).toBe("processing versions P05023 and P05036");
    expect(processingVersions("P05023, P05036, P05040")).toBe("processing versions P05023, P05036 and P05040");
  });

  test("is the token the copy quotes", () => {
    expect(lakeTokens({ ...fixtureLakes, crid: "P05023, P05036" }).processing_versions).toBe("processing versions P05023 and P05036");
  });
});

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
  test("accepts a lake whose images and bounds are null", async () => {
    const lake = { ...fixtureLakes.lakes[0], images: { latest_hh: null, water: null }, bounds: null };
    const file = { ...fixtureLakes, lakes: [lake] };
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => file })));
    const out = await loadLakes("data/lakes.json");
    expect(out?.lakes[0].images).toEqual({ latest_hh: null, water: null });
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
    expect(statusSentence(by("grow-new"), 2)).toBe(
      "Growing: +0.031 km² since earlier 156A passes (noise ±0.005 km²; change must exceed 2× noise), 9 looks, latest 23 Oct 2026",
    );
    const s = statusSentence(by("shrink"), 2);
    expect(s).toContain("-0.040 km²");
  });
  test("test_statusSentence_point_only_lake_says_search_window", () => {
    expect(statusSentence(by("shrink"), 2)).toContain("in the search window");
    expect(statusSentence(by("grow-new"), 2)).not.toContain("search window");
  });
  test("null-change statuses use the reason and never show 0 km²", () => {
    for (const id of ["few", "hidden", "control"]) {
      const s = statusSentence(by(id), 2);
      expect(s).toContain(by(id).status.reason);
      expect(s).not.toMatch(/\b0 km²/);
      expect(s).not.toContain("search window");
    }
  });
  test("a change that rounds to zero never prints as -0.000", () => {
    const l = by("stable");
    const s = statusSentence({ ...l, status: { ...l.status, change_km2: -0.0002 } }, 2);
    expect(s).toContain(" 0.000 km²");
    expect(s).not.toContain("-0.000");
  });
  test("uses the change factor it is given", () => {
    expect(statusSentence(by("grow-new"), 3)).toContain("change must exceed 3× noise");
  });
});

describe("sortLakes tie-break", () => {
  test("same status and date fall back to name order", () => {
    const l = fixtureLakes.lakes.find((x) => x.id === "stable")!;
    const ids = sortLakes([{ ...l, id: "z", name: "Zeta" }, { ...l, id: "a", name: "Alpha" }, { ...l, id: "m", name: "Mu" }]).map((x) => x.id);
    expect(ids).toEqual(["a", "m", "z"]);
  });
});

describe("methodLimits", () => {
  const mk = (iou: number | null, days = 0) => ({ lake: "x", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "s", days_apart: days, s2_window_cloud_pct: 1, scope: "w", radar_km2: 0.1, optical_km2: 0.2, area_error_pct: 1, iou, zone_valid_share: 1, window_radar_km2: 0, window_optical_km2: 0, window_area_error_pct: null, window_iou: null });
  test("notes, the not-validated list and an IoU range from the checks", () => {
    const out = methodLimits({ ...fixtureLakes, notes: "N.", checks: [mk(0.0049), mk(0.1137), mk(null)] });
    expect(out).toEqual([
      "N.",
      "Not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.",
      "In a same-day check against Sentinel-2, radar water overlapped optical water poorly at every lake checked (IoU 0.005–0.11); treat areas as indicative.",
    ]);
    expect(opticalCheckSentence([mk(0.0138, 3)])).toBe("In checks up to 3 days apart against Sentinel-2, radar water overlapped optical water poorly at every lake checked (IoU 0.014); treat areas as indicative.");
    expect(opticalCheckSentence([mk(null)])).toBeNull();
  });
});

describe("splitChecks", () => {
  test("test_unmeasured_check_rows_move_to_check_notes", async () => {
    const { splitChecks } = await import("./lakes");
    const { fixtureLakes } = await import("./fixtures");
    const measured = { lake: "passu", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "S2", days_apart: 0, s2_window_cloud_pct: 0, scope: "zone", radar_km2: 0.05, optical_km2: 0.2, area_error_pct: null, iou: 0.03, zone_valid_share: 1, window_radar_km2: 0.1, window_optical_km2: 0.3, window_area_error_pct: null, window_iou: 0.02 };
    const raw = { ...fixtureLakes, checks: [measured, { lake: "attabad", note: "no clear Sentinel-2 scene within 3 days" }, { lake: "x" }] } as unknown as typeof fixtureLakes;
    const out = splitChecks(raw);
    expect(out.checks).toEqual([measured]);
    expect(out.check_notes).toEqual([{ lake: "attabad", note: "no clear Sentinel-2 scene within 3 days" }]);
  });
});
