// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { cardFor, PLACEHOLDER, siteCards } from "./content";
import { changeManifest, fixtureManifest } from "./fixtures";
import { createSitesView, isControl, mapCheckText, type ChartData, type ChartFactory, type ChartHooks } from "./sitesView";
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
    expect(t).toContain("Unusual dates score");
    expect(t).toContain("3.5 or more is highlighted");
    expect(t).toContain("2 Jul Excluded from change analysis, 14 Jul 5.4 (flagged date), 26 Jul 1.3.");
  });

  test("the step sits by the curve, with its size and dates, and says the card's test is the lenient one", () => {
    const t = open(changeManifest)("card-step").textContent ?? "";
    expect(t).toContain("On the Change map");
    expect(t).toContain("HH -8.1 dB, HV -5.3 dB between 26 Jul and 19 Aug.");
    expect(t).toContain("On the site's averaged curve this step passes the limits the map uses.");
    expect(t).toContain("more lenient than the map's own test, which judges each pixel");
    expect(t).not.toContain("passes the test the map uses");
  });

  test("a card with no map check never shows the map share as a percentage", () => {
    const t = open(changeManifest)("card-step").textContent ?? "";
    expect(t).not.toMatch(/\d+%/);
    expect(t).toContain("too few to give a percentage");
  });

  test("a step that does not pass says so", () => {
    const quiet = { ...scored, step: { ...scored.step!, flagged: false, map_share: 0 } };
    const root = document.createElement("div");
    document.body.append(root);
    createSitesView(root, { sites: [quiet], manifest: changeManifest }).select("demo-a");
    const t = root.querySelector('[data-role="card-step"]')!.textContent ?? "";
    expect(t).toContain("Largest step");
    expect(t).toContain("is under the limits the map uses");
    expect(t).toContain("None of the few map pixels");
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
    expect($("card-dates").textContent).toContain("not set yet");
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

describe("map check wording", () => {
  const step = { map_share: 0.9 };
  test("a share is quoted with its pixel count and radius, never bare", () => {
    expect(mapCheckText(cardFor("tarbela-shore"), step, 90)).toBe("27% of the 78 map pixels (90 m) within 450 m of the site are flagged.");
    expect(mapCheckText(cardFor("peshawar-city"), { map_share: 0 }, 90)).toBe("None of the 99 map pixels (90 m) within 500 m of the site are flagged.");
  });

  test("every shipped card with a share has a large enough sample to quote one", () => {
    for (const [id, c] of Object.entries(siteCards)) {
      if (c.mapCheck && c.mapCheck.flagged_pct > 0) expect(c.mapCheck.pixels, id).toBeGreaterThan(50);
    }
  });

  test("the shore card says its step rests on two earlier dates, one of them the flagged 14 Jul", () => {
    const note = cardFor("tarbela-shore").changeNote ?? "";
    expect(note).toContain("two earlier dates, 14 Jul and 26 Jul");
    expect(note).toContain("14 Jul is a flagged date");
  });
});

describe("controls", () => {
  const control = { ...mk("ctl", "Control site", [-18, -18, -18]), role: "Stable urban control" };
  const moved = { ...mk("mv", "Moved site", [-18, -18, -18]), role: "Reservoir shoreline" };

  test("a role that says control marks the site", () => {
    expect(isControl(control)).toBe(true);
    expect(isControl(moved)).toBe(false);
    expect(isControl({ role: "Permanent water control" })).toBe(true);
  });

  test("controls are listed apart from the sites that moved, and their card says what that means", () => {
    const root = document.createElement("div");
    document.body.append(root);
    const view = createSitesView(root, { sites: [control, moved], manifest: fixtureManifest });
    const inControls = [...root.querySelectorAll('[data-role="controls-list"] [data-site]')].map((b) => (b as HTMLElement).dataset.site);
    const inMoved = [...root.querySelectorAll('[data-role="list"] [data-site]')].map((b) => (b as HTMLElement).dataset.site);
    expect(inControls).toEqual(["ctl"]);
    expect(inMoved).toEqual(["mv"]);
    view.select("ctl");
    const $ = (r: string) => root.querySelector<HTMLElement>(`[data-role="${r}"]`)!;
    expect($("card-control-tag").hidden).toBe(false);
    const t = $("card-control").textContent ?? "";
    expect(t).toContain("used in setting the Change map's limits, so they are not an independent test");
    expect(t).toContain("An independent reviewer found that five fresh cities");
    expect(t).toContain("0% flagged within 450 m");
    view.select("mv");
    expect($("card-control-tag").hidden).toBe(true);
    expect($("card-control").hidden).toBe(true);
  });
});

describe("seeing the map on a date", () => {
  function open(withCallback = true) {
    const root = document.createElement("div");
    document.body.append(root);
    const shown: [string, string][] = [];
    let hooks: ChartHooks | undefined;
    const createChart: ChartFactory = (_el, _data, h) => {
      hooks = h;
      return { destroy() {} };
    };
    const view = createSitesView(root, {
      sites,
      manifest: fixtureManifest,
      createChart,
      onShowDate: withCallback ? (d, site) => shown.push([d, site.id]) : undefined,
    });
    view.select("demo-a");
    const $ = (r: string) => root.querySelector<HTMLElement>(`[data-role="${r}"]`)!;
    return { root, shown, $, tap: (i: number) => hooks!.onPick!(i) };
  }

  test("tapping a point on the chart shows that date's values and offers the map", () => {
    const { $, tap, shown } = open();
    expect($("card-pick").hidden).toBe(true);
    tap(2);
    expect($("card-pick").hidden).toBe(false);
    expect($("card-pick-text").textContent).toBe("26 Jul 2026: HH -12.0 dB, HV -17.0 dB.");
    $("card-pick-go").click();
    expect(shown).toEqual([["2026-07-26", "demo-a"]]);
  });

  test("a date in the table does the same, and marks its row", () => {
    const { root, $, shown } = open();
    root.querySelector<HTMLButtonElement>('tr[data-date="2026-07-14"] button')!.click();
    expect($("card-pick-text").textContent).toContain("14 Jul 2026: HH -11.0 dB, HV no data.");
    expect(root.querySelector('tr[data-date="2026-07-14"]')!.classList.contains("picked-row")).toBe(true);
    $("card-pick-go").click();
    expect(shown).toEqual([["2026-07-14", "demo-a"]]);
  });

  test("the site button opens the map at the picked date, or the latest one", () => {
    const { $, tap, shown } = open();
    $("card-map").click();
    expect(shown.at(-1)).toEqual(["2026-07-26", "demo-a"]);
    tap(0);
    $("card-map").click();
    expect(shown.at(-1)).toEqual(["2026-07-02", "demo-a"]);
  });

  test("without a callback there are no map buttons", () => {
    const { $, root } = open(false);
    expect($("card-map").hidden).toBe(true);
    expect(root.querySelectorAll("button.date-link")).toHaveLength(0);
  });

  test("the chart's text alternative gives the ranges and points to the table", () => {
    const { $ } = open();
    const label = $("card-chart").getAttribute("aria-label") ?? "";
    expect(label).toContain("HH runs from -12.0 to -10.0 dB");
    expect(label).toContain("HV from -18.0 to -17.0 dB");
    expect(label).toContain("table below");
  });
});
