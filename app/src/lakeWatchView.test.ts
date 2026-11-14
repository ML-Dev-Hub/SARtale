// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { findBannedClaims } from "./content";
import { fixtureLakes, frozenFixture, olderFile, requestedLake, withRequestedLake } from "./fixtures";
import { isLakesFile, keepValidLakes, splitChecks, type Lake, type LakesFile } from "./lakes";
import { checkLine, createLakeWatchView, FORMING_LAYER, FORMING_NO_LAYER, lakeChartData, openingLake, type LakeChartData } from "./lakeWatchView";

function setup(file: LakesFile | null = fixtureLakes, extra: Partial<Parameters<typeof createLakeWatchView>[1]> = {}) {
  const root = document.createElement("div");
  document.body.append(root);
  const charts: LakeChartData[] = [];
  const view = createLakeWatchView(root, {
    lakes: file,
    createChart: (_el, data) => {
      charts.push(data);
      return { destroy() {} };
    },
    ...extra,
  });
  return { root, view, charts };
}

afterEach(() => {
  document.body.innerHTML = "";
});

/** The status chip in the lake's panel. The list moved to the overview (overview/overviewView.test.ts). */
const detailChip = (root: HTMLElement) => root.querySelector<HTMLElement>('[data-role="lw-detail"] .lw-chip')!;

