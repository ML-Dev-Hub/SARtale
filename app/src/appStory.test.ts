// @vitest-environment jsdom
import { afterEach, describe, expect, test, vi } from "vitest";
import manifestJson from "../public/data/manifest.json";
import sitesJson from "../public/data/sites.json";
import { mountApp, type Camera, type MapHost, type Padding } from "./app";
import { findBannedClaims, storyBeats } from "./content";
import { calibratedManifest, fixtureManifest, INTERFERENCE_FLAG, previewManifest } from "./fixtures";
import type { MapLike } from "./map";
import { createPreloader } from "./preload";
import type { Manifest, Site } from "./types";

/** The real shipped manifest and curves, so these tests follow the story as a visitor sees it. */
const realManifest = manifestJson as unknown as Manifest;
const realSites = sitesJson as unknown as Site[];

function fakeMap(): MapLike & { urls: string[]; overlays: (string | null)[] } {
  const urls: string[] = [];
  const overlays: (string | null)[] = [];
  return {
    urls,
    overlays,
    setImage: async (url) => void urls.push(url),
    setOverlay: async (url) => void overlays.push(url),
  };
}

function setup(manifest: Manifest, opts?: Parameters<typeof mountApp>[3]) {
  const root = document.createElement("div");
  document.body.append(root);
  const moves: { camera: Camera; padding: Padding }[] = [];
  const host = { after: fakeMap(), before: fakeMap(), moveTo: (camera: Camera, padding: Padding) => moves.push({ camera, padding }) } satisfies MapHost;
  const app = mountApp(root, manifest, () => host, opts);
  const $ = <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { root, host, app, $, moves };
}

const setupReal = (opts: Parameters<typeof mountApp>[3] = { sites: realSites }) => setup(realManifest, opts);
const rect = (w: number, h: number) => ({ width: w, height: h, left: 0, top: 0, right: w, bottom: h, x: 0, y: 0, toJSON() {} }) as DOMRect;

afterEach(() => {
  document.body.innerHTML = "";
});

describe("the opening screen", () => {
  test("says what this is, shows the real picture and one finding, and offers a clear start", async () => {
    const { app, $ } = setupReal();
    await app.settled();
    expect($("hero-title").textContent).toContain("Peshawar Valley");
    expect($("hero-lede").textContent).toContain("every 12 days");
    expect($<HTMLImageElement>("hero-img").hidden).toBe(false);
    expect($<HTMLImageElement>("hero-img").getAttribute("src")).toBe("brand/hero-radar.webp");
    expect($("hero-finding").hidden).toBe(false);
    expect($("hero-finding-text").textContent).toContain("Around 19 Aug the Tarbela shore went dark");
    expect($("hero-finding-text").textContent).toContain("may indicate");
    expect($("hero-start").textContent).toBe("Start the story");
    expect($("hero-maturity").textContent).toBe("Provisional NISAR data");
    expect($("hero-caption").textContent).toContain("26 Jul 2026, 12 Sep 2026 and 18 Oct 2026");
  });

  test("its timeline shows the nine passes and the gap", async () => {
    const { app, root, $ } = setupReal();
    await app.settled();
    expect(root.querySelectorAll('[data-role="hero-axis-layer"] .axis-dot')).toHaveLength(9);
    expect(root.querySelector('[data-role="hero-axis-layer"] .axis-gap')).not.toBeNull();
    expect($("hero-strip-caption").textContent).toContain("9 passes, 2 Jul 2026 to 18 Oct 2026");
    expect($("hero-strip-caption").textContent).toContain("27 Jul to 10 Aug");
  });

  test("a build without the sites shows no finding", async () => {
    const { app, $ } = setup(calibratedManifest, { sites: null });
    await app.settled();
    expect($("hero-finding").hidden).toBe(true);
    expect($("hero-explore").hidden).toBe(false);
  });

  test("a preview or synthetic build shows no radar picture, no finding and no story", async () => {
    for (const manifest of [previewManifest, { ...fixtureManifest, maturity: "Synthetic demo" }]) {
      const { app, $ } = setup(manifest, { sites: realSites });
      await app.settled();
      expect($<HTMLImageElement>("hero-img").hidden).toBe(true);
      expect($("hero-finding").hidden).toBe(true);
      expect($("hero-start").hidden).toBe(true);
      expect($("story-start").hidden).toBe(true);
      expect($("hero-explore").hidden).toBe(false);
      document.body.innerHTML = "";
    }
  });

  test("the visible text has no banned claim and never says detect", async () => {
    const { app, root } = setupReal();
    await app.settled();
    expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
    expect(root.textContent).not.toMatch(/detect/i);
  });
});

