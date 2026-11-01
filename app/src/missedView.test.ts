// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { findBannedClaims, story } from "./content";
import { fixtureManifest } from "./fixtures";
import { createMissedView } from "./missedView";
import type { Manifest } from "./types";

const gapped: Manifest = {
  ...fixtureManifest,
  gap: { start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" },
  dates: [
    ...fixtureManifest.dates,
    { date: "2026-08-19", granule: "g4", frames: { HH: "a", HV: "b" } },
  ],
};

function setup(m: Manifest) {
  const root = document.createElement("div");
  document.body.append(root);
  const view = createMissedView(root, { manifest: m });
  const $ = <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { root, view, $ };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("missed view", () => {
  test("states the gap start and end from the manifest as plain text", () => {
    const { $ } = setup(gapped);
    const t = $("gap-facts").textContent ?? "";
    expect(t).toContain("27 Jul 2026, 22:03:25 UTC");
    expect(t).toContain("10 Aug 2026, 00:55:27 UTC");
    expect(t).toContain("NISAR has no data");
    expect(t).toContain("No observation");
  });

  test("lists every manifest date as observed", () => {
    const { $ } = setup(gapped);
    const items = [...$("passes").querySelectorAll("li")].map((li) => li.textContent);
    expect(items).toEqual(["2 Jul 2026", "14 Jul 2026", "26 Jul 2026", "19 Aug 2026"]);
  });

  test("the run list names the permanent gap in text, apart from ordinary days between passes", () => {
    const { $ } = setup(gapped);
    const runs = [...$("runs").querySelectorAll("li")].map((li) => ({ kind: li.dataset.kind, text: li.textContent }));
    const gapRun = runs.filter((r) => r.kind === "gap");
    expect(gapRun).toHaveLength(1);
    expect(gapRun[0].text).toBe("No observation, permanent data gap: 28 Jul 2026 to 9 Aug 2026");
    expect(runs.some((r) => r.kind === "between" && r.text === "No observation, between passes: 3 Jul 2026 to 13 Jul 2026")).toBe(true);
    expect(runs.some((r) => r.kind === "observed" && r.text === "Observed: 2 Jul 2026")).toBe(true);
  });

  test("the timeline strip draws the gap differently and labels it in text", () => {
    const { $ } = setup(gapped);
    const cells = [...$("strip").querySelectorAll<HTMLElement>("[data-kind]")];
    expect(cells.map((c) => c.dataset.kind)).toContain("gap");
    expect(cells.find((c) => c.dataset.kind === "gap")!.textContent).toContain("No data");
  });

  test("the strip has a text alternative and the legend names all three states", () => {
    const { $ } = setup(gapped);
    expect($("strip").getAttribute("role")).toBe("img");
    expect($("strip").getAttribute("aria-label")).toContain("permanent data gap");
    const legend = $("legend").textContent ?? "";
    expect(legend).toContain("Observed");
    expect(legend).toContain("No observation, between passes");
    expect(legend).toContain("No observation, permanent data gap");
  });

  test("event copy states only what the data shows, with no event claims", () => {
    const { root, $ } = setup(gapped);
    const copy = story["what-nisar-missed"].summary;
    expect(copy).not.toMatch(/placeholder/i);
    expect($("event-copy").textContent).toBe(copy);
    expect(copy).toContain("which dates NISAR imaged");
    expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
    expect(root.textContent).not.toMatch(/flood|river|rain|monsoon|storm/i);
  });

  test("a flagged date carries its flag in the list of observed dates", () => {
    const m: Manifest = {
      ...gapped,
      dates: gapped.dates.map((d) => (d.date === "2026-07-14" ? { ...d, flag: "Forecast-orbit product; positions may be less precise." } : d)),
    };
    const { $ } = setup(m);
    const items = [...$("passes").querySelectorAll("li")].map((li) => li.textContent);
    expect(items[1]).toBe("14 Jul 2026. Forecast-orbit product; positions may be less precise.");
    expect(items[0]).toBe("2 Jul 2026");
  });

  test("a manifest with no gap says so and draws no gap", () => {
    const { $ } = setup(fixtureManifest);
    expect($("gap-facts").textContent).toContain("lists no data gap");
    expect($("strip").querySelector('[data-kind="gap"]')).toBeNull();
  });

  test("the scroll area can be reached by keyboard", () => {
    const { $ } = setup(gapped);
    expect($("scroll").getAttribute("tabindex")).toBe("0");
    expect($("scroll").getAttribute("role")).toBe("region");
    expect($("scroll").getAttribute("aria-label")).toBeTruthy();
  });
});
