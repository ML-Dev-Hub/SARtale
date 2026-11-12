// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { findBannedClaims } from "./content";
import { createEvidenceView } from "./evidenceView";
import { iouRange, lakeTokens, opticalOverlapPhrase, type LakesFile } from "./lakes";

const realLakes = lakesJson as unknown as LakesFile;

function open(lakes: LakesFile | null = realLakes) {
  const root = document.createElement("div");
  document.body.append(root);
  const view = createEvidenceView(root, { lakes });
  return { root, view, text: root.textContent ?? "" };
}
const withLakes = () => open();

afterEach(() => {
  document.body.innerHTML = "";
});

describe("How we know", () => {
  test("has the lake method, the Sentinel-2 check, frozen lakes, the data, the limits and how to check it, in that order", () => {
    const ids = [...withLakes().root.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section);
    expect(ids).toEqual(["lake-method", "lake-checks", "frozen", "data", "limits", "check"]);
  });

  test("states the freeze rule from lakes.json and its limits", () => {
    const { root, text } = withLakes();
    const c = realLakes.constants;
    const sec = root.querySelector('[data-section="frozen"]')!.textContent ?? "";
    expect(sec).toContain(`below 0 °C on at least ${c.freeze_cold_run_days} days in a row, with at least ${c.freeze_fdd} freezing degree-days since 1 Sep`);
    expect(sec).toContain(`at ${Math.abs(c.lapse_c_per_km!)} °C per km`);
    expect(sec).toContain("Winter radar is untested");
    expect(sec).toContain("tested again with late-January data");
    expect(sec).toContain("one to two weeks late");
    expect(sec).toContain("Air temperature alone never says a lake is open");
    expect(text).toContain("NASA POWER daily air temperature");
    expect(text).toContain("Copernicus DEM GLO-30");
    // an older build without the freeze constants leaves the rule's figures out instead of showing {gaps}
    const { lapse_c_per_km: _a, freeze_fdd: _b, ...old } = c;
    const older = open({ ...realLakes, constants: old as LakesFile["constants"] });
    expect(older.text).not.toMatch(/\{\w+\}/);
    expect(older.root.querySelector('[data-section="frozen"]')!.textContent).toContain("Winter radar is untested");
  });

  test("puts what it can and cannot do first, before the detail", () => {
    const main = withLakes().root.querySelector(".evidence-main")!;
    expect([...main.children].slice(0, 2).map((c) => c.className)).toEqual(["evidence-head", "evidence-verdict"]);
    const verdict = main.querySelector(".evidence-verdict")!.textContent ?? "";
    expect(verdict).toContain("What it cannot do");
    expect(verdict).toMatch(/not an official warning service/);
  });

  test("links to every section, and a link moves focus to its heading without changing the address", () => {
    const { root } = withLakes();
    const links = [...root.querySelectorAll<HTMLAnchorElement>(".evidence-toc a")];
    expect(links).toHaveLength(6);
    const before = location.hash;
    links[4].click();
    expect(location.hash).toBe(before);
    expect(document.activeElement?.id).toBe("evidence-limits-h");
  });

  test("without lake data the page still stands and has no Sentinel-2 rows", () => {
    const { root } = open(null);
    expect(root.querySelector('[data-role="lake-checks-table"]')).toBeNull();
    expect(root.querySelector(".evidence-title")!.textContent).toBe("How we know");
  });

  test("C10: without lake data no raw {token} is shown, and the page says why figures are missing", () => {
    const { root } = open(null);
    expect(root.textContent).not.toMatch(/\{\w+\}/);
    expect(root.querySelector('[data-role="evidence-nodata"]')?.textContent).toContain("No lake data in this build");
  });

  test("a build with two processing versions names both, and says which part is provisional", () => {
    const text = open({ ...realLakes, crid: "P05023, P05036" }).text;
    expect(text).toContain("this build uses processing versions P05023 and P05036");
    expect(text).toContain("from 17 June 2026, processing versions P05023 and P05036, read as a 6 km window");
    expect(text).toContain("Passes up to 21 Oct 2026 are the provisional release (P05023)");
    expect(text).toContain("standard GCOV product (P05036)");
    expect(text).not.toMatch(/processing version P05023, P05036/);
    expect(text).not.toMatch(/\bvalidated standard\b|standard product is validated/i);
    const one = open({ ...realLakes, crid: "P05023" }).text;
    expect(one).toContain("this build uses processing version P05023.");
  });

  test("the constants are filled from lakes.json, not typed in", () => {
    const t = lakeTokens(realLakes);
    const c = realLakes.constants;
    expect(t.drop_db).toBe(String(c.drop_db));
    expect(t.speckle_box).toBe(String(c.speckle_box));
    expect(t.min_looks).toBe(String(c.min_looks));
    expect(t.min_observable).toBe(String(c.min_observable));
    expect(t.noise_floor_km2).toBe(String(c.noise_floor_km2));
    expect(t.change_factor).toBe(String(c.change_factor));
    // A changed constant shows up on the page.
    const other: LakesFile = { ...realLakes, constants: { ...c, drop_db: 6.5, min_looks: 5 } };
    const text = open(other).text;
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
    expect(text).toMatch(/dark in one viewing direction's season median image \(ascending or descending\) but seen and not dark in the other's/);
    expect(text).toContain("inside the lake zone, not shadow-prone, and valid");
    expect(text).toMatch(/robust z-score above 3\.5/);
    expect(text).toMatch(/that is radar shadow, not water/);
    expect(text).toContain("search circle around its coordinates, 1 km unless the lake sets a smaller one");
    expect(text).toContain("underestimate lakes whose shores sit in radar shadow");
    expect(text).toContain(realLakes.notes);
    expect(text).toMatch(/only with its own earlier passes from the same track/);
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

  test("words the agreement from the data, with its range, says neither source is a clean reference, and that this is not a validation", () => {
    const { text } = withLakes();
    expect(text).toContain(`Radar water ${opticalOverlapPhrase(realLakes.checks)}.`);
    expect(text).toContain(iouRange(realLakes.checks)!);
    expect(text).not.toMatch(/\{\w+\}/);
    expect(text).toMatch(/neither is a clean reference/);
    expect(text).toMatch(/not a validation of lake extent/);
  });

  test("says the SUPARCO comparison was skipped and lists what is not validated", () => {
    const { text } = withLakes();
    expect(text).toMatch(/SUPARCO area comparison was skipped because no SUPARCO lake IDs or locations have been supplied/);
    for (const item of ["frozen lakes", "lakes under 0.05 km²", "wind-roughened water"]) expect(text).toContain(item);
  });

  test("uses no praise words, no banned claims and no Peshawar chapter", () => {
    const { text } = withLakes();
    expect(text).not.toMatch(/accurate/i);
    expect(text).not.toMatch(/(?<!not )validated/i);
    expect(findBannedClaims(text)).toEqual([]);
    expect(text).not.toMatch(/detect/i);
    expect(text).not.toMatch(/Peshawar|Tarbela|OPERA/);
    expect(text).not.toMatch(/\{\w+\}/);
  });
});