describe("header and footer", () => {
  test("the footer says the data is provisional, not a warning service, credits NASA, ASF, OPERA and FFD, and names the team", async () => {
    const { app, root } = setupReal();
    await app.settled();
    const t = root.querySelector("footer")!.textContent ?? "";
    expect(t).toContain("Provisional NISAR data.");
    expect(t).toContain("Not an official warning service");
    for (const word of ["NASA", "ASF", "OPERA", "FFD", "SARcastic Scientists"]) expect(t).toContain(word);
  });

  test("the header has the logo once and no visible second wordmark", async () => {
    const { app, root } = setupReal();
    await app.settled();
    const header = root.querySelector("header")!;
    expect(header.querySelectorAll("img.logo")).toHaveLength(1);
    expect([...header.querySelectorAll("h1, .brand")].filter((e) => !e.classList.contains("sr-only"))).toHaveLength(0);
  });
});

describe("the guided story", () => {
  test("Start the story opens the map on the first step, and the camera goes to it", async () => {
    const { app, $, moves } = setupReal();
    await app.settled();
    $("hero-start").click();
    await app.settled();
    expect($("hero").hidden).toBe(true);
    expect($("story").hidden).toBe(false);
    expect($("view-dance").getAttribute("aria-pressed")).toBe("true");
    expect($("story-title").textContent).toBe(storyBeats[0].title);
    expect(moves.at(-1)!.camera).toEqual({ fit: true });
  });

  test("each step moves the date, polarization, layers and camera it names", async () => {
    const { app, host, $, moves, root } = setupReal();
    $("hero-start").click();
    const at = (id: string) => storyBeats.findIndex((b) => b.id === id);
    for (let i = 1; i <= at("tarbela"); i++) $("story-next").click();
    await app.settled();
    // Tarbela: 19 Aug, HH, the step map on, the camera at the shore.
    expect($("slider").getAttribute("aria-valuetext")).toBe("19 Aug 2026");
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-08-19_HH.webp");
    expect(host.after.overlays.at(-1)).toBe("data/frames/step_date.webp");
    expect($("change-panel").hidden).toBe(false);
    expect(moves.at(-1)!.camera).toEqual({ center: [72.871, 34.0138], zoom: 10.3 });
    // HH against HV: HV, no overlay.
    $("story-next").click();
    $("story-next").click();
    await app.settled();
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-08-19_HV.webp");
    expect(root.querySelector<HTMLInputElement>('input[value="HV"]')!.checked).toBe(true);
    expect(host.after.overlays.at(-1)).toBeNull();
    // 2 July: HV on the flagged date, west of Peshawar.
    $("story-next").click();
    await app.settled();
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-07-02_HV.webp");
    expect($("flag-after").textContent).toBe(INTERFERENCE_FLAG);
  });

  test("the peak and gap steps turn on before and after across the passes they name", async () => {
    const { app, host, $ } = setupReal();
    $("hero-start").click();
    const to = (id: string) => {
      const target = storyBeats.findIndex((b) => b.id === id);
      for (let n = 0; n < 12 && $("story-title").textContent !== storyBeats[target].title; n++) $("story-next").click();
    };
    to("peak");
    await app.settled();
    expect($("before").hidden).toBe(false);
    expect(host.before.urls.at(-1)).toBe("data/frames/2026-07-14_HH.webp");
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-07-26_HH.webp");
    to("gap");
    await app.settled();
    expect(host.before.urls.at(-1)).toBe("data/frames/2026-07-26_HH.webp");
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-08-19_HH.webp");
  });

  test("walking all steps visits the six parts and ends offering the map", async () => {
    const { app, $ } = setupReal();
    $("hero-start").click();
    const seen = new Set<string>([$("story-kicker").textContent!.split(",")[0]]);
    for (let i = 1; i < storyBeats.length; i++) {
      $("story-next").click();
      seen.add($("story-kicker").textContent!.split(",")[0]);
    }
    await app.settled();
    expect([...seen]).toEqual([
      "Why the valley matters", "Meet NISAR", "The season plays", "Why it moved", "What NISAR missed", "Why it matters",
    ]);
    expect($("story-next").textContent).toBe("Explore the map");
    $("story-next").click();
    expect($("story").hidden).toBe(true);
    expect($("story-start").textContent).toBe("Start the story");
  });

  test("leaving mid-way frees the map, keeps the place and lets the person return to it", async () => {
    const { app, $, moves, root } = setupReal();
    $("hero-start").click();
    for (let i = 0; i < 3; i++) $("story-next").click();
    await app.settled();
    const place = $("story-title").textContent;
    $("story-exit").click();
    expect($("story").hidden).toBe(true);
    expect(root.querySelector('[data-role="story-resume"]')).toBeNull();
    expect($("story-start").textContent).toBe("Resume the story");
    expect($("story-start").title).toBe(`Resume at step 4 of ${storyBeats.length}`);
    expect(moves.at(-1)!.camera).toEqual({ center: [72.871, 34.0138], zoom: 10.3 });
    // Free exploring still works.
    $<HTMLInputElement>("slider").value = "6";
    $("slider").dispatchEvent(new Event("input"));
    await app.settled();
    expect($("slider").getAttribute("aria-valuetext")).toBe("24 Sep 2026");
    const before = moves.length;
    $("story-start").click();
    await app.settled();
    expect($("story").hidden).toBe(false);
    expect($("story-title").textContent).toBe(place);
    expect(moves.length).toBe(before + 1);
    expect($("slider").getAttribute("aria-valuetext")).toBe("19 Aug 2026");
  });

  test("the story survives a visit to another view, and the header button goes back to it", async () => {
    const { app, $ } = setupReal();
    $("hero-start").click();
    $("story-next").click();
    $("view-evidence").click();
    expect($("story").hidden).toBe(true);
    expect($("evidence-view").hidden).toBe(false);
    $("story-start").click();
    expect($("story").hidden).toBe(false);
    expect($("story-title").textContent).toBe(storyBeats[1].title);
    await app.settled();
  });

  test("Back returns to the earlier step and its map", async () => {
    const { app, host, $ } = setupReal();
    $("hero-start").click();
    for (let i = 0; i < 4; i++) $("story-next").click();
    $("story-back").click();
    await app.settled();
    expect($("story-title").textContent).toBe(storyBeats[3].title);
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-08-19_HH.webp");
  });

  test("the camera leaves room for the story card beside it, or above it on a narrow screen", async () => {
    const { app, $, moves } = setupReal();
    $("stage").getBoundingClientRect = () => rect(1000, 600);
    $("story").getBoundingClientRect = () => rect(380, 500);
    $("hero-start").click();
    expect(moves.at(-1)!.padding.left).toBe(400);
    expect(moves.at(-1)!.padding.bottom).toBe(0);
    $("story").getBoundingClientRect = () => rect(980, 260);
    $("story-next").click();
    expect(moves.at(-1)!.padding.bottom).toBe(268);
    expect(moves.at(-1)!.padding.left).toBe(0);
    await app.settled();
  });

  test("a build without the step map still walks the story, leaving that layer off", async () => {
    const { app, $ } = setup(calibratedManifest, { sites: null });
    await app.settled();
    $("hero-start").click();
    for (let i = 0; i < 4; i++) $("story-next").click();
    await app.settled();
    expect($("change-panel").hidden).toBe(true);
    expect($("story-title").textContent).toBe(storyBeats[4].title);
  });

  test("the Play button in the season step plays the season", async () => {
    const { app, $, root } = setupReal();
    $("hero-start").click();
    $("story-next").click();
    $("story-next").click();
    root.querySelector<HTMLButtonElement>(".story-actions button")!.click();
    expect($("play").textContent).toBe("Pause");
    $("play").click();
    await app.settled();
  });

  test("the story text and the page it sits in are free of banned claims at every step", async () => {
    const { app, root, $ } = setupReal();
    $("hero-start").click();
    for (let i = 0; i < storyBeats.length - 1; i++) {
      expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
      $("story-next").click();
    }
    await app.settled();
  });

  test("the story's site step opens that site's card", async () => {
    const { $ } = setupReal();
    $("hero-start").click();
    for (let i = 0; i < 3; i++) $("story-next").click();
    ($("story").querySelector(".story-actions button") as HTMLButtonElement).click();
    expect($("sites-view").hidden).toBe(false);
    expect($("card-title").textContent).toContain("Tarbela");
  });
});