describe("Lake Watch", () => {
  test("test_opens_on_the_first_lake_with_pictures", () => {
    const { root } = setup();
    const first = openingLake(fixtureLakes.lakes);
    const area = (l: Lake) => Math.max(-1, ...l.series.filter((p) => p.excluded === null && p.area_km2 !== null).slice(-1).map((p) => p.area_km2!));
    for (const l of fixtureLakes.lakes) expect(area(first)).toBeGreaterThanOrEqual(area(l));
    expect(root.querySelector(".lw-title")?.textContent).toBe(first.name);
  });

  test("test_headline_sums_cloud_window_looks", () => {
    const { root } = setup();
    const h = root.querySelector<HTMLElement>('[data-role="lw-headline"]')!;
    expect(h.textContent).toBe("From 17 June to 4 August, NISAR made 49 valid looks across 7 lakes. SUPARCO's updates reported that cloud limited optical imagery in these weeks.");
    expect(h.closest("a")?.getAttribute("href") ?? h.getAttribute("href")).toBe("#cloud-gap");
  });

  test("test_select_shows_coord_source_and_limits", () => {
    const lake: Lake = { ...fixtureLakes.lakes[2], id: "x", coord_source: "Fixture gazetteer", limits: ["Shadow hides the north shore."], excluded: [{ pass: "2026-07-07 156", reason: "HH 25 dB from track median" }] };
    const { root, view } = setup({ ...fixtureLakes, lakes: [lake] });
    view.select("x");
    const text = root.querySelector<HTMLElement>('[data-role="lw-detail"]')!.textContent!;
    expect(text).toContain("Coordinates: Fixture gazetteer");
    expect(text).toContain("Shadow hides the north shore.");
    expect(text).toContain("HH 25 dB from track median");
    expect(text).toContain("PMD, NDMA, GBDMA and PDMA");
  });

  test("test_not_observable_lake_has_no_area_number", () => {
    const { root, view } = setup();
    for (const id of ["hidden", "few", "control"]) {
      view.select(id);
      const detail = root.querySelector<HTMLElement>('[data-role="lw-detail"]')!.cloneNode(true) as HTMLElement;
      detail.querySelector('[data-role="lw-method-limits"]')?.remove(); // standing text quotes "0.05 km²" on purpose
      const text = detail.textContent!;
      expect(text).toContain(`Fixture reason for ${id}.`);
      expect(text).not.toMatch(/\d\s*km²/);
      expect(text).not.toContain("0 km²");
    }
  });

  test("standing method limits show for a lake with no limits of its own, and never 'None recorded'", () => {
    const { root, view } = setup({ ...fixtureLakes, notes: "Fixture build notes." });
    for (const l of fixtureLakes.lakes) {
      view.select(l.id);
      const detail = root.querySelector<HTMLElement>('[data-role="lw-detail"]')!;
      const method = detail.querySelector<HTMLElement>('[data-role="lw-method-limits"]')!;
      expect(method.textContent).toContain("Fixture build notes.");
      expect(method.textContent).toContain("Not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.");
      expect(detail.textContent).not.toContain("None recorded");
    }
  });

  test("test_view_text_has_no_banned_claims", () => {
    const { root, view } = setup();
    for (const l of fixtureLakes.lakes) view.select(l.id);
    expect(findBannedClaims(root.textContent!)).toEqual([]);
  });

  test("one chart series per track, excluded passes kept apart", () => {
    const pt = (date: string, track: string, area: number | null, excluded: string | null) => ({ date, track, area_km2: area, observable_share: 1, excluded });
    const lake: Lake = {
      ...fixtureLakes.lakes[2],
      // the producer's shape: an excluded pass has area_km2 null and keeps what it read as diagnostic_km2
      series: [pt("2026-07-01", "156A", 1.0, null), pt("2026-07-02", "64D", 2.0, null), { ...pt("2026-07-13", "156A", null, "bright"), diagnostic_km2: 9.0 }, pt("2026-07-25", "156A", 1.1, null), { ...pt("2026-07-30", "156A", null, "window has no valid HH pixels"), diagnostic_km2: null }],
    };
    const d = lakeChartData(lake);
    expect(d.series.filter((s) => !s.excluded).map((s) => s.label)).toEqual(["156A", "64D"]);
    const t156 = d.series.find((s) => s.label === "156A")!;
    expect(t156.values.filter((v) => v !== null)).toEqual([1.0, 1.1]);
    expect(d.series.find((s) => s.excluded)!.values.filter((v) => v !== null)).toEqual([9.0]);
  });

  test("test_chart_leaves_off_passes_that_saw_too_little_of_the_zone", () => {
    const pt = (date: string, area: number, share: number) => ({ date, track: "156A", area_km2: area, observable_share: share, excluded: null });
    const lake: Lake = { ...fixtureLakes.lakes[2], series: [pt("2026-07-01", 1.0, 0.9), pt("2026-07-13", 0.04, 0.06), pt("2026-07-25", 1.1, 0.5)] };
    expect(lakeChartData(lake, 0.5).series[0].values).toEqual([1.0, null, 1.1]);
    expect(lakeChartData(lake).series[0].values).toEqual([1.0, 0.04, 1.1]);
  });

  test("test_every_pass_is_listed_in_the_readings_table_with_why_it_was_not_used", () => {
    const pt = (date: string, area: number | null, share: number, excluded: string | null) => ({ date, track: "156A", area_km2: area, observable_share: share, excluded });
    const lake: Lake = {
      ...fixtureLakes.lakes[2],
      series: [pt("2026-07-25", 1.1, 0.9, null), pt("2026-07-01", 1.0, 0.1, null), pt("2026-07-13", null, 1, "window too bright")],
    };
    const { root, view } = setup({ ...fixtureLakes, lakes: [lake] });
    view.select(lake.id);
    const rows = [...root.querySelectorAll('[data-role="lw-readings"] tbody tr')].map((tr) => [...tr.children].map((td) => td.textContent));
    expect(rows.map((r) => r[0])).toEqual(["1 Jul 2026", "13 Jul 2026", "25 Jul 2026"]);
    expect(rows.map((r) => r[4])).toEqual(["Too little of the zone seen", "Left out: window too bright", "Yes"]);
    expect(rows[1][2]).toBe("–");
    expect(rows.map((r) => r[5])).toEqual(["–", "–", "–"]); // an older build has no CRID per pass
  });

  test("test_the_readings_table_names_each_pass_processing_version", () => {
    const pt = (date: string, crid: string) => ({ date, track: "156A", area_km2: 1, observable_share: 1, excluded: null, crid });
    const lake: Lake = { ...fixtureLakes.lakes[2], series: [pt("2026-10-11", "P05023"), pt("2026-11-04", "P05036")] };
    const { root, view } = setup({ ...fixtureLakes, crid: "P05023, P05036", lakes: [lake] });
    view.select(lake.id);
    const head = [...root.querySelectorAll('[data-role="lw-readings"] thead th')].map((th) => th.textContent);
    expect(head.slice(5)).toEqual(["Baseline (km²)", "z", "Level set", "Version"]);
    const rows = [...root.querySelectorAll('[data-role="lw-readings"] tbody tr')].map((tr) => [...tr.children].map((td) => td.textContent));
    expect(rows.map((r) => r[8])).toEqual(["P05023", "P05036"]);
  });

  test("test_a_check_note_shows_as_a_line_and_does_not_break_the_panel", () => {
    const lake = fixtureLakes.lakes[2];
    const { root, view } = setup({ ...fixtureLakes, checks: [], check_notes: [{ lake: lake.id, note: "no clear Sentinel-2 scene within 3 days" }] });
    view.select(lake.id);
    expect([...root.querySelectorAll(".lw-check")].map((e) => e.textContent)).toEqual(["Sentinel-2 check: no clear Sentinel-2 scene within 3 days."]);
  });

  test("test_picking_a_lake_reports_it_but_opening_on_one_does_not", () => {
    const picked: string[] = [];
    const { root } = setup(fixtureLakes, { onSelect: (id) => void picked.push(id) });
    expect(picked).toEqual([]);
    root.querySelector<HTMLButtonElement>(".lw-alert-open")!.click();
    expect(picked).toEqual(["grow-new"]);
  });

  test("the lake's page links back to the overview", () => {
    const { root } = setup();
    expect(root.querySelector('[data-role="lw-back"]')!.getAttribute("href")).toBe("#lakes");
  });

  test("too few looks hides the chart and any area number even with series points", () => {
    const pt = (date: string) => ({ date, track: "156A", area_km2: 1.234, observable_share: 1, excluded: null });
    const lake: Lake = { ...fixtureLakes.lakes.find((l) => l.id === "few")!, series: [pt("2026-07-01"), pt("2026-07-13")] };
    const { root, view, charts } = setup({ ...fixtureLakes, lakes: [lake] });
    view.select("few");
    expect(charts).toHaveLength(0);
    const detail = root.querySelector<HTMLElement>('[data-role="lw-detail"]')!.cloneNode(true) as HTMLElement;
    detail.querySelector('[data-role="lw-method-limits"]')?.remove(); // standing text quotes "0.05 km²" on purpose
    const text = detail.textContent!;
    expect(text).toContain("Fixture reason for few.");
    expect(text).not.toMatch(/\d\s*km²/);
  });

  test("every cross-check row for the lake is shown", () => {
    const row = (s2: string) => ({ lake: "stable", nisar_date: "2026-08-01", nisar_track: "156A", s2_date: s2, s2_id: "x", days_apart: 1, s2_window_cloud_pct: 5, scope: "zone", radar_km2: 1.1, optical_km2: 1.0, area_error_pct: 10, iou: 0.8, zone_valid_share: 1, window_radar_km2: 1, window_optical_km2: 1, window_area_error_pct: 0, window_iou: 0.8 });
    const { root, view } = setup({ ...fixtureLakes, checks: [row("2026-08-02"), row("2026-08-20")] });
    view.select("stable");
    const lines = [...root.querySelectorAll(".lw-check")].map((e) => e.textContent!);
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("One NISAR pass vs one Sentinel-2 scene:");
  });

  test("onBrief receives the selected lake", () => {
    const got: string[] = [];
    const { root, view } = setup(fixtureLakes, { onBrief: (l) => void got.push(l.id) });
    view.select("grow-new");
    root.querySelector<HTMLButtonElement>('[data-role="lw-brief"]')!.click();
    expect(got).toEqual(["grow-new"]);
  });

  test("images use dataUrl and a null path says so", () => {
    const lake: Lake = { ...fixtureLakes.lakes[2], id: "img", images: { latest_hh: "lakes/img_hh.png", water: null } };
    const { root, view } = setup({ ...fixtureLakes, lakes: [lake] });
    view.select("img");
    expect(root.querySelector("img")!.getAttribute("src")).toBe("data/lakes/img_hh.png");
    view.select("img");
    expect(root.textContent).toContain("No radar picture yet");
  });

  test("missing file shows the message", () => {
    const { root } = setup(null);
    expect(root.textContent).toContain("No lake data in this build");
  });

  test("M6: names the sites the page could not read, and still shows the rest", () => {
    const { root } = setup({ ...fixtureLakes, dropped_lakes: ["Future lake"] });
    const note = root.querySelector<HTMLElement>('[data-role="lw-dropped"]')!;
    expect(note.hidden).toBe(false);
    expect(note.textContent).toContain("Future lake");
    expect(note.textContent).toContain("Reload the page");
    expect(root.querySelector(".lw-title")?.textContent).toBe(openingLake(fixtureLakes.lakes).name);
    const plain = setup(fixtureLakes).root.querySelector<HTMLElement>('[data-role="lw-dropped"]')!;
    expect(plain.hidden).toBe(true);
  });
});

