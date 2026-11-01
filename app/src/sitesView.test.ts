// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { PLACEHOLDER } from "./content";
import { changeManifest, fixtureManifest } from "./fixtures";
import { createSitesView, type ChartData, type ChartFactory } from "./sitesView";
import type { Site } from "./types";

const mk = (id: string, name: string, hv: (number | null)[]): Site => ({
  id,
  name,
  lon: 0.3,
  lat: 0.4,
  role: "demo",
  stack: fixtureManifest.stack,
  crid: fixtureManifest.crid,
  series: ["2026-07-02", "2026-07-14", "2026-07-26"].map((date, i) => ({
    date,
    hh_db: -10 - i,
    hv_db: hv[i],
    valid_fraction: hv[i] === null ? 0 : 1,
  })),
});
const sites = [mk("demo-a", "Demo site A", [-18, null, -17]), mk("demo-b", "Demo site B", [-19, -19, -19])];

function setup(list: Site[] | null = sites) {
  const root = document.createElement("div");
  document.body.append(root);
  const charts: { data: ChartData; destroyed: boolean }[] = [];
  const createChart: ChartFactory = (_el, data) => {
    const rec = { data, destroyed: false };
    charts.push(rec);
    return { destroy: () => (rec.destroyed = true) };
  };
  const view = createSitesView(root, { sites: list, manifest: fixtureManifest, createChart });
  const $ = <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { root, view, charts, $ };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("change scores on a card", () => {
  const scored: Site = {
    ...mk("demo-a", "Demo site A", [-18, -18, -17]),
    step: { date: "2026-08-19", previous_date: "2026-07-26", hh_db: -8.14, hv_db: -5.26, stability: 5.7, flagged: true, map_share: 0.7 },
    series: [
      { date: "2026-07-26", hh_db: -10, hv_db: -18, valid_fraction: 1, change_score: 1.26 },
      { date: "2026-07-02", hh_db: -10, hv_db: -18, valid_fraction: 1, change_score: null },
      { date: "2026-07-14", hh_db: -10, hv_db: -18, valid_fraction: 1, change_score: 5.39 },
    ],
  };
  function open(manifest: Parameters<typeof createSitesView>[1]["manifest"]) {
    const root = document.createElement("div");
    document.body.append(root);
    const view = createSitesView(root, { sites: [scored], manifest });
    view.select("demo-a");
    return <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  }

  test("each date's score sits by the curve, in date order, with exclusions and flags in words", () => {
    const $ = open(changeManifest);
    const t = $("card-change").textContent ?? "";
    expect($("card-change").hidden).toBe(false);
    expect(t).toContain("Unusual dates score:");
    expect(t).toContain("3.5 or more is highlighted");
    expect(t).toContain("2 Jul Excluded from change analysis, 14 Jul 5.4 (flagged date), 26 Jul 1.3.");
  });

  test("the step sits by the curve, with its size, dates and whether it passes", () => {
    const t = open(changeManifest)("card-step").textContent ?? "";
    expect(t).toContain("Step: HH -8.1 dB, HV -5.3 dB between 26 Jul and 19 Aug.");
    expect(t).toContain("It passes the test the map uses.");
    expect(t).toContain("70% of map pixels here are flagged.");
  });

  test("a step that does not pass says so", () => {
    const quiet = { ...scored, step: { ...scored.step!, flagged: false, map_share: 0 } };
    const root = document.createElement("div");
    document.body.append(root);
    createSitesView(root, { sites: [quiet], manifest: changeManifest }).select("demo-a");
    const t = root.querySelector('[data-role="card-step"]')!.textContent ?? "";
    expect(t).toContain("Largest step:");
    expect(t).toContain("does not pass");
  });

  test("the values table carries the score", () => {
    const $ = open(changeManifest);
    const rows = [...$("card-table").querySelectorAll("tbody tr")].map((tr) => tr.lastElementChild?.textContent);
    expect(rows).toEqual(["Excluded from change analysis", "5.4 (flagged date)", "1.3"]);
  });

  test("a build with no change layer shows no score line", () => {
    const $ = open(fixtureManifest);
    expect($("card-change").hidden).toBe(true);
    expect($("card-step").hidden).toBe(true);
  });
});

describe("sites view", () => {
  test("shows a plain No site curves yet state when there is no sites file", () => {
    const { $, root } = setup(null);
    expect($("empty").hidden).toBe(false);
    expect($("empty").textContent).toBe("No site curves yet");
    expect(root.querySelectorAll("[data-site]").length).toBe(0);
    expect($("card").hidden).toBe(true);
  });

  test("an empty list is also the no-curves state", () => {
    const { $ } = setup([]);
    expect($("empty").hidden).toBe(false);
  });

  test("lists each site as a button and starts with no card open", () => {
    const { $, root } = setup();
    expect($("empty").hidden).toBe(true);
    const buttons = [...root.querySelectorAll<HTMLButtonElement>("[data-site]")];
    expect(buttons.map((b) => b.textContent)).toEqual([
      expect.stringContaining("Demo site A"),
      expect.stringContaining("Demo site B"),
    ]);
    expect($("card").hidden).toBe(true);
  });

  test("tapping a list item opens that site's card with a chart", () => {
    const { $, root, charts } = setup();
    root.querySelector<HTMLButtonElement>('[data-site="demo-b"]')!.click();
    expect($("card").hidden).toBe(false);
    expect($("card-title").textContent).toBe("Demo site B");
    expect(root.querySelector('[data-site="demo-b"]')!.getAttribute("aria-pressed")).toBe("true");
    expect(root.querySelector('[data-site="demo-a"]')!.getAttribute("aria-pressed")).toBe("false");
    expect(charts).toHaveLength(1);
    expect(charts[0].data.hh).toEqual([-10, -11, -12]);
  });

  test("the chart data keeps the gap as null", () => {
    const { view, charts } = setup();
    view.select("demo-a");
    expect(charts[0].data.hv).toEqual([-18, null, -17]);
  });

  test("the card has every slot, with date, source and the evidence badge", () => {
    const { view, $ } = setup();
    view.select("demo-a");
    expect($("card-dates").textContent).toContain("Dates");
    expect($("card-source").textContent).toContain("Source");
    expect($("card-source").textContent).toContain("2 Jul 2026");
    expect($("card-source").textContent).toContain("26 Jul 2026");
    expect($("card-observation").textContent).toContain(PLACEHOLDER);
    expect($("card-hypothesis").textContent).toContain("Hypothesis");
    expect($("card-test").textContent).toContain("What would test it");
    expect($("card-limits").textContent).toContain("Limits");
    const badge = $("card-evidence");
    expect(badge.textContent).toBe("Placeholder");
    expect(badge.dataset.evidence).toBe("placeholder");
  });

  test("a row missing hh_db or hv_db shows no data instead of throwing", () => {
    const partial = { ...sites[0], series: [{ date: "2026-07-02", hv_db: -18 }, { date: "2026-07-14", hh_db: -11 }] } as unknown as Site;
    const { view, root, charts } = setup([partial]);
    expect(() => view.select("demo-a")).not.toThrow();
    const rows = [...root.querySelectorAll("[data-role='card-table'] tbody tr")].map((r) => [...r.children].map((c) => c.textContent));
    expect(rows).toEqual([
      ["2 Jul 2026", "no data", "-18.0", "no data"],
      ["14 Jul 2026", "-11.0", "no data", "no data"],
    ]);
    expect(charts[0].data.hh).toEqual([null, -11]);
  });

  test("the values table shows no data for a gap", () => {
    const { view, root } = setup();
    view.select("demo-a");
    const rows = [...root.querySelectorAll("[data-role='card-table'] tbody tr")].map((r) => r.textContent);
    expect(rows).toHaveLength(3);
    expect(rows[1]).toContain("no data");
    expect(rows[1]).toContain("-11");
  });

  test("selecting another site replaces the chart and destroys the old one", () => {
    const { view, charts } = setup();
    view.select("demo-a");
    view.select("demo-b");
    expect(charts).toHaveLength(2);
    expect(charts[0].destroyed).toBe(true);
    expect(charts[1].destroyed).toBe(false);
  });

  test("works without a chart factory (table only)", () => {
    const root = document.createElement("div");
    document.body.append(root);
    const view = createSitesView(root, { sites, manifest: fixtureManifest });
    view.select("demo-a");
    expect(root.querySelector("[data-role='card-title']")!.textContent).toBe("Demo site A");
  });

  test("selecting an unknown id does nothing", () => {
    const { view, $ } = setup();
    view.select("nope");
    expect($("card").hidden).toBe(true);
  });
});