describe("the date line", () => {
  test("spaces the nine passes by real time and draws the data gap", async () => {
    const { app, root } = setupReal();
    await app.settled();
    const left = (date: string) => parseFloat(root.querySelector<HTMLElement>(`[data-role="ticks"] [data-date="${date}"]`)!.style.left);
    expect(left("2026-08-19") - left("2026-07-26")).toBeCloseTo(2 * (left("2026-08-31") - left("2026-08-19")), 1);
    const gap = root.querySelector<HTMLElement>('[data-role="ticks"] .axis-gap')!;
    expect(parseFloat(gap.style.left)).toBeGreaterThan(left("2026-07-26"));
    expect(parseFloat(gap.style.left) + parseFloat(gap.style.width)).toBeLessThan(left("2026-08-19"));
    expect(gap.title).toBe("No data 27 Jul to 10 Aug");
  });

  test("marks the two flagged dates, and the key names the flag and the gap", async () => {
    const { app, root, $ } = setupReal();
    await app.settled();
    const flagged = [...root.querySelectorAll<HTMLElement>('[data-role="ticks"] .axis-dot.flagged')].map((e) => e.dataset.date);
    expect(flagged).toEqual(["2026-07-02", "2026-07-14"]);
    const key = $("axis-key").textContent ?? "";
    expect(key).toContain("Flagged date");
    expect(key).toContain("No data 27 Jul to 10 Aug");
  });

  test("in the Change view the dates the map can place take its colours, and 2 July is shown as left out", async () => {
    const { app, root, $ } = setupReal();
    $("hero-explore").click();
    $("change-toggle").click();
    await app.settled();
    const tinted = [...root.querySelectorAll<HTMLElement>('[data-role="ticks"] .axis-dot.step')].map((e) => e.dataset.date);
    expect(tinted).toEqual(realManifest.change!.step!.split_dates);
    expect(root.querySelector('[data-role="ticks"] [data-date="2026-07-02"]')!.classList.contains("excluded")).toBe(true);
    expect($("date-excluded").hidden).toBe(false);
    $("change-toggle").click();
    await app.settled();
    expect(root.querySelectorAll('[data-role="ticks"] .axis-dot.step')).toHaveLength(0);
    expect($("date-excluded").hidden).toBe(true);
  });

  test("a press on the line picks the nearest date and pauses play", async () => {
    const { app, root, $ } = setupReal();
    $("hero-explore").click();
    $("ticks").getBoundingClientRect = () => rect(1000, 10);
    $("play").click();
    expect($("play").textContent).toBe("Pause");
    const target = parseFloat(root.querySelector<HTMLElement>('[data-role="ticks"] [data-date="2026-09-24"]')!.style.left) * 10;
    const press = (type: string) => $("axis").dispatchEvent(Object.assign(new Event(type, { bubbles: true }), { clientX: target + 5, pointerId: 1, button: 0 }));
    press("pointerdown");
    press("pointerup");
    await app.settled();
    expect($("slider").getAttribute("aria-valuetext")).toBe("24 Sep 2026");
    expect($("play").textContent).toBe("Play");
  });

  test("the composite locks the line", async () => {
    const { app, root, $ } = setupReal();
    $("hero-explore").click();
    $("composite-toggle").click();
    await app.settled();
    $("ticks").getBoundingClientRect = () => rect(1000, 10);
    $("axis").dispatchEvent(Object.assign(new Event("pointerdown", { bubbles: true }), { clientX: 900, pointerId: 1, button: 0 }));
    await app.settled();
    expect($("slider").getAttribute("aria-valuetext")).toBe("2 Jul 2026");
    expect(root.querySelector(".axis.locked")).not.toBeNull();
  });
});

