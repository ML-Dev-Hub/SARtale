// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { storyBeats, type StoryStep } from "./content";
import { calibratedManifest } from "./fixtures";
import { createStoryPanel } from "./storyPanel";
import type { Manifest, Site } from "./types";

const REAL_DATES = [
  "2026-07-02", "2026-07-14", "2026-07-26", "2026-08-19", "2026-08-31",
  "2026-09-12", "2026-09-24", "2026-10-06", "2026-10-18",
];
const manifest: Manifest = {
  ...calibratedManifest,
  dates: REAL_DATES.map((date) => ({ date, granule: "g", frames: { HH: `frames/${date}_HH.webp`, HV: `frames/${date}_HV.webp` } })),
  gap: { start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" },
};
const shore: Site = { id: "tarbela-shore", name: "Tarbela Reservoir, south-east shore", lon: 72.87, lat: 34.01, role: "Reservoir shoreline", stack: "s", crid: "c", series: [] };

function mount(extra: Partial<Parameters<typeof createStoryPanel>[1]> = {}) {
  const root = document.createElement("aside");
  document.body.append(root);
  const calls: { id: string; index: number; from: number }[] = [];
  const log: string[] = [];
  const panel = createStoryPanel(root, {
    steps: storyBeats,
    manifest,
    sites: [shore],
    onGo: (s, index, from) => calls.push({ id: s.id, index, from }),
    onExit: () => log.push("exit"),
    onOpenSite: (id) => log.push(`site:${id}`),
    onPlay: () => log.push("play"),
    ...extra,
  });
  const $ = <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { root, panel, calls, log, $ };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("the story panel", () => {
  test("starts on the first step, with Back off and the count shown", () => {
    const { panel, $, calls } = mount();
    panel.go(0);
    expect(calls).toEqual([{ id: "valley", index: 0, from: -1 }]);
    expect($("story-kicker").textContent).toBe("Why the valley matters");
    expect($("story-title").textContent).toContain("monsoon cloud");
    expect($("story-count").textContent).toBe(`1 of ${storyBeats.length}`);
    expect($<HTMLButtonElement>("story-back").disabled).toBe(true);
  });

  test("Next walks every step in order through all six parts, and Back returns", () => {
    const { panel, $, calls } = mount();
    panel.go(0);
    for (let i = 1; i < storyBeats.length; i++) $("story-next").click();
    expect(calls.map((c) => c.id)).toEqual(storyBeats.map((s) => s.id));
    expect(calls.at(-1)!.from).toBe(storyBeats.length - 2);
    $("story-back").click();
    expect(calls.at(-1)).toEqual({ id: storyBeats.at(-2)!.id, index: storyBeats.length - 2, from: storyBeats.length - 1 });
    const beats = new Set(calls.map((c) => storyBeats[c.index].beat));
    expect([...beats]).toEqual([1, 2, 3, 4, 5, 6]);
  });

  test("the last step offers the map, and pressing it leaves the story", () => {
    const { panel, $, log, calls } = mount();
    panel.go(storyBeats.length - 1);
    expect($("story-next").textContent).toBe("Explore the map");
    const before = calls.length;
    $("story-next").click();
    expect(log).toEqual(["exit"]);
    expect(calls).toHaveLength(before);
  });

  test("Explore freely and Escape both leave the story", () => {
    const { panel, $, log, root } = mount();
    panel.go(3);
    $("story-exit").click();
    root.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(log).toEqual(["exit", "exit"]);
    expect(panel.index()).toBe(3);
  });

  test("six progress dots jump to the first step of a part and mark the current one", () => {
    const { panel, $, calls, root } = mount();
    panel.go(0);
    const dots = [...root.querySelectorAll<HTMLButtonElement>(".beat-dot")];
    expect(dots).toHaveLength(6);
    dots[4].click();
    expect(calls.at(-1)!.id).toBe("interference");
    expect(dots[4].getAttribute("aria-current")).toBe("step");
    expect(dots[3].classList.contains("done")).toBe(true);
    expect(dots[5].classList.contains("done")).toBe(false);
    expect(dots[4].getAttribute("aria-label")).toBe("Part 5 of 6: What NISAR missed");
    expect($("story-kicker").textContent).toBe("What NISAR missed, 2 July (1 of 3)");
  });

  test("a part with three stops says which one this is", () => {
    const { panel, $ } = mount();
    panel.go(storyBeats.findIndex((s) => s.id === "polarizations"));
    expect($("story-kicker").textContent).toBe("Why it moved, HH against HV (3 of 3)");
  });

  test("the season step offers a Play button, and a site step opens that site's card", () => {
    const { panel, $, log, root } = mount();
    panel.go(storyBeats.findIndex((s) => s.id === "season"));
    root.querySelector<HTMLButtonElement>(".story-actions button")!.click();
    panel.go(storyBeats.findIndex((s) => s.id === "tarbela"));
    root.querySelector<HTMLButtonElement>(".story-actions button")!.click();
    expect(log).toEqual(["play", "site:tarbela-shore"]);
    expect($("story-actions").textContent).toContain("Open the Tarbela Reservoir, south-east shore card");
  });

  test("a site card button is left out when the site is not in this build", () => {
    const { panel, $ } = mount({ sites: null });
    panel.go(storyBeats.findIndex((s) => s.id === "tarbela"));
    expect($("story-actions").children).toHaveLength(0);
  });

  test("the peak and the gap steps draw the timeline with the gap and the 23 July mark", () => {
    const { panel, $, root } = mount();
    panel.go(storyBeats.findIndex((s) => s.id === "peak"));
    expect($("story-strip").hidden).toBe(false);
    expect(root.querySelectorAll(".axis-dot")).toHaveLength(9);
    expect(root.querySelector(".axis-gap")).not.toBeNull();
    expect(root.querySelector(".axis-mark")?.getAttribute("data-label")).toBe("Peak, 23 Jul");
    expect($("story-strip-caption").textContent).toContain("No data 27 Jul to 10 Aug");
    expect($("story-axis").getAttribute("aria-label")).toContain("9 passes");
    panel.go(0);
    expect($("story-strip").hidden).toBe(true);
  });

  test("the 23 July mark falls between the 14 and 26 July passes", () => {
    const { panel, root } = mount();
    panel.go(storyBeats.findIndex((s) => s.id === "peak"));
    const left = (el: Element | null) => parseFloat((el as HTMLElement).style.left);
    const mark = left(root.querySelector(".axis-mark"));
    expect(mark).toBeGreaterThan(left(root.querySelector('[data-date="2026-07-14"]')));
    expect(mark).toBeLessThan(left(root.querySelector('[data-date="2026-07-26"]')));
  });

  test("a source line shows only where the step names one", () => {
    const { panel, $ } = mount();
    panel.go(storyBeats.findIndex((s) => s.id === "peak"));
    expect($("story-source").hidden).toBe(false);
    expect($("story-source").textContent).toContain("Flood Forecasting Division");
    panel.go(storyBeats.findIndex((s) => s.id === "nisar"));
    expect($("story-source").hidden).toBe(true);
  });

  test("out-of-range steps do nothing", () => {
    const { panel, calls } = mount();
    panel.go(-1);
    panel.go(99);
    expect(calls).toHaveLength(0);
  });

  test("works for a story of a single step", () => {
    const one: StoryStep[] = [storyBeats[0]];
    const { panel, $ } = mount({ steps: one });
    panel.go(0);
    expect($<HTMLButtonElement>("story-back").disabled).toBe(true);
    expect($("story-next").textContent).toBe("Explore the map");
  });
});
