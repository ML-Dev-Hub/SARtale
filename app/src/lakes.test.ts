import { afterEach, describe, expect, test, vi } from "vitest";
import { fixtureLakes, frozenFixture } from "./fixtures";
import realLakes from "../public/data/lakes.json";
import frozenLakes from "./frozen/lakes.json";
import { droppedLine, isLake, isLakesFile } from "./lakes";
import { findBannedClaims } from "./content";
import { absenceLine, cloudHeadline, FROZEN_AREA, freezeFacts, freezeHeadline, frozenAreaLine, hasLakeNow, isFrozen, isTrendPass, lakeTokens, mayBeForming, loadLakes, methodLimits, opticalCheckSentence, opticalOverlapPhrase, processingVersions, sortLakes, statusSentence, STATUS_ORDER, watchList, type LakeCheck, type LakesFile } from "./lakes";

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
  test("asks the server each time, so a weekly update shows on the next load", async () => {
    const fetchFn = vi.fn(async () => new Response(JSON.stringify(fixtureLakes))) as unknown as typeof fetch;
    await loadLakes("data/lakes.json", fetchFn);
    expect(fetchFn).toHaveBeenCalledWith("data/lakes.json", expect.objectContaining({ cache: "no-cache" }));
  });

  test("R01: gives up after the timeout instead of waiting forever", async () => {
    const stall = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as unknown as typeof fetch;
    expect(await loadLakes("data/lakes.json", stall, 20)).toBeNull();
  });

  test("C09: a file whose shape the views cannot draw takes the no-data path", async () => {
    const bad = [
      { lakes: [{ id: "x", status: {} }], checks: [] },
      { ...fixtureLakes, constants: { ...fixtureLakes.constants, change_factor: "2" } },
      { ...fixtureLakes, cloud_window: ["2026-06-17"] },
      { ...fixtureLakes, lakes: "x" },
      { ...fixtureLakes, checks: null },
    ];
    for (const b of bad) {
      vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => b })));
      expect(await loadLakes("data/lakes.json"), JSON.stringify(b).slice(0, 80)).toBeNull();
    }
  });

  test("M6: a lake the page cannot read is dropped and named; the other lakes stay", async () => {
    const [first, ...rest] = fixtureLakes.lakes;
    const cases = [
      { ...first, status: { ...first.status, status: "Alert level 2" } }, // a status from a newer pipeline
      { ...first, lon: null },
      { ...first, series: [{ date: "x", track: "1A" }] },
    ];
    for (const broken of cases) {
      const file = { ...fixtureLakes, lakes: [broken, ...rest] };
      vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => file })));
      const out = await loadLakes("data/lakes.json");
      expect(out, JSON.stringify(broken).slice(0, 80)).not.toBeNull();
      expect(out!.lakes.map((l) => l.id)).toEqual(rest.map((l) => l.id));
      expect(out!.dropped_lakes).toEqual([first.name]);
      expect(droppedLine(out!)).toBe(`1 site in the data (${first.name}) could not be shown by this version of the page. Reload the page to see it.`);
    }
  });

  test("C09: the shipped and the frozen lakes.json pass the check, every lake included", () => {
    expect(isLakesFile(realLakes)).toBe(true);
    expect(isLakesFile(frozenLakes)).toBe(true);
    expect(realLakes.lakes.every(isLake)).toBe(true);
    expect(frozenLakes.lakes.every(isLake)).toBe(true);
  });

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
    expect(STATUS_ORDER).toEqual([
      "Lake may be forming", "Growing", "Shrinking", "Change not confirmed yet", "Frozen (likely)", "Frozen (seen by Sentinel-2)", "Break-up likely", "Not seen this pass", "Stable", "Not enough NISAR looks yet", "Not observable", "No lake now",
    ]);
  });
  test("frozen lakes sort after Change not confirmed yet and before Not seen this pass and Stable", () => {
    const lakes = [...fixtureLakes.lakes, frozenFixture("ice", "Frozen (likely)"), frozenFixture("ice-s2", "Frozen (seen by Sentinel-2)"), frozenFixture("thaw", "Break-up likely")];
    const ids = sortLakes(lakes).map((l) => l.id);
    expect(ids).toEqual(["grow-new", "grow-old", "shrink", "ice", "ice-s2", "thaw", "stable", "few", "hidden", "control"]);
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
  test("an unconfirmed change gives its numbers and says it waits for a second pass on the new version", () => {
    const lake = { ...by("grow-new"), status: { ...by("grow-new").status, status: "Change not confirmed yet" as const, track: "084A",
      change_km2: 0.065, noise_km2: 0.016, latest_date: "2026-10-30", new_crid: "P05036" } };
    expect(statusSentence(lake, 2)).toBe(
      "Change not confirmed yet: +0.065 km² since earlier 084A passes (noise ±0.016 km²; change must exceed 2× noise), 9 looks, latest 30 Oct 2026; first pass on NISAR processing version P05036, so the change waits for a second pass on that version",
    );
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

describe("sites with no lake now", () => {
  const file = (): LakesFile => ({
    ...fixtureLakes,
    lakes: fixtureLakes.lakes.map((l) =>
      l.id === "hidden" ? { ...l, lake_state: "no_lake" as const, status: { ...l.status, status: "No lake now" as const } } : l,
    ),
  });

  test("are left out of the lake count and the cloud-window looks, and named in the list", () => {
    const f = file();
    const t = lakeTokens(f);
    expect(t.site_count).toBe("7");
    expect(t.lake_count).toBe("6");
    expect(t.cloud_looks).toBe(String(6 * 7));
    expect(t.cloud_lakes).toBe("6");
    expect(t.watch_list).toBe("6 lakes and 1 site with no lake now");
    expect(watchList(fixtureLakes)).toBe("7 lakes");
    expect(cloudHeadline(f)).toContain("NISAR made 42 valid looks across 6 lakes.");
  });

  test("carry the dated Sentinel-2 check, and water in it makes a site where a lake may be forming", () => {
    const f = file();
    const hidden = f.lakes.find((l) => l.id === "hidden")!;
    const dry = { ...hidden, absence_checked: { date: "2026-08-17", s2_id: "S2B_X", water_share: 0.0004, water_km2: 0.001, zone_valid_share: 1, checked: "2026-11-11" } };
    expect(absenceLine(dry)).toBe("Last checked 17 Aug 2026 with Sentinel-2 (S2B_X): water on 0.04% of the lake zone.");
    expect(absenceLine({ ...hidden, absence_checked: null })).toBeNull();
    // I1/I2: no clear, snow-free view since: said, so an old view never reads as a recent check
    const stale = { ...hidden, absence_checked: { ...dry.absence_checked, snow_share: 0, searched: "2026-11-12", no_view_since: true } };
    expect(absenceLine(stale)).toBe("Last checked 17 Aug 2026 with Sentinel-2 (S2B_X): water on 0.04% of the lake zone; no clear, snow-free Sentinel-2 view of the zone since (searched to 12 Nov 2026).");
    const wet = { ...dry, lake_state: "lake_forming_check" as const, status: { ...hidden.status, status: "Lake may be forming" as const } };
    expect(hasLakeNow(wet) || !mayBeForming(wet)).toBe(false);
    const g = { ...f, lakes: f.lakes.map((l) => (l.id === "hidden" ? wet : l)) };
    expect(watchList(g)).toBe("6 lakes and 1 site where a lake may be forming");
    expect(sortLakes(g.lakes)[0].id).toBe("hidden");
    const both = { ...g, lakes: [...g.lakes, { ...dry, id: "dry" }] };
    expect(watchList(both)).toBe("6 lakes, 1 site with no lake now and 1 site where a lake may be forming");
  });

  test("sort after every other status", () => {
    expect(sortLakes(file().lakes).map((l) => l.id).slice(-2)).toEqual(["hidden", "control"]);
  });

  test("say why in the status sentence, without an area", () => {
    const l = { ...file().lakes[1], status: { ...file().lakes[1].status, reason: "No lake in recent imagery: a dry basin. SARtale keeps the site to watch for a lake forming.", latest_date: "2026-11-04" } };
    expect(statusSentence(l, 2)).toBe("No lake now: No lake in recent imagery: a dry basin. SARtale keeps the site to watch for a lake forming., latest 4 Nov 2026");
  });
});

describe("opticalOverlapPhrase", () => {
  const row = (iou: number): LakeCheck => ({ lake: "x", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "S2", days_apart: 0, s2_window_cloud_pct: 0, scope: "zone", radar_km2: 0.1, optical_km2: 0.1, area_error_pct: 0, iou, zone_valid_share: 1, window_radar_km2: 0.1, window_optical_km2: 0.1, window_area_error_pct: 0, window_iou: 0.1 });
  test("is worded from the IoU values", () => {
    expect(opticalOverlapPhrase([row(0.02), row(0.3)])).toBe("overlapped optical water poorly at every lake checked (IoU 0.02–0.3)");
    expect(opticalOverlapPhrase([row(0.05), row(0.46), row(0.61)])).toBe("overlapped optical water unevenly across the 3 lakes checked (IoU 0.05–0.61)");
    expect(opticalOverlapPhrase([row(0.7), row(0.8)])).toBe("overlapped optical water with IoU 0.7–0.8 across the 2 lakes checked");
    expect(opticalOverlapPhrase([])).toBeNull();
  });
});

describe("frozen lakes", () => {
  test("an older lakes.json without freeze fields still loads, every lake kept", async () => {
    for (const l of (frozenLakes as unknown as LakesFile).lakes) {
      expect(l.freeze).toBeUndefined();
      expect(l.series.some((p) => "frozen" in p)).toBe(false);
    }
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => frozenLakes })));
    const out = await loadLakes("data/lakes.json");
    expect(out?.lakes.length).toBe(frozenLakes.lakes.length);
    expect(out?.dropped_lakes).toBeUndefined();
  });

  test("a lake with a freeze object and frozen passes is valid; a broken freeze object drops only that lake", () => {
    const ice = frozenFixture("ice");
    expect(isLake(ice)).toBe(true);
    expect(isLake({ ...ice, freeze: null })).toBe(true);
    expect(isLake({ ...ice, freeze: { state: 3, reason: "x" } })).toBe(false);
    expect(isLake({ ...ice, freeze: { ...ice.freeze, s2: { date: "8 Nov" } } })).toBe(false);
    expect(isLake({ ...ice, series: [{ ...ice.series[0], frozen: "yes" }] })).toBe(false);
  });

  test("frozen passes keep their area but are not trend passes", () => {
    const ice = frozenFixture("ice");
    const frozen = ice.series.filter((p) => p.frozen);
    expect(frozen.map((p) => p.area_km2)).toEqual([0.225, 0.226]);
    expect(frozen.every((p) => !isTrendPass(p, 0.5))).toBe(true);
    expect(ice.series.filter((p) => isTrendPass(p, 0.5))).toHaveLength(5);
  });

  test("the frozen statuses: no change figures, the reason and the Ice state", () => {
    const ice = frozenFixture("ice");
    expect(isFrozen(ice)).toBe(true);
    expect(isFrozen(fixtureLakes.lakes[2])).toBe(false);
    expect(statusSentence(ice, 2)).toBe("Frozen (likely): Probably frozen since 18 Oct 2026, when the air at the lake met the freeze rule., latest 30 Oct 2026");
    expect(frozenAreaLine(ice)).toBe(`Latest reading 0.226 km² on 30 Oct 2026 (084A): ${FROZEN_AREA}.`);
    expect(FROZEN_AREA).toBe("not an open-water measurement while frozen");
    expect(frozenAreaLine(fixtureLakes.lakes[2])).toBeNull();
  });

  test("the freeze card's facts: temperature run, degree-days, Sentinel-2 evidence or none clear, frozen passes", () => {
    const facts = freezeFacts(frozenFixture("ice"));
    expect(facts[0]).toBe("Air temperature (NASA POWER to 10 Nov 2026, adjusted to the lake's height of 4,188 m): daily mean below 0 °C for 30 days in a row; 7-day mean −5.8 °C.");
    expect(facts[1]).toBe("Freezing degree-days since 1 Sep: 150.");
    expect(facts[2]).toBe("Sentinel-2: none clear over the lake zone in the last 7 days.");
    expect(facts[3]).toBe(`2 passes were taken while the lake was probably frozen: greyed below, ${FROZEN_AREA}, and left out of the comparison.`);
    const seen = freezeFacts(frozenFixture("ice", "Frozen (seen by Sentinel-2)"));
    expect(seen[2]).toBe("Sentinel-2 8 Nov 2026 (S2A_43SCV_20261108_0_L2A): snow or ice on 94% and water on 0% of the lake zone seen clear.");
    expect(freezeHeadline(frozenFixture("ice").freeze!)).toBe("Probably frozen since 18 Oct 2026 (air temperature)");
    expect(freezeHeadline(frozenFixture("ice", "Frozen (seen by Sentinel-2)").freeze!)).toBe("Frozen since 18 Oct 2026: snow or ice seen by Sentinel-2");
    expect(freezeHeadline({ ...frozenFixture("ice").freeze!, state: "open", since: null })).toBe("Not frozen by the air-temperature rule");
    expect(freezeHeadline({ ...frozenFixture("ice").freeze!, state: "not_assessed" })).toBe("Freeze not assessed");
    const notCold = freezeFacts({ ...frozenFixture("ice"), freeze: { ...frozenFixture("ice").freeze!, state: "open", s2_searched: false } });
    expect(notCold).toContain("Sentinel-2: not checked (the lake is not cold).");
    for (const t of [...facts, ...seen]) expect(findBannedClaims(t)).toEqual([]);
  });

  test("the freeze rule's figures come from lakes.json constants, and an older file has none", () => {
    const c = { ...fixtureLakes.constants, lapse_c_per_km: -6.5, freeze_cold_run_days: 7, freeze_fdd: 30, breakup_warm_run_days: 7, thaw_warm_run_days: 14, breakup_contrast_db: 2, breakup_dark_drop: 0.3, s2_frozen_snow_share: 0.8, s2_open_water_share: 0.5, s2_freeze_days: 7, s2_freeze_clear: 0.8, power_stale_days: 10 };
    const t = lakeTokens({ ...fixtureLakes, constants: c });
    expect([t.lapse_c_per_km, t.freeze_cold_run_days, t.freeze_fdd, t.s2_frozen_pct, t.s2_open_pct]).toEqual(["6.5", "7", "30", "80", "50"]);
    expect(lakeTokens(fixtureLakes).freeze_fdd).toBeUndefined();
  });
});