describe("Lake Watch after an accept", () => {
  test("mounts the shipped data with a lake that has no pass yet, and opens that lake", async () => {
    const real = splitChecks((await import("../public/data/lakes.json")).default as unknown as LakesFile);
    const frozen = (await import("./frozen/lakes.json")).default as unknown as LakesFile;
    for (const base of [frozen, real]) {
      const file = withRequestedLake(base);
      const { root, view } = setup(file);
      view.select(requestedLake.id);
      expect(root.querySelector(".lw-title")?.textContent).toBe(requestedLake.name);
      expect(root.textContent).not.toMatch(/NaN|undefined|\{\w+\}/);
      expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
      document.body.innerHTML = "";
    }
    expect(withRequestedLake(frozen).lakes).toHaveLength(12);
  });
});

describe("Lake Watch: alert levels", () => {
  const byId = (id: string) => fixtureLakes.lakes.find((l) => l.id === id)!;

  test("each level has its own chip; an Alert carries a mark as well as its colour", () => {
    const { root, view } = setup(fixtureLakes);
    const chip = (id: string) => {
      view.select(id);
      return detailChip(root);
    };
    expect(chip("grow-new").className).toContain("lw-status-alert-growing");
    expect(chip("grow-new").textContent).toBe("▲ Alert: growing");
    expect(chip("grow-new").querySelector(".lw-chip-mark")!.getAttribute("aria-hidden")).toBe("true");
    expect(chip("grow-old").className).toContain("lw-status-watch");
    expect(chip("shrink").className).toContain("lw-status-decrease-noted");
    expect(chip("stable").className).toContain("lw-status-no-change");
    expect(chip("stable").textContent).toBe("No change");
  });

  test("a banner over Lake Watch names every lake at Alert and opens it", () => {
    const picked: string[] = [];
    const { root } = setup(fixtureLakes, { onSelect: (id) => void picked.push(id) });
    const banner = root.querySelector<HTMLElement>('[data-role="lw-alert-banner"]')!;
    expect(banner.hidden).toBe(false);
    expect(banner.getAttribute("role")).toBe("alert");
    expect(banner.textContent).toContain("Alert: growing at Fixture grow-new. Alert: growing. The radar water area of Fixture grow-new rose on two passes in a row.");
    expect(banner.textContent).toContain("Official warnings come from PMD, NDMA, GBDMA and PDMA.");
    banner.querySelector<HTMLButtonElement>(".lw-alert-open")!.click();
    expect(picked).toEqual(["grow-new"]);
    expect(root.querySelector(".lw-title")!.textContent).toBe("Fixture grow-new");
    // no Alert, no banner
    const calm = setup({ ...fixtureLakes, lakes: fixtureLakes.lakes.filter((l) => l.id !== "grow-new") }).root;
    expect(calm.querySelector<HTMLElement>('[data-role="lw-alert-banner"]')!.hidden).toBe(true);
  });

  test("the message is at the top of the lake's view, before the status sentence", () => {
    const { root, view } = setup(fixtureLakes);
    for (const id of ["grow-new", "grow-old", "shrink"]) {
      view.select(id);
      const detail = root.querySelector('[data-role="lw-detail"]')!;
      const msg = detail.querySelector<HTMLElement>('[data-role="lw-message"]')!;
      expect(msg.dataset.level).toBe(byId(id).status.status);
      expect(detail.children[1]).toBe(msg); // straight after the header
      const m = byId(id).status.message!;
      expect(msg.textContent).toContain(m.title);
      expect(msg.textContent).toContain(m.what);
      expect(msg.textContent).toContain("This is not an outburst forecast.");
      expect(msg.querySelector(".lw-message-since")!.textContent).toBe(m.since);
      expect(msg.textContent).toContain("Contact GBDMA or PDMA. Official warnings come from PMD, NDMA, GBDMA and PDMA.");
      expect(findBannedClaims(msg.textContent!)).toEqual([]);
    }
    view.select("stable");
    expect(root.querySelector('[data-role="lw-message"]')).toBeNull();
  });

  test("the chart marks the passes that set a level and draws the baseline ± 2 × noise band of the status track", () => {
    const p = (date: string, area: number, extra: object = {}) => ({ date, track: "156A", area_km2: area, observable_share: 1, excluded: null, ...extra });
    const series = [p("2026-09-01", 1.0), p("2026-09-13", 1.0), p("2026-09-25", 1.0),
      p("2026-10-07", 1.01, { z: 0.5, baseline_km2: 1.0, noise_km2: 0.02, level_contrib: "No change" }),
      p("2026-10-19", 1.2, { z: 9.5, baseline_km2: 1.0, noise_km2: 0.021, level_contrib: "Watch" }),
      { date: "2026-10-24", track: "063D", area_km2: 0.5, observable_share: 1, excluded: null }];
    const lake: Lake = { ...byId("grow-old"), series };
    const data = lakeChartData(lake, 0.5, 2);
    const hi = data.series.find((s) => s.band === "hi")!;
    const lo = data.series.find((s) => s.band === "lo")!;
    const set = data.series.find((s) => s.level)!;
    expect(hi.label).toBe("Baseline ± 2 × noise (156A), upper");
    expect(hi.values).toEqual([null, null, null, 1.04, 1.042, null]);
    expect(lo.values.map((v) => (v === null ? null : Number(v.toFixed(3))))).toEqual([null, null, null, 0.96, 0.958, null]);
    expect(set.values).toEqual([null, null, null, null, 1.2, null]);
    // without a level (older builds, frozen lakes) neither is drawn
    expect(lakeChartData(olderFile().lakes[0], 0.5, 2).series.some((s) => s.band || s.level)).toBe(false);
  });
});

