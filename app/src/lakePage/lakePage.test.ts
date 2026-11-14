// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { findBannedClaims } from "../content";
import { fixtureMessage, frozenFixture, makeFile, makeLake } from "../fixtures";
import { sentinel2Url } from "../links";
import { provinceName } from "../provinces";
import type { Lake } from "../lakes";
import { createLakePage } from "./lakePage";

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
  it("orders the blocks as the spec says", () => expect(roles(page(watchLake))).toEqual(["lp-header", "lp-message", "lp-gauge", "lp-extent", "lp-picture", "lp-history", "lp-sources"]));
  it("a frozen lake swaps the gauge for the frozen card and has no message", () => expect(roles(page(frozen))).toEqual(["lp-header", "lp-freeze", "lp-extent", "lp-picture", "lp-history", "lp-sources"]));
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
