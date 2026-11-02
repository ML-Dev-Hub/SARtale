// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import manifestJson from "../public/data/manifest.json";
import sitesJson from "../public/data/sites.json";
import { findBannedClaims, heroCopy, siteCards, storyBeats } from "./content";
import lakesJson from "../public/data/lakes.json";
import type { LakesFile } from "./lakes";
import { calibratedManifest, changeManifest } from "./fixtures";
import { createEvidenceView, evidenceCopy, evidenceTokens, fillTokens } from "./evidenceView";
import type { Manifest, Site } from "./types";

const real = manifestJson as unknown as Manifest;
const realSites = sitesJson as unknown as Site[];

const realLakes = lakesJson as unknown as LakesFile;

function open(m: Manifest, sites: Site[] | null = null, lakes: LakesFile | null = null) {
  const root = document.createElement("div");
  document.body.append(root);
  const view = createEvidenceView(root, { manifest: m, sites, lakes });
  return { root, view, text: root.textContent ?? "" };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("How we know", () => {
  test("covers sources, method, control results, the rule, limits and what would change our mind", () => {
    const { root } = open(real, realSites);
    const ids = [...root.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section);
    expect(ids).toEqual(["data", "method", "controls", "rule", "limits", "mind", "check"]);
  });

  test("names the data sources and credits NASA, ASF, OPERA and the FFD", () => {
    const { text } = open(real, realSites);
    for (const word of ["NISAR", "ASF", "OPERA", "Flood Forecasting Division", "NASA", "Provisional"]) expect(text).toContain(word);
    expect(text).toContain("not validated");
  });

  test("states the limits of the step view in plain words", () => {
    const { text } = open(real, realSites);
    expect(text).toContain("set with the known sites in view");
    expect(text).toContain("false-alarm budget");
    expect(text).toMatch(/about 1%|1% of control pixels/);
    expect(text).toContain("Plain ground flags as strongly as the known sites, with no known cause");
    expect(text).toContain("A step names no cause");
  });

  test("words the control claim accurately: controls fed the limit, fresh cities are the independent check", () => {
    const { text } = open(real, realSites);
    expect(text).toContain("The controls were used in setting the limit");
    expect(text).toContain("An independent reviewer ran the rule on five fresh cities that played no part in setting it, and 0% were flagged within 450 m");
    expect(text).toContain("That is the independent check");
    expect(text).not.toMatch(/controls (prove|confirm)/i);
  });

  test("says the map is drawn at 270 m and analysed at 90 m, and that about 31% of flagged pixels are not drawn", () => {
    const { text } = open(real, realSites);
    expect(text).toContain("drawn at 270 m and analysed at 90 m");
    expect(text).toContain("About 31% of flagged pixels fall in cells that are not drawn");
  });

  test("says the card's averaged curve is more lenient than the map's pixel test", () => {
    expect(open(real, realSites).text).toContain("more lenient than the map's pixel-by-pixel test");
  });

  test("says the shore's step rests on two earlier dates, one of them flagged", () => {
    expect(open(real, realSites).text).toContain("two earlier dates, 14 Jul and 26 Jul, and 14 Jul is a flagged forecast-orbit date");
  });

  test("the rule was not blind and it changed, and the page says so", () => {
    const { text } = open(real, realSites);
    expect(text).toContain("This rule was not blind, and it changed");
  });

  test("every control row comes from a card: share, pixel count and radius", () => {
    const { root } = open(real, realSites);
    const rows = [...root.querySelectorAll('[data-role="evidence-controls"] tbody tr')].map((tr) => [...tr.children].map((c) => c.textContent));
    expect(rows).toHaveLength(7);
    expect(rows.find((r) => r[0]?.includes("Peshawar"))).toEqual(["Peshawar city", "Stable urban control", "0% of 99 pixels within 500 m"]);
    expect(rows.find((r) => r[0]?.includes("Tarbela Reservoir, south-east shore"))?.[2]).toBe("27% of 78 pixels within 450 m");
    expect(root.querySelectorAll('[data-role="evidence-controls"] tr[data-control]')).toHaveLength(3);
  });

  test("with no sites there is no control table, and the rest still stands", () => {
    const { root } = open(real, null);
    expect(root.querySelector('[data-role="evidence-controls"]')).toBeNull();
    expect(root.querySelector('[data-section="rule"]')).not.toBeNull();
  });

  test("a build with no step layer leaves out the step method, rule and control results", () => {
    const { root, text } = open(calibratedManifest);
    const ids = [...root.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section);
    expect(ids).toEqual(["data", "method", "limits", "mind", "check"]);
    expect(text).not.toContain("{");
    expect(text).not.toContain("Draw the flagged pixels");
  });

  test("no token is left unfilled, and the numbers come from the manifest", () => {
    const { text } = open(real, realSites);
    expect(text).not.toMatch(/\{\w+\}/);
    const t = evidenceTokens(real);
    expect(t.step_pixel_m).toBe("90");
    expect(t.drawn_m).toBe("270");
    expect(t.min_step_db).toBe("3");
    expect(t.min_stability).toBe("3.0");
    expect(t.step_dates).toBe("8");
    expect(t.analysis_m).toBe("30");
    expect(t.flagged_pct).toBe("1.4");
    expect(text).toContain("at least 3 dB on average");
  });

  test("a small fixture manifest fills its own numbers", () => {
    expect(evidenceTokens(changeManifest).step_dates).toBe("4");
    expect(fillTokens("{a} and {b}", { a: "1" })).toBe("1 and {b}");
  });

  test("invents no expectation: nothing says what a reprocessed 2 July file should read, and the mask claim follows the docs", () => {
    const { text } = open(real, realSites);
    expect(text).not.toMatch(/interference filtering|back to about -10/i);
    // The same holds for every card and for the story and hero copy.
    const all = JSON.stringify([siteCards, storyBeats, heroCopy]);
    expect(all).not.toMatch(/interference filtering|back to about -10|should bring HV/i);
    expect(siteCards["peshawar-city"].test).not.toMatch(/-?\d+(\.\d+)? dB|about -?\d/);
    expect(text).not.toContain("The mask was set on the main pool");
    expect(text).toContain("thresholds were set on the main Tarbela pool on 26 July, a date not compared");
    expect(text).toContain("The 2 July HV brightening is likely radio interference");
  });

  test("never names a land cover nobody has checked", () => {
    expect(open(real, realSites).text).not.toMatch(/farm|cropland|wheat|rice|orchard|village|paddy/i);
  });

  test("has no banned claims and never says detect", () => {
    const { text } = open(real, realSites);
    expect(findBannedClaims(text)).toEqual([]);
    expect(text).not.toMatch(/detect/i);
    expect(findBannedClaims(JSON.stringify(evidenceCopy))).toEqual([]);
  });

  test("links to every section, and a link moves focus to its heading without changing the address", () => {
    const { root } = open(real, realSites);
    const links = [...root.querySelectorAll<HTMLAnchorElement>(".evidence-toc a")];
    expect(links).toHaveLength(7);
    const before = location.hash;
    links[3].click();
    expect(location.hash).toBe(before);
    expect(document.activeElement?.id).toBe("evidence-rule-h");
  });

  test("honest wording is on the page where a reader first looks, before the detail", () => {
    const { root } = open(real, realSites);
    const first = root.querySelector(".evidence-verdict")!.textContent ?? "";
    expect(first).toContain("What it cannot do");
    expect(first).toContain("Call the rule a blind test");
  });
});

describe("How we know: lake method", () => {
  const withLakes = () => open(real, realSites, realLakes);

  test("the lake sections come first and are left out when there is no lake data", () => {
    const ids = [...withLakes().root.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section);
    expect(ids.slice(0, 2)).toEqual(["lake-method", "lake-checks"]);
    expect(ids.slice(2)).toEqual(["data", "method", "controls", "rule", "limits", "mind", "check"]);
    expect(open(real, realSites, null).text).not.toContain("Sentinel-2");
  });

  test("the lake method comes before the Peshawar verdict, and the verdict stays first without lake data", () => {
    const main = withLakes().root.querySelector(".evidence-main")!;
    const order = [...main.children].map((c) => (c as HTMLElement).dataset.section ?? c.className);
    expect(order.slice(0, 4)).toEqual(["evidence-head", "lake-method", "lake-checks", "evidence-verdict"]);
    const bare = [...open(real, realSites).root.querySelector(".evidence-main")!.children].map((c) => c.className);
    expect(bare.slice(0, 2)).toEqual(["evidence-head", "evidence-verdict"]);
  });

  test("the constants are filled from lakes.json, not typed in", () => {
    const t = evidenceTokens(real, realLakes);
    const c = realLakes.constants;
    expect(t.drop_db).toBe(String(c.drop_db));
    expect(t.speckle_box).toBe(String(c.speckle_box));
    expect(t.min_looks).toBe(String(c.min_looks));
    expect(t.min_observable).toBe(String(c.min_observable));
    expect(t.noise_floor_km2).toBe(String(c.noise_floor_km2));
    expect(t.change_factor).toBe(String(c.change_factor));
    // A changed constant shows up on the page.
    const other: LakesFile = { ...realLakes, constants: { ...c, drop_db: 6.5, min_looks: 5 } };
    const text = open(real, realSites, other).text;
    expect(text).toContain("6.5 dB below");
    expect(text).toContain("at least 5 valid");
    expect(text).not.toMatch(/\{\w+\}/);
    const mine = withLakes().text;
    expect(mine).toContain(`${c.drop_db} dB below`);
    expect(mine).toContain(`${c.noise_floor_km2} km²`);
    expect(mine).toContain("17 Jun 2026 to 4 Aug 2026");
  });

  test("states the two-view rule, the search circle and the data file's own note", () => {
    const { text } = withLakes();
    expect(text).toMatch(/dark from both an ascending and a descending view/);
    expect(text).toMatch(/dark from one side only is treated as terrain shadow/i);
    expect(text).toContain("1 km search circle");
    expect(text).toContain("underestimate lakes whose shores sit in radar shadow");
    expect(text).toContain(realLakes.notes);
    expect(text).toMatch(/only with its own earlier passes from the same viewing direction/);
  });

  test("lists every Sentinel-2 cross-check row from lakes.json", () => {
    const { root } = withLakes();
    const rows = [...root.querySelectorAll<HTMLTableRowElement>('[data-role="lake-checks-table"] tbody tr')];
    expect(rows).toHaveLength(realLakes.checks.length);
    realLakes.checks.forEach((c, i) => {
      const cells = [...rows[i].children].map((x) => x.textContent);
      const name = realLakes.lakes.find((l) => l.id === c.lake)!.name;
      expect(cells[0]).toBe(name);
      expect(cells[1]).toContain(c.nisar_track);
      expect(cells[1]).toMatch(/\d{1,2} \w{3} 2026/);
      expect(cells[2]).toContain(c.s2_id);
      expect(cells[3]).toBe(c.radar_km2.toFixed(3));
      expect(cells[4]).toBe(c.optical_km2.toFixed(3));
      expect(cells[5]).toBe(c.iou === null ? "n/a" : c.iou.toFixed(2));
    });
  });

  test("says agreement is poor except at Attabad, that neither source is a clean reference, and that this is not a validation", () => {
    const { text } = withLakes();
    expect(text).toMatch(/Agreement is poor except at Attabad/);
    expect(text).toMatch(/Shisper/);
    expect(text).toMatch(/ice or shadow/);
    expect(text).toMatch(/neither is a clean reference/);
    expect(text).toMatch(/not a validation of lake extent/);
  });

  test("says the SUPARCO comparison was skipped and lists what is not validated", () => {
    const { text } = withLakes();
    expect(text).toMatch(/SUPARCO area comparison was skipped because no SUPARCO lake IDs or locations have been supplied/);
    for (const item of ["frozen lakes", "lakes under 0.05 km²", "wind-roughened water"]) expect(text).toContain(item);
  });

  test("uses no praise words and no banned claims", () => {
    const { text } = withLakes();
    expect(text).not.toMatch(/accurate/i);
    expect(text).not.toMatch(/(?<!not )validated/i);
    expect(findBannedClaims(text)).toEqual([]);
    expect(text).not.toMatch(/detect/i);
  });
});