describe("Lake Watch: a lakes.json made before the levels", () => {
  test("still loads and shows its old status text, with no banner and no message", () => {
    const older = olderFile();
    expect(isLakesFile(older)).toBe(true);
    expect(keepValidLakes(older).lakes).toHaveLength(3);
    const { root, view } = setup(older);
    const chips = older.lakes.map((l) => {
      view.select(l.id);
      return detailChip(root).textContent;
    });
    expect(chips.sort()).toEqual(["Growing", "Shrinking", "Stable"]);
    expect(root.querySelector<HTMLElement>('[data-role="lw-alert-banner"]')!.hidden).toBe(true);
    for (const l of older.lakes) {
      view.select(l.id);
      expect(root.querySelector('[data-role="lw-message"]')).toBeNull();
    }
    // a status this page does not know, in a build that has the levels, still drops that lake only
    const bad = { ...fixtureLakes, lakes: [...fixtureLakes.lakes, { ...fixtureLakes.lakes[2], id: "odd", status: { ...fixtureLakes.lakes[2].status, status: "Growing" } }] };
    expect(keepValidLakes(bad).dropped_lakes).toEqual(["Fixture stable"]);
  });
});

describe("Lake Watch: a site with no lake now", () => {
  const series = [
    { date: "2026-07-01", track: "156A", area_km2: 0.9, observable_share: 1, excluded: null },
    { date: "2026-07-13", track: "156A", area_km2: 0.95, observable_share: 1, excluded: null },
    { date: "2026-07-25", track: "156A", area_km2: 0.97, observable_share: 1, excluded: null },
  ];
  const basin: Lake = {
    ...fixtureLakes.lakes[2],
    id: "basin",
    name: "Empty basin",
    lake_state: "no_lake",
    lake_state_source: "a dry basin",
    series,
    images: { latest_hh: "lakes/basin/latest_hh.webp", water: null, date: "2026-07-25", track: "156A" },
    status: { status: "No lake now", track: "156A", latest_date: "2026-07-25", looks: 3, change_km2: null, noise_km2: null, reason: "No lake in recent imagery: a dry basin. SARtale keeps the site to watch for a lake forming." },
  };
  const file: LakesFile = { ...fixtureLakes, lakes: [...fixtureLakes.lakes, basin] };

  test("is never the lake the view opens on, even with the most dark area", () => {
    expect(openingLake(file.lakes).id).not.toBe("basin");
  });

  test("shows its reason instead of an area chart, and says why there is no water layer", () => {
    const { root, view, charts } = setup(file);
    const before = charts.length;
    view.select("basin");
    expect(charts.length).toBe(before);
    const detail = root.querySelector('[data-role="lw-detail"]')!;
    expect(detail.querySelector(".lw-chip")?.className).toContain("lw-status-no-lake-now");
    expect(detail.textContent).toContain("SARtale keeps the site to watch for a lake forming.");
    expect(detail.textContent).toContain("No water layer: there is no lake at this site now.");
    expect(detail.textContent).not.toContain("No radar picture yet for the water pixels");
    expect(findBannedClaims(detail.textContent ?? "")).toEqual([]);
  });

  test("I3: a site where a lake may be forming says what happens next, and promises no automatic measurement", () => {
    const forming = (water: string | null): Lake => ({
      ...basin,
      lake_state: "lake_forming_check",
      images: { ...basin.images!, water },
      status: { ...basin.status, status: "Lake may be forming", reason: "Sentinel-2 on 1 Oct 2026 (S2_WET) shows water on 8.0% of the lake zone (0.250 km2), where recent imagery had no lake. A lake may be forming. Its radar dark area is shown but not yet treated as lake area; the SARtale team reviews the site to add it as a measured lake." },
    });
    for (const [water, note] of [[null, FORMING_NO_LAYER], ["lakes/basin/water.webp", FORMING_LAYER]] as const) {
      const { root, view } = setup({ ...fixtureLakes, lakes: [...fixtureLakes.lakes, forming(water)] });
      view.select("basin");
      const text = root.querySelector('[data-role="lw-detail"]')!.textContent ?? "";
      expect(text).toContain(note);
      expect(text).toContain("the SARtale team reviews the site to add it as a measured lake");
      expect(text).not.toMatch(/next NISAR pass|measures it/);
      expect(findBannedClaims(text)).toEqual([]);
    }
  });

  test("C06: its table calls the dark pixels dark area, not water, and never says a pass was used", () => {
    const { root, view } = setup(file);
    view.select("basin");
    const table = root.querySelector('[data-role="lw-readings"] table')!;
    expect(table.querySelector("caption")?.textContent).toContain("dark radar area by date and track");
    expect(table.querySelector("caption")?.textContent).not.toContain("water area");
    expect([...table.querySelectorAll("th")].map((th) => th.textContent)).toContain("Dark area (km²)");
    const used = [...table.querySelectorAll("tbody tr")].map((tr) => tr.children[4].textContent);
    expect(used).toEqual(["No: not lake water", "No: not lake water", "No: not lake water"]);
    expect(used).not.toContain("Yes");
  });
});