describe("the step view's words", () => {
  async function open() {
    const s = setupReal();
    s.$("hero-explore").click();
    s.$("change-toggle").click();
    await s.app.settled();
    return s;
  }

  test("says plainly: set with the known sites in view, about a 1% false-alarm budget, plain ground flags too", async () => {
    const { $ } = await open();
    const t = $("change-limit").textContent ?? "";
    expect(t).toContain("set with the known sites in view");
    expect(t).toContain("not a blind test");
    expect(t).toContain("false-alarm budget is about 1%");
    expect(t).toContain("Plain ground flags too, with no known cause");
  });

  test("says the map is drawn at 270 m and analysed at 90 m, that about 31% of flagged pixels are not drawn, and how the controls count", async () => {
    const { $ } = await open();
    const t = $("change-detail").textContent ?? "";
    expect(t).toContain("drawn at 270 m and analysed at 90 m");
    expect(t).toContain("about 31% of flagged pixels fall in cells that are not drawn");
    expect(t).toContain("The controls were used in setting the limit");
    expect(t).toContain("an independent reviewer found that five fresh cities also stayed quiet (0% flagged within 450 m)");
  });

  test("the caption says it is one season-wide map and that colour is the date of the step", async () => {
    const { $ } = await open();
    const t = $("change-caption").textContent ?? "";
    expect(t).toContain("One map for the whole season");
    expect(t).toContain("its colour is the date of the first pass after the step");
    expect(t).not.toContain("around this date");
    expect($("change-legend").textContent).toContain("The date slider changes the radar underneath, not these colours");
  });

  test("the legend has a row per date with its two shades, and Unusual dates stays a secondary button", async () => {
    const { root, $ } = await open();
    const rows = [...root.querySelectorAll<HTMLElement>('[data-role="step-legend"] li[data-date]')];
    expect(rows.map((r) => r.dataset.date)).toEqual(realManifest.change!.step!.split_dates);
    for (const r of rows) expect(r.querySelectorAll(".swatch")).toHaveLength(2);
    expect($("unusual-toggle").classList.contains("unusual")).toBe(true);
    expect($("unusual-toggle").textContent).toBe("Unusual dates");
    expect($("change-toggle").textContent).toBe("Change");
  });

  test("pointing at a legend row lights its date on the line", async () => {
    const { root } = await open();
    const row = root.querySelector<HTMLElement>('[data-role="step-legend"] li[data-date="2026-09-24"]')!;
    row.dispatchEvent(new Event("pointerenter"));
    expect(root.querySelector('[data-role="ticks"] [data-date="2026-09-24"]')!.classList.contains("lit")).toBe(true);
    row.dispatchEvent(new Event("pointerleave"));
    expect(root.querySelector('[data-role="ticks"] .lit')).toBeNull();
  });
});

