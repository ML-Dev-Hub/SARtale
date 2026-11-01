// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import manifestJson from "../public/data/manifest.json";
import sitesJson from "../public/data/sites.json";
import { findBannedClaims, heroCopy, siteCards, storyBeats } from "./content";
import { calibratedManifest, changeManifest } from "./fixtures";
import { createEvidenceView, evidenceCopy, evidenceTokens, fillTokens } from "./evidenceView";
import type { Manifest, Site } from "./types";

const real = manifestJson as unknown as Manifest;
const realSites = sitesJson as unknown as Site[];

function open(m: Manifest, sites: Site[] | null = null) {
  const root = document.createElement("div");
  document.body.append(root);
  const view = createEvidenceView(root, { manifest: m, sites });
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