describe("checkLine", () => {
  const c = { lake: "x", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "S2", days_apart: 0, s2_window_cloud_pct: 1, scope: "zone", radar_km2: 2.736, optical_km2: 4.585, area_error_pct: -40, iou: 0.5, zone_valid_share: 1, window_radar_km2: 3, window_optical_km2: 4, window_area_error_pct: null, window_iou: 0.4 };
  test("names the open-water season the pair was chosen in, when the row has one", () => {
    expect(checkLine({ ...c, season: "15 Jun–30 Sep" })).toMatch(/^One NISAR pass vs one Sentinel-2 scene \(open-water season 15 Jun–30 Sep\): NISAR 2\.736 km²/);
    expect(checkLine(c)).toMatch(/^One NISAR pass vs one Sentinel-2 scene: NISAR/);
  });
});


describe("a frozen lake", () => {
  const file = (): LakesFile => ({ ...fixtureLakes, lakes: [...fixtureLakes.lakes, frozenFixture("ice"), frozenFixture("ice-s2", "Frozen (seen by Sentinel-2)")] });

  test("its panel has the frozen chip", () => {
    const { root, view } = setup(file());
    view.select("ice");
    expect(detailChip(root).className).toContain("lw-status-frozen-likely");
    expect(detailChip(root).textContent).toBe("Frozen (likely)");
    view.select("ice-s2");
    expect(detailChip(root).className).toContain("lw-status-frozen-seen-by-sentinel-2");
  });

  test("its detail shows the freeze card and greys the area with what it is not", () => {
    const { root, view } = setup(file());
    view.select("ice");
    const detail = root.querySelector('[data-role="lw-detail"]')!;
    const card = detail.querySelector('[data-role="lw-freeze"]')!;
    expect(card.querySelector("h3")?.textContent).toBe("Lake ice");
    expect(card.textContent).toContain("Probably frozen since 18 Oct 2026 (air temperature)");
    expect(card.textContent).toContain("below 0 °C for 30 days in a row");
    expect(card.textContent).toContain("Freezing degree-days since 1 Sep: 150.");
    expect(card.textContent).toContain("Sentinel-2: none clear over the lake in the last 7 days.");
    const area = detail.querySelector('[data-role="lw-frozen-area"]')!;
    expect(area.textContent).toBe("Latest reading 0.226 km² on 30 Oct 2026 (084A): not an open-water measurement while frozen.");
    expect(area.className).toBe("lw-frozen-area");
    const scope = detail.querySelector<HTMLElement>(".lw-scope")!;
    expect(scope.dataset.frozen).toBe("true");
    expect(scope.textContent).toContain("(not an open-water measurement while frozen)");
    expect(detail.querySelector(".lw-sentence-big")?.textContent).toMatch(/^Frozen \(likely\): Probably frozen since 18 Oct 2026/);
    expect(findBannedClaims(detail.textContent ?? "")).toEqual([]);
  });

  test("its frozen passes are greyed in the chart and the table, and left out of the track lines", () => {
    const { root, view, charts } = setup(file());
    view.select("ice");
    const data = charts[charts.length - 1];
    const ice = data.series.find((s) => s.frozen)!;
    expect(ice.label).toBe("Frozen passes (not open water)");
    expect(ice.values.filter((v) => v !== null)).toEqual([0.225, 0.226]);
    const track = data.series.find((s) => s.label === "084A")!;
    expect(track.values.filter((v) => v !== null)).toHaveLength(5);
    expect(root.querySelector('[data-role="lw-detail"]')!.textContent).toContain("Grey markers are passes taken while the lake was probably frozen");
    const rows = [...root.querySelectorAll<HTMLTableRowElement>('[data-role="lw-readings"] tbody tr')];
    const frozen = rows.filter((r) => r.dataset.frozen === "true");
    expect(frozen).toHaveLength(2);
    expect(frozen.every((r) => r.className === "lw-frozen")).toBe(true);
    expect(frozen[0].children[2].textContent).toBe("0.225");
    expect(frozen[0].children[4].textContent).toBe("No: frozen, not an open-water measurement while frozen");
    expect(rows.filter((r) => r.children[4].textContent === "Yes")).toHaveLength(5);
  });

  test("a lake that is not frozen shows its freeze check as a note and no greyed area", () => {
    const open = { ...frozenFixture("warm"), status: fixtureLakes.lakes.find((l) => l.id === "stable")!.status, series: [] };
    open.freeze = { ...open.freeze!, state: "open", since: null, cold_run_days: 0, warm_run_days: 5, s2_searched: false, frozen_passes: 0, reason: "Not frozen by the freeze rule (7 days in a row below 0 °C and 30 freezing degree-days since 1 Sep), so the usual assessment applies. Air temperature alone cannot show that the lake is open." };
    const { root, view } = setup({ ...fixtureLakes, lakes: [...fixtureLakes.lakes, open] });
    view.select("warm");
    const card = root.querySelector('[data-role="lw-freeze"]')!;
    expect(card.textContent).toContain("Not frozen by the air-temperature rule");
    expect(card.textContent).toContain("Air temperature alone cannot show that the lake is open.");
    expect(card.textContent).toContain("Sentinel-2: not checked (the lake is not cold).");
    expect(root.querySelector('[data-role="lw-frozen-area"]')).toBeNull();
  });

  test("an older lakes.json without freeze fields shows no freeze card", async () => {
    const old = (await import("./frozen/lakes.json")).default as unknown as LakesFile;
    const { root, view } = setup(old);
    for (const l of old.lakes) {
      view.select(l.id);
      expect(root.querySelector('[data-role="lw-freeze"]')).toBeNull();
    }
  });
});