describe("frames load ahead of the person", () => {
  test("after the first frame, every HH frame is requested, nearest first, and HV waits until it is picked", async () => {
    const asked: string[] = [];
    const preload = createPreloader(async (url) => void asked.push(url), 9);
    const { app, root } = setup(realManifest, { sites: realSites, preload });
    await app.settled();
    await new Promise((r) => setTimeout(r, 10));
    expect(asked.filter((u) => u.endsWith("_HH.webp"))).toHaveLength(9);
    expect(asked[0]).toBe("data/frames/2026-07-02_HH.webp");
    expect(asked.some((u) => u.endsWith("_HV.webp"))).toBe(false);
    const hv = root.querySelector<HTMLInputElement>('input[value="HV"]')!;
    hv.checked = true;
    hv.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 10));
    expect(asked.filter((u) => u.endsWith("_HV.webp"))).toHaveLength(9);
  });

  test("play waits for the next frame, so a slow frame does not make a blank step", async () => {
    let release: (() => void) | undefined;
    const preload = createPreloader((url) => (url.includes("2026-07-14_HH") ? new Promise<void>((r) => (release = r)) : Promise.resolve()), 9);
    const { app, $ } = setup(realManifest, { sites: realSites, preload });
    $("hero-explore").click();
    await app.settled();
    $("play").click();
    await new Promise((r) => setTimeout(r, 120));
    expect($("slider").getAttribute("aria-valuetext")).toBe("2 Jul 2026");
    release!();
    await vi.waitFor(() => expect($("slider").getAttribute("aria-valuetext")).toBe("14 Jul 2026"));
    $("play").click();
  });

  test("a slow frame says what the map is waiting for, and a fast one stays silent", async () => {
    const root = document.createElement("div");
    document.body.append(root);
    let finish: (() => void) | undefined;
    const after: MapLike = { setImage: () => new Promise<void>((r) => (finish = r)) };
    const app = mountApp(root, fixtureManifest, () => ({ after, before: fakeMap() }));
    const loading = root.querySelector<HTMLElement>('[data-role="loading"]')!;
    expect(loading.hidden).toBe(true);
    await new Promise((r) => setTimeout(r, 220));
    expect(loading.hidden).toBe(false);
    expect(loading.textContent).toBe("Loading 2 Jul 2026, HH");
    finish!();
    await app.settled();
    await vi.waitFor(() => expect(loading.hidden).toBe(true));
  });

  test("progress shows while frames are still being fetched", async () => {
    const gates: (() => void)[] = [];
    const preload = createPreloader(() => new Promise<void>((r) => gates.push(r)), 2);
    const { app, $ } = setup(realManifest, { sites: realSites, preload });
    await app.settled();
    await new Promise((r) => setTimeout(r, 10));
    expect($("load-state").hidden).toBe(false);
    expect($("load-state").textContent).toBe("Preparing frames: 0 of 9");
    await vi.waitFor(() => {
      while (gates.length) gates.shift()!();
      expect($("load-state").hidden).toBe(true);
    });
  });
});

