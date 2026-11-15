// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { findBannedClaims } from "./content";
import { createEvidenceView } from "./evidenceView";
import { iouRange, lakeTokens, opticalOverlapPhrase, splitChecks, type LakesFile } from "./lakes";

// loaded the way the app loads it (lakes.ts loadLakes): check rows with only a note move to check_notes
const realLakes = splitChecks(lakesJson as unknown as LakesFile);

function open(lakes: LakesFile | null = realLakes) {
  const root = document.createElement("div");
  document.body.append(root);
  const view = createEvidenceView(root, { lakes });
  return { root, view, text: root.textContent ?? "" };
}
const withLakes = () => open();
/** Page text outside the closed Technical details block. */
function visibleText(root: HTMLElement): string {
  const clone = root.cloneNode(true) as HTMLElement;
  clone.querySelector('details[data-role="evidence-technical"]')?.remove();
  return clone.textContent ?? "";
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("How we know", () => {
  test("shows frozen lakes and the limits in short, then the full method, Sentinel-2 check, data, limits and how to check it inside Technical details", () => {
    const { root } = withLakes();
    const ids = [...root.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section);
    expect(ids).toEqual(["short-frozen", "short-limits", "lake-method", "lake-checks", "frozen", "data", "map-licences", "limits", "check"]);
    const tech = root.querySelector<HTMLDetailsElement>('details[data-role="evidence-technical"]')!;
    expect(tech.open).toBe(false);
    expect(tech.querySelector("summary")!.textContent).toBe("Technical details");
    expect([...tech.querySelectorAll<HTMLElement>("[data-section]")].map((s) => s.dataset.section)).toEqual(["lake-method", "lake-checks", "frozen", "data", "map-licences", "limits", "check"]);
    expect(tech.querySelector('[data-role="lake-checks-table"]')).not.toBeNull();
    expect(tech.textContent).toContain("docs/DATA_SOURCES.md");
    expect(tech.querySelector('[data-section="map-licences"]')!.textContent).toContain("Open Database Licence (ODbL) 1.0");
    expect(root.querySelector(".evidence-main")!.lastElementChild).toBe(tech);
  });

  test("C8: opens with four plain steps and keeps the visible text short and free of jargon", () => {
    const { root } = withLakes();
    const box = root.querySelector(".evidence-summary")!;
    expect(box.querySelector("h3")!.textContent).toBe("How SARtale reads a lake, in four steps");
    const steps = [...box.querySelectorAll("ol > li")].map((li) => li.textContent ?? "");
    expect(steps).toHaveLength(4);
    expect(steps[0]).toMatch(/NISAR/);
    expect(steps[0]).toMatch(/every 12 days/);
    expect(steps[0]).toMatch(/through cloud/);
    expect(steps[1]).toMatch(/dark/);
    expect(steps[2]).toMatch(/own normal range/);
    expect(steps[2]).toMatch(/same track/);
    expect(steps[3]).toMatch(/one status/);
    expect(steps[3]).toMatch(/Frozen/);
    expect(steps[3]).toMatch(/Sentinel-2/);
    expect(steps[3]).toMatch(/air temperature/);
    const visible = visibleText(root);
    expect(visible.split(/\s+/).filter(Boolean).length).toBeLessThan(700);
    for (const jargon of ["IoU", "D17", "Lee", "EPSG", "CUSUM", "GCOV", "z-score", "MNDWI", "speckle"]) expect(visible).not.toContain(jargon);
    expect(findBannedClaims(visible)).toEqual([]);
  });

  test("C8: the visible numbers come from lakes.json", () => {
    const t = lakeTokens(realLakes);
    const visible = visibleText(withLakes().root);
    expect(visible).toContain(`${t.cloud_looks} valid`);
    expect(visible).toContain(`${t.cloud_lakes} of ${t.lake_count} lakes`);
    expect(visible).toContain(t.cloud_start);
    expect(visible).toContain(t.site_counts);
    expect(t.site_counts).toBe("39 sites are watched: 36 hold water now and 3 have no lake now; 35 of the 36 had a clear Sentinel-2 scene to check against.");
    expect(visible).toContain(`radar water ${opticalOverlapPhrase(realLakes.checks, true)}`);
    const fewer: LakesFile = { ...realLakes, lakes: realLakes.lakes.slice(0, 3) };
    expect(lakeTokens(fewer).lake_count).not.toBe(t.lake_count);
    expect(visibleText(open(fewer).root)).toContain(` of ${lakeTokens(fewer).lake_count} lakes`);
  });

  test("C8: the not-an-official-warning line is on the page once", () => {
    const { text } = withLakes();
    expect(text.split("Official warnings come from PMD, NDMA, GBDMA and PDMA.").length - 1).toBe(1);
    expect(text.match(/not an official warning service/gi)).toHaveLength(1);
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
    expect(sec).toContain("Air temperature alone never shows open water");
    expect(sec).toContain("No freeze signal in air temperature since");
    expect(sec).not.toMatch(/Rogheli|melting ice brightens/);
    expect(text).toContain("NASA POWER daily air temperature");
    expect(text).toContain("Copernicus DEM GLO-30");
    // an older build without the freeze constants leaves the rule's figures out instead of showing {gaps}
    const { lapse_c_per_km: _a, freeze_fdd: _b, ...old } = c;
    const older = open({ ...realLakes, constants: old as LakesFile["constants"] });
    expect(older.text).not.toMatch(/\{\w+\}/);
    expect(older.root.querySelector('[data-section="frozen"]')!.textContent).toContain("Winter radar is untested");
  });

  test("says Not measured, not Not observable", () => {
    const t = open(realLakes).root.textContent ?? "";
    expect(t).not.toContain("Not observable");
    expect(t).toContain("Not measured");
  });

  test("puts what it can and cannot do first, before the detail", () => {
    const main = withLakes().root.querySelector(".evidence-main")!;
    expect([...main.children].slice(0, 3).map((c) => c.className)).toEqual(["evidence-head", "evidence-summary", "evidence-verdict"]);
    const verdict = main.querySelector(".evidence-verdict")!.textContent ?? "";
    expect(verdict).toContain("What it cannot do");
    expect(verdict).toMatch(/not an official warning service/);
  });

  test("links to every section, and a link moves focus to its heading without changing the address", () => {
    const { root } = withLakes();
    const links = [...root.querySelectorAll<HTMLAnchorElement>(".evidence-toc a")];
    expect(links.map((a) => a.textContent)).toEqual(["How it works", "Frozen lakes", "Where it falls short", "Technical details"]);
    const before = location.hash;
    links[2].click();
    expect(location.hash).toBe(before);
    expect(document.activeElement?.id).toBe("evidence-short-limits-h");
    const tech = root.querySelector<HTMLDetailsElement>('details[data-role="evidence-technical"]')!;
    links[3].click();
    expect(tech.open).toBe(true);
  });

  test("without lake data the page still stands and has no Sentinel-2 rows", () => {
    const { root } = open(null);
    expect(root.querySelector('[data-role="lake-checks-table"]')).toBeNull();
    expect(root.querySelector(".evidence-title")!.textContent).toBe("How we know");
  });

  test("the main heading is an h1 and amber is not used for generic caveats", async () => {
    const { root } = open();
    expect(root.querySelector("h1.evidence-title")).not.toBeNull();
    expect(root.querySelector("h2.evidence-title")).toBeNull();
    const css = (await import("./styles.css?raw")).default;
    const { rulesFor } = await import("./testCss");
    for (const sel of [".evidence-status", ".verdict-cannot", ".evidence-list li::marker"]) expect(rulesFor(css, sel).join(" "), sel).not.toContain("--warm");
  });

  test("C10: without lake data no raw {token} is shown, and the page says why figures are missing", () => {
    const { root } = open(null);
    expect(root.textContent).not.toMatch(/\{\w+\}/);
    expect(root.querySelector('[data-role="evidence-nodata"]')?.textContent).toContain("No lake data in this build");
  });

  test("a build with two processing versions names both, and says which part is provisional", () => {
    const text = open({ ...realLakes, crid: "P05023, P05036" }).text;
    expect(text).toContain("This build uses processing versions P05023 and P05036");
    expect(text).toContain("from 17 June 2026, processing versions P05023 and P05036, read as a 6 km window");
    expect(text).toContain("Passes up to 21 Oct 2026 are the provisional release (P05023)");
    expect(text).toContain("standard GCOV product (P05036)");
    expect(text).not.toMatch(/processing version P05023, P05036/);
    expect(text).not.toMatch(/\bvalidated standard\b|standard product is validated/i);
    const one = open({ ...realLakes, crid: "P05023" }).text;
    expect(one).toContain("This build uses processing version P05023.");
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
    expect(text).toContain("at least 5 earlier valid passes");
    expect(text).not.toMatch(/\{\w+\}/);
    const mine = withLakes().text;
    expect(mine).toContain(`${c.drop_db} dB below`);
    expect(mine).toContain(`${c.noise_floor_km2} km²`);
    expect(mine).toContain("17 Jun 2026 to 4 Aug 2026");
  });

  test("states the D17 water rule, the DEM mask, the levels, the search circle and the data file's own note", () => {
    const { text } = withLakes();
    expect(text).toContain("Water rule (method D17). SARtale first smooths each pass with a 7 by 7 pixel Lee filter");
    expect(text).toContain("A pixel is water when its HH is at least 3 dB below the median HH of the 6 km search window");
    expect(text).toContain("SARtale masks nothing inside the lake zone");
    expect(text).toContain("SARtale used an earlier two-view rule");
    expect(text).not.toMatch(/that is radar shadow, not water|not shadow-prone, and valid/);
    expect(text).toMatch(/robust z-score above 3\.5/);
    expect(text).toContain("Alert: growing when two valid passes in a row, on any tracks, have z of +2 or more");
    expect(text).toContain("a CUSUM with k = 0.5) reaches 4");
    expect(text).toContain("never below 0.005 km² or 2% of the baseline");
    expect(text).toContain("IoU under 0.4 gets no level");
    expect(text).toContain("search circle around its coordinates, 1 km unless the lake sets a smaller one");
    expect(text).toContain(realLakes.notes);
    expect(text).toMatch(/compared only with earlier passes from its own track/);
    // the Limits list states what the levels cannot do
    for (const t of ["nearly invisible", "5–12 days after a change begins in Hunza", "8–12 days in Chitral", "not outburst warning", "modelled", "one more season", "0.05 km²"]) expect(text).toContain(t);
  });

  test("a build made before the levels leaves the level sentences out rather than show gaps", () => {
    const { method: _m, ...older } = realLakes;
    const text = open(older as LakesFile).text;
    expect(text).not.toMatch(/\{\w+\}/);
    expect(text).not.toContain("Water rule (method");
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
    expect(text).toMatch(/Neither is a clean reference/);
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
    expect(text).not.toMatch(/(?<!not )(?<!not yet )validated/i); // "Not yet validated against Sentinel-2" is a status name
    expect(findBannedClaims(text)).toEqual([]);
    expect(text).not.toMatch(/detect/i);
    expect(text).not.toMatch(/Peshawar|Tarbela|OPERA/);
    expect(text).not.toMatch(/\{\w+\}/);
  });
});