describe("a frozen lake's radar picture", () => {
  test("M8: the water layer is hidden while frozen and the caption says why", () => {
    const ice = frozenFixture("ice", "Frozen (likely)", { images: { latest_hh: "lakes/ice/latest_hh.webp", water: "lakes/ice/water.webp", date: "2026-10-30", track: "084A" } });
    const { root, view } = setup({ ...fixtureLakes, lakes: [...fixtureLakes.lakes, ice] });
    view.select("ice");
    const detail = root.querySelector('[data-role="lw-detail"]')!;
    expect(detail.querySelector(".lw-img-water")).toBeNull();
    expect(detail.querySelector(".lw-img-hh")).not.toBeNull();
    expect(detail.querySelector('[data-role="lw-water-hidden"]')?.textContent).toBe("Water layer hidden: not an open-water measurement while frozen.");
    // an open lake keeps its layer, unless its pictured pass was itself taken while frozen (review m2)
    const stable = fixtureLakes.lakes.find((l) => l.id === "stable")!.status;
    const open = { ...ice, id: "warm", status: stable, images: { ...ice.images!, date: "2026-09-18", track: "084A" } };
    const flaggedPicture = { ...ice, id: "edge", status: stable };
    const two = setup({ ...fixtureLakes, lakes: [...fixtureLakes.lakes, open, flaggedPicture] });
    two.view.select("warm");
    expect(two.root.querySelector('[data-role="lw-detail"] .lw-img-water')).not.toBeNull();
    two.view.select("edge");
    expect(two.root.querySelector('[data-role="lw-detail"] .lw-img-water')).toBeNull();
    expect(two.root.querySelector('[data-role="lw-water-hidden"]')).not.toBeNull();
  });
});