describe("site cards and the map", () => {
  test("a date picked on a card opens the map on that date, centred on the site, and leaves the story", async () => {
    const { app, $, root, moves, host } = setupReal();
    $("hero-start").click();
    $("view-sites").click();
    root.querySelector<HTMLButtonElement>('[data-site="tarbela-shore"]')!.click();
    root.querySelector<HTMLButtonElement>('tr[data-date="2026-09-24"] button')!.click();
    $("card-pick-go").click();
    await app.settled();
    expect($("view-dance").getAttribute("aria-pressed")).toBe("true");
    expect($("story").hidden).toBe(true);
    expect($("slider").getAttribute("aria-valuetext")).toBe("24 Sep 2026");
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-09-24_HH.webp");
    expect(moves.at(-1)!.camera).toEqual({ center: [72.871, 34.0138], zoom: 10.5 });
  });
});

describe("How we know in the app", () => {
  test("the fourth view opens the evidence page and hides the map", async () => {
    const { app, $ } = setupReal();
    await app.settled();
    $("view-evidence").click();
    expect($("evidence-view").hidden).toBe(false);
    expect($("stage").hidden).toBe(true);
    expect($("dock").hidden).toBe(true);
    expect($("view-name").textContent).toBe("How we know");
    expect($("evidence-maturity").textContent).toBe("Provisional NISAR data");
    expect($("evidence-view").textContent).toContain("What it cannot do");
  });

  test("the hero links to it", async () => {
    const { app, $ } = setupReal();
    await app.settled();
    $("hero-method").click();
    expect($("evidence-view").hidden).toBe(false);
    expect($("hero").hidden).toBe(true);
  });
});

