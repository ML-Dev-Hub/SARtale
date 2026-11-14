// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { findBannedClaims } from "../content";
import { fixtureMessage, frozenFixture, makeFile, makeLake } from "../fixtures";
import { sentinel2Url } from "../links";
import { provinceName } from "../provinces";
import type { Lake } from "../lakes";
import { rulesFor } from "../testCss";
import { createLakePage } from "./lakePage";
import lakeCss from "./lakePage.css?raw";

vi.mock("../contacts", () => ({ authorityFor: () => null }));

afterEach(() => {
  document.body.innerHTML = "";
});

const watchLake = makeLake({
  id: "passu", name: "Passu terminal lake", province: "GB", district: "Hunza",
  status: { ...makeLake().status, status: "Watch", level: "Watch", message: fixtureMessage("Watch", "Passu") },
});
const frozen = frozenFixture("shazore");

function page(lake: Lake, opts: Partial<Parameters<typeof createLakePage>[1]> = {}): HTMLElement {
  const el = document.createElement("div");
  document.body.append(el);
  createLakePage(el, { file: makeFile([lake]), lakeId: lake.id, onRoute: vi.fn(), ...opts });
  return el;
}
const roles = (el: HTMLElement): string[] => [...el.querySelectorAll<HTMLElement>("section")].filter((s) => !s.parentElement?.closest("section")).map((s) => s.dataset.role!);
const header = (el: HTMLElement): HTMLElement => el.querySelector<HTMLElement>('[data-role="lp-header"]')!;

describe("the lake page", () => {
  it("draws the header, the message and the filled blocks in order, and no block that has nothing in it yet", () => {
    expect(roles(page(watchLake))).toEqual(["lp-header", "lp-message", "lp-gauge", "lp-extent", "lp-picture", "lp-history", "lp-sources"]);
    expect(page(watchLake).querySelectorAll("h2").length).toBe(6);
  });
  it("a frozen lake has no message", () => expect(roles(page(frozen))).toEqual(["lp-header", "lp-freeze", "lp-extent", "lp-picture", "lp-history", "lp-sources"]));
  it("the sources block lists the sources and limits and prints the brief", () => {
    const onBrief = vi.fn();
    const b = page(watchLake, { onBrief }).querySelector<HTMLElement>('[data-role="lp-sources"]')!;
    expect(b.textContent).toContain("Coordinates");
    expect(b.querySelector("h3")!.textContent).toBe("Limits");
    b.querySelector<HTMLButtonElement>('button[data-action="brief"]')!.click();
    expect(onBrief).toHaveBeenCalledWith(watchLake);
  });
  it("a lake without a level has no message", () => expect(roles(page(makeLake()))).not.toContain("lp-message"));
  it("the message has the four parts and the actions", () => {
    const m = page(watchLake).querySelector('[data-role="lp-message"]')!;
    expect([...m.querySelectorAll("h3")].map((h) => h.textContent)).toEqual(["What changed", "How sure", "What it is not", "What to do"]);
    expect(m.querySelector<HTMLAnchorElement>('a[data-action="sentinel2"]')!.href).toBe(sentinel2Url(watchLake));
    expect(m.textContent).toContain("Official warnings come from PMD, NDMA, GBDMA and PDMA.");
  });
  it("the message carries its headline, what changed and the since line", () => {
    const m = page(watchLake).querySelector('[data-role="lp-message"]')!;
    const msg = watchLake.status.message!;
    expect(m.textContent).toContain(msg.title);
    expect(m.textContent).toContain(msg.what);
    expect(m.textContent).toContain(msg.since!);
  });
  it("the official-warnings sentence shows exactly once", () => {
    expect(page(watchLake).textContent!.split("Official warnings come from PMD, NDMA, GBDMA and PDMA.").length - 1).toBe(1);
    const bare = makeLake({ ...watchLake, id: "bare", status: { ...watchLake.status, message: { ...watchLake.status.message!, do: "Check recent optical imagery." } } });
    expect(page(bare).textContent!.split("Official warnings come from PMD, NDMA, GBDMA and PDMA.").length - 1).toBe(1);
  });
  it("the radar picture shows the HH image and the water layer, with the pass and track", () => {
    const l = makeLake({ images: { latest_hh: "lakes/lake_a/latest_hh.webp", water: "lakes/lake_a/water.webp", date: "2026-11-09", track: "055A" } });
    const b = page(l).querySelector('[data-role="lp-picture"]')!;
    expect([...b.querySelectorAll("img")].map((i) => i.getAttribute("src"))).toEqual(["data/lakes/lake_a/latest_hh.webp", "data/lakes/lake_a/water.webp"]);
    expect(b.querySelector(".lp-caption")!.textContent).toContain("pass of 9 Nov 2026, track 055A");
  });
  it("the radar picture says so when there is none, and hides the water layer while frozen", () => {
    expect(page(makeLake({ images: null })).querySelector('[data-role="lp-picture"]')!.textContent).toContain("No radar picture yet");
    const f = frozenFixture("shazore", "Frozen (likely)", { images: { latest_hh: "lakes/shazore/latest_hh.webp", water: "lakes/shazore/water.webp" } });
    const b = page(f).querySelector('[data-role="lp-picture"]')!;
    expect(b.querySelectorAll("img")).toHaveLength(1);
    expect(b.textContent).toContain("Water layer hidden");
  });
  it("no authority button when authorityFor gives none", () => expect(page(watchLake).querySelector('[data-action="authority"]')).toBeNull());
  it("an unknown lake id says so", () => {
    const el = document.createElement("div");
    createLakePage(el, { file: makeFile([watchLake]), lakeId: "nope", onRoute: vi.fn() });
    expect(el.textContent).toContain("This lake is not in the current data.");
    expect(el.querySelector('a[href="#lakes"]')).not.toBeNull();
  });
  it("a lake with no district, SUPARCO or province still renders its header", () => {
    const h = header(page(makeLake({ name: "Lake A" })));
    expect(h.textContent).toContain("Lake A");
    expect(h.textContent).toContain("Not matched to a SUPARCO PDGL ID");
  });
  it("the header has the back link, build line, place, chip and meta", () => {
    const h = header(page(watchLake));
    expect(h.textContent).toContain("All 1 watched lakes");
    expect(h.textContent).toContain("Data built 13 Nov 2026 · next refresh Mon 16 Nov 2026");
    expect(h.querySelector(".lp-place")!.textContent).toBe("Hunza, Gilgit-Baltistan");
    expect(h.querySelector("h1")!.textContent).toBe("Passu terminal lake");
    expect(h.querySelector(".ov-chip")!.textContent).toBe("Watch");
    expect(h.querySelector(".lp-meta")!.textContent).toBe("Latest assessment 9 Nov 2026 · track 055A · 9 valid looks · 1 track");
  });
  it("the header chip is the family with its evidence line", () => {
    const h = header(page(frozenFixture("shazore", "Frozen (seen by Sentinel-2)")));
    expect(h.querySelector(".ov-chip")!.textContent).toBe("Frozen");
    expect(h.querySelector(".lp-tag")!.textContent).toBe("Seen in Sentinel-2 since 18 Oct");
    expect(header(page(makeLake({ status: { ...makeLake().status, status: "Not observable" } }))).querySelector(".ov-chip")!.textContent).toBe("Not measured");
  });
  it("the frozen card heading names the family and its evidence", () => {
    expect(page(frozen).querySelector(".lp-freeze-head")!.textContent).toBe("Frozen: By air temperature since 18 Oct; no clear image");
  });
  it("leaves out the place and the meta parts the data lacks", () => {
    const h = header(page(makeLake({ status: { ...makeLake().status, latest_date: null, track: null, looks: 0 }, series: [] })));
    expect(h.querySelector(".lp-place")).toBeNull();
    expect(h.querySelector(".lp-meta")!.textContent).not.toMatch(/null|undefined|NaN/);
  });
  it("shows the district alone when there is no province", () => {
    expect(header(page(makeLake({ district: "Hunza" }))).querySelector(".lp-place")!.textContent).toBe("Hunza");
  });
  it("the back link goes through onRoute", () => {
    const onRoute = vi.fn();
    const el = page(watchLake, { onRoute });
    el.querySelector<HTMLAnchorElement>('a[href="#lakes"]')!.click();
    expect(onRoute).toHaveBeenCalledWith("#lakes");
  });
  it("with compare set the body is the compare view", () => {
    const el = page(watchLake, { compare: ["a", "b"] });
    expect(roles(el)).toEqual(["lp-header", "lp-compare"]);
    expect(el.textContent).toContain("Compare is not available yet.");
  });
  it("has no banned claim", () => expect(findBannedClaims(page(watchLake).textContent!)).toEqual([]));
  it("province names come from one constant", () => {
    expect(provinceName("KP")).toBe("Khyber Pakhtunkhwa");
    expect(provinceName(null)).toBeNull();
  });
  it("destroy empties the root", () => {
    const el = document.createElement("div");
    createLakePage(el, { file: makeFile([watchLake]), lakeId: "passu", onRoute: vi.fn() }).destroy();
    expect(el.innerHTML).toBe("");
  });
});

