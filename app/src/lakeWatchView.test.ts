// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { findBannedClaims } from "./content";
import { fixtureLakes } from "./fixtures";
import { sortLakes, type Lake, type LakesFile } from "./lakes";
import { createLakeWatchView, lakeChartData, type LakeChartData } from "./lakeWatchView";

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
    expect(text).toContain("PMD and NDMA");
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
