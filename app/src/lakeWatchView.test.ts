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
    expect(h.textContent).toBe("Between SUPARCO's 16 Jun image and its 5 Aug update, NISAR made 49 valid looks across 7 lakes.");
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
      const text = root.querySelector<HTMLElement>('[data-role="lw-detail"]')!.textContent!;
      expect(text).toContain(`Fixture reason for ${id}.`);
      expect(text).not.toMatch(/\d\s*km²/);
      expect(text).not.toContain("0 km²");
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