describe("the lake page on a phone", () => {
  it("keeps the block order in one column", () => {
    const el = page(watchLake, { isPhone: true });
    expect(el.querySelector(".lp")!.classList.contains("lp-phone")).toBe(true);
    expect(roles(el)).toEqual(["lp-header", "lp-message", "lp-gauge", "lp-extent", "lp-picture", "lp-history", "lp-sources"]);
    expect(header(el).textContent).toContain("All lakes");
    expect(header(el).textContent).not.toContain("watched lakes");
    expect(header(el).textContent).toContain("Data 13 Nov · next Mon 16 Nov");
  });
  it("readings render as stacked rows on a phone", () => {
    const el = page(watchLake, { isPhone: true });
    expect(el.querySelector('[data-role="lp-history"] table')).toBeNull();
    expect(el.querySelector('[data-role="lp-history"] [role="table"]')).toBeNull();
    expect(el.querySelectorAll('[data-role="lp-reading"]').length).toBeGreaterThan(0);
  });
  it("draws the gauge at phone width with short labels", () => {
    const svg = page(watchLake, { isPhone: true }).querySelector(".lp-gauge-svg")!;
    expect(svg.getAttribute("viewBox")).toBe("0 0 358 130");
    expect(svg.textContent).toContain("Smaller");
    expect(svg.textContent).not.toContain("Smaller than usual");
  });
  it("the desktop page keeps its table and its watched-lakes link", () => {
    const el = page(watchLake, { isPhone: false });
    expect(el.querySelector('[data-role="lp-reading"]')).toBeNull();
    expect(header(el).textContent).toContain("All 1 watched lakes");
  });
  it("phone controls, pass strip buttons included, are at least 44 px and nothing lowers it", () => {
    expect(rulesFor(lakeCss, ".lp-phone :is(button, a, select)")).toContainEqual(expect.stringMatching(/min-height:\s*44px/));
    for (const sel of [".lp-phone button", ".lp-phone a", ".lp-phone .lp-pass"])
      for (const d of rulesFor(lakeCss, sel)) expect(d).not.toMatch(/(min-)?height:\s*([0-3]?\d|4[0-3])px/);
  });
});
