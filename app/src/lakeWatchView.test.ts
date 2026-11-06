// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { findBannedClaims } from "./content";
import { fixtureLakes, requestedLake, withRequestedLake } from "./fixtures";
import { sortLakes, type Lake, type LakesFile } from "./lakes";
import { createLakeWatchView, lakeChartData, openingLake, type LakeChartData } from "./lakeWatchView";

function setup(file: LakesFile | null = fixtureLakes, extra: Partial<Parameters<typeof createLakeWatchView>[1]> = {}) {
  const root = document.createElement("div");
  document.body.append(root);
  const charts: LakeChartData[] = [];
  const picks: string[] = [];
  const view = createLakeWatchView(root, {
    lakes: file,
    createChart: (_el, data) => {
      charts.push(data);
      return { destroy() {} };
    },
    createLocator: (_el, _lakes, _onPick) => ({ highlight: (id) => void picks.push(id), destroy() {} }),
    ...extra,
  });
  return { root, view, charts, picks };
}

afterEach(() => {
  document.body.innerHTML = "";
});

const rowIds = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>("[data-lake-id]")].map((e) => e.dataset.lakeId);

describe("Lake Watch", () => {
  test("test_opens_on_the_first_lake_with_pictures", () => {
    const { root, picks } = setup();
    const first = openingLake(fixtureLakes.lakes);
    const area = (l: Lake) => Math.max(-1, ...l.series.filter((p) => p.excluded === null && p.area_km2 !== null).slice(-1).map((p) => p.area_km2!));
    for (const l of fixtureLakes.lakes) expect(area(first)).toBeGreaterThanOrEqual(area(l));
    expect(root.querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe(first.id);
    expect(root.querySelector(".lw-title")?.textContent).toBe(first.name);
    expect(picks).toContain(first.id);
  });

  test("test_list_rows_carry_a_radar_thumbnail", () => {
    const { root } = setup();
    for (const lake of fixtureLakes.lakes) {
      const t = root.querySelector(`[data-lake-id="${lake.id}"] .lw-thumb`)!;
      expect(t.getAttribute("aria-hidden")).toBe("true");
      const srcs = [...t.querySelectorAll("img")].map((i) => i.getAttribute("src"));
      expect(srcs).toEqual([lake.images?.latest_hh, lake.images?.water].filter(Boolean).map((x) => `data/${x}`));
      expect(t.hasAttribute("data-empty")).toBe(srcs.length === 0);
    }
  });

  test("test_lake_list_order_matches_sortLakes", () => {
    const { root } = setup();
    expect(rowIds(root)).toEqual(sortLakes(fixtureLakes.lakes).map((l) => l.id));
  });

  test("test_headline_sums_cloud_window_looks", () => {
    const { root } = setup();
    const h = root.querySelector<HTMLElement>('[data-role="lw-headline"]')!;
    expect(h.textContent).toBe("From 17 June to 4 August, while SUPARCO's updates reported cloud limiting optical imagery, NISAR made 49 valid looks across 7 lakes.");
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

  test("test_keyboard_select_with_enter", () => {
    const { root, picks } = setup();
    const row = root.querySelector<HTMLButtonElement>('[data-lake-id="stable"]')!;
    expect(row.tagName).toBe("BUTTON");
    row.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    expect(row.getAttribute("aria-pressed")).toBe("true");
    expect(root.querySelector('[data-role="lw-detail"]')!.textContent).toContain("Fixture stable");
    expect(picks).toContain("stable");
  });

  test("one chart series per track, excluded passes kept apart", () => {
    const pt = (date: string, track: string, area: number | null, excluded: string | null) => ({ date, track, area_km2: area, observable_share: 1, excluded });
    const lake: Lake = {
      ...fixtureLakes.lakes[2],
      series: [pt("2026-07-01", "156A", 1.0, null), pt("2026-07-02", "64D", 2.0, null), pt("2026-07-13", "156A", 9.0, "bright"), pt("2026-07-25", "156A", 1.1, null)],
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
    const id = fixtureLakes.lakes[1].id;
    root.querySelector<HTMLButtonElement>(`[data-lake-id="${id}"]`)!.click();
    expect(picked).toEqual([id]);
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
});

describe("Lake Watch after an accept", () => {
  test("mounts the shipped data with a 12th lake that has no pass yet, and opens that lake", async () => {
    const real = (await import("../public/data/lakes.json")).default as unknown as LakesFile;
    const frozen = (await import("./fixtures/lakes.json")).default as unknown as LakesFile;
    for (const base of [frozen, real]) {
      const file = withRequestedLake(base);
      const { root } = setup(file);
      expect(rowIds(root)).toHaveLength(base.lakes.length + 1);
      expect(rowIds(root)).toContain(requestedLake.id);
      root.querySelector<HTMLElement>(`.lw-row[data-lake-id="${requestedLake.id}"]`)!.click();
      expect(root.querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe(requestedLake.id);
      expect(root.querySelector(".lw-title")?.textContent).toBe(requestedLake.name);
      expect(root.textContent).not.toMatch(/NaN|undefined|\{\w+\}/);
      expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
      document.body.innerHTML = "";
    }
    expect(withRequestedLake(frozen).lakes).toHaveLength(12);
  });
});