describe("cautions in the story", () => {
  const to = ($: (r: string) => HTMLElement, id: string) => {
    const target = storyBeats.findIndex((b) => b.id === id);
    for (let n = 0; n < 12 && $("story-title").textContent !== storyBeats[target].title; n++) $("story-next").click();
  };

  test("the 23 July step states the 14 July caution in its own text and in the card, where it cannot be covered", async () => {
    const { app, $ } = setupReal();
    $("hero-start").click();
    to($, "peak");
    await app.settled();
    expect($("story-text").textContent).toContain("14 July is a forecast-orbit file, so its positions may be less precise");
    expect($("story-caution").hidden).toBe(false);
    expect($("story-caution").textContent).toContain("14 Jul 2026: Forecast-orbit product; positions may be less precise.");
    expect($("story").contains($("story-caution"))).toBe(true);
  });

  test("the 2 July step shows the interference caution inside the card, on every screen size", async () => {
    const { app, $ } = setupReal();
    $("hero-start").click();
    to($, "interference");
    await app.settled();
    expect($("story-caution").textContent).toContain("Likely radio interference in HV over the western area. Do not read this as surface change.");
  });

  test("a step on an unflagged date shows no caution", async () => {
    const { app, $ } = setupReal();
    $("hero-start").click();
    await app.settled();
    expect($("story-caution").hidden).toBe(true);
  });

  test("background steps are labelled as background, findings are not", async () => {
    const { $ } = setupReal();
    $("hero-start").click();
    expect($("story-background").hidden).toBe(false);
    to($, "tarbela");
    expect($("story-background").hidden).toBe(true);
  });
});

describe("leaving the story", () => {
  test("Escape returns focus to the story button and the map takes the whole stage back", async () => {
    const { app, $, moves, root } = setupReal();
    $("hero-start").click();
    $("story-title").focus();
    $("story").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect($("story").hidden).toBe(true);
    expect(document.activeElement).toBe($("story-start"));
    expect(moves.at(-1)).toEqual({ camera: { home: true }, padding: { top: 0, right: 0, bottom: 0, left: 0 } });
    await app.settled();
    expect(root).toBeTruthy();
  });

  test("leaving on a step that zoomed to a place keeps that place", async () => {
    const { $, moves } = setupReal();
    $("hero-start").click();
    for (let i = 0; i < 3; i++) $("story-next").click();
    const before = moves.length;
    $("story-exit").click();
    expect(moves.length).toBe(before);
  });

  test("destroying the app stops listening to the preloader", async () => {
    const preload = createPreloader(async () => {}, 2);
    let heard = 0;
    const real = preload.onChange.bind(preload);
    let stopped = 0;
    preload.onChange = (l) => {
      const stop = real(() => {
        heard += 1;
        l();
      });
      return () => {
        stopped += 1;
        stop();
      };
    };
    const { app } = setup(realManifest, { sites: realSites, preload });
    await app.settled();
    app.destroy();
    expect(stopped).toBe(1);
    const h = heard;
    preload.request(["x.webp"]);
    expect(heard).toBe(h);
  });
});
