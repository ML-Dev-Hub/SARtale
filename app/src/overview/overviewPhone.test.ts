// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { findBannedClaims } from "../content";
import { fixtureMessage, makeFile, makeLake } from "../fixtures";
import type { Lake, LakesFile, LevelName } from "../lakes";
import { rulesFor } from "../testCss";
import { DEFAULT_STATE, type OverviewState } from "./model";
import phoneCss from "./overview.css?raw";
import { createOverview } from "./overviewView";


vi.mock("../contacts", () => ({
  authorityFor: (p: string) => (p === "GB" ? { id: "GBDMA", label: "Contact GBDMA", url: "https://example.test/gb", checked: "2026-11-14" } : null),
}));

const lake = (id: string, over: Partial<Lake> = {}, status: Partial<Lake["status"]> = {}): Lake => {
  const l = makeLake({ id, name: id, ...over });
  const level = status.level as LevelName | null | undefined;
  const message = level && level !== "No change" ? fixtureMessage(level, id) : null;
  return { ...l, status: { ...l.status, message, ...status } };
};

const file = makeFile([
  lake("alert_lake", { province: "GB" }, { status: "Alert: growing", level: "Alert: growing", latest_date: "2026-11-09", change_km2: 0.012 }),
  lake("forming_site", { lake_state: "lake_forming_check", province: "GB" }, { status: "Lake may be forming", level: null }),
  lake("watch_lake", { province: "KP" }, { status: "Watch", level: "Watch" }),
  lake("decrease_lake", { province: "GB" }, { status: "Decrease noted", level: "Decrease noted" }),
  lake("passu", { district: "Hunza", share_of_largest: 0.96, elevation_m: 2500 }),
  lake("shazore", { district: "Chitral", share_of_largest: null }, { status: "Frozen (likely)", level: null }),
  lake("shisper", { district: "Nagar", lake_state: "no_lake", share_of_largest: null }, { status: "No lake now", level: null }),
  lake("karambar_lake", { district: "Ghizer", suparco: { id: 116, match: "probable", source: "PDGL" }, share_of_largest: 0.97, above_largest: true }),
]);

let root: HTMLDivElement;
let onState: Mock<(s: OverviewState) => void>;
let onOpenLake: Mock<(id: string) => void>;

function render(f: LakesFile, state: OverviewState = DEFAULT_STATE) {
  document.body.innerHTML = "";
  root = document.createElement("div");
  document.body.append(root);
  onState = vi.fn<(s: OverviewState) => void>();
  onOpenLake = vi.fn<(id: string) => void>();
  return createOverview(root, { file: f, state, onState, onOpenLake, isPhone: true });
}
const role = (name: string) => root.querySelector<HTMLElement>(`[data-role="${name}"]`)!;
const card = () => role("ovp-attention");
const click = (el: Element) => el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));

afterEach(() => {
  document.body.innerHTML = "";
});

describe("overview on a phone", () => {
  it("shows the needs-attention card before the list", () => {
    render(file);
    expect(card().compareDocumentPosition(role("ovp-list")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(card().querySelectorAll("[data-id]")).toHaveLength(4);
    expect(card().querySelector('a[data-action="authority"]')!.textContent).toBe("Contact GBDMA");
  });
  it("offers each authority once, only for the provinces in the card, and hides one with no URL", () => {
    render(file);
    expect(card().querySelectorAll('a[data-action="authority"]')).toHaveLength(1);
    expect(card().textContent).toContain("If people on the ground report the lake changing:");
    expect(card().querySelector<HTMLAnchorElement>('a[data-action="authority"]')!.href).toBe("https://example.test/gb");
    render(makeFile([lake("w", { province: "KP" }, { status: "Watch", level: "Watch" })]));
    expect(card().querySelector('a[data-action="authority"]')).toBeNull();
    expect(card().textContent).not.toContain("If people on the ground");
  });
  it("has no needs-attention card when no lake needs attention", () => {
    render(makeFile([lake("passu")]));
    expect(root.querySelector('[data-role="ovp-attention"]')).toBeNull();
  });
  it("a card gives the family chip and the evidence line; a frozen lake reads Frozen with its evidence", () => {
    render(file);
    const sha = role("ovp-list").querySelector<HTMLElement>("[data-id=\"shazore\"]")!;
    expect(sha.querySelector(".ov-chip")!.textContent).toBe("Frozen");
    expect(sha.querySelector(".ov-tag")!.textContent).toBe("By air temperature; no clear image");
    const alert = card().querySelector<HTMLElement>("[data-id=\"alert_lake\"]")!;
    expect(alert.querySelector(".ov-chip")!.textContent).toBe("Alert: growing");
    expect(alert.querySelector(".ov-tag")!.textContent).toMatch(/^since /);
  });
  it("count chips filter and write the URL state", () => {
    render(file);
    click(root.querySelector('[data-role="ovp-chips"] [data-filter="frozen"]')!);
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ show: "frozen" }));
    const filters = [...role("ovp-chips").querySelectorAll<HTMLElement>("[data-filter]")].map((b) => b.dataset.filter);
    expect(filters).toEqual(["all", "alert", "watch", "open", "frozen", "no-lake", "above", "suparco"]);
  });
  it("the chips show their counts and mark the chosen one", () => {
    render(file, { ...DEFAULT_STATE, show: "frozen" });
    const frozen = role("ovp-chips").querySelector('[data-filter="frozen"]')!;
    expect(frozen.getAttribute("aria-pressed")).toBe("true");
    expect(frozen.textContent).toContain("1");
  });
  it("search and sort write the state", () => {
    render(file);
    const q = root.querySelector<HTMLInputElement>('input[type="search"]')!;
    q.value = "passu";
    q.dispatchEvent(new Event("input", { bubbles: true }));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ q: "passu" }));
    const sort = root.querySelector<HTMLSelectElement>("select")!;
    expect([...sort.options].map((o) => o.value)).toEqual(["status", "change", "name", "latest"]);
    sort.value = "name";
    sort.dispatchEvent(new Event("change", { bubbles: true }));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "name", dir: "asc" }));
  });
  it("the list holds the lakes that need no attention, with area, share and latest pass, and opens a lake", () => {
    render(file);
    const cards = role("ovp-list").querySelectorAll<HTMLElement>("[data-id]");
    expect([...cards].map((c) => c.dataset.id).sort()).toEqual(["karambar_lake", "passu", "shazore", "shisper"]);
    const passu = role("ovp-list").querySelector('[data-id="passu"]')!;
    for (const t of ["Area", "Of largest", "Latest pass"]) expect(passu.textContent).toContain(t);
    click(passu);
    expect(onOpenLake).toHaveBeenCalledWith("passu");
  });
  it("folds a long list behind Show all", () => {
    render(makeFile(Array.from({ length: 14 }, (_, i) => lake(`lake_${String(i).padStart(2, "0")}`))));
    expect(role("ovp-list").querySelectorAll("[data-id]")).toHaveLength(8);
    click([...role("ovp-list").querySelectorAll("button")].find((b) => b.textContent === "Show all 14 lakes")!);
    expect(role("ovp-list").querySelectorAll("[data-id]")).toHaveLength(14);
  });
  it("expands a first message in the card", () => {
    render(file);
    const first = card().querySelector<HTMLElement>("[data-id]")!;
    const toggle = first.querySelector("button")!;
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(first.textContent).toContain("What to do");
  });
  it("the bottom bar has List and Map", () => {
    render(file);
    expect([...role("ovp-bar").querySelectorAll("a, button")].map((e) => e.textContent)).toEqual(["List", "Map"]);
    expect(root.querySelector('a[href="#share"]')).toBeNull();
  });
  it("opens the map from the bar when a map drawer is given", () => {
    document.body.innerHTML = "";
    root = document.createElement("div");
    document.body.append(root);
    onState = vi.fn();
    const drawer = vi.fn(() => ({ highlight() {}, setMappedVisible() {}, destroy() {} }));
    createOverview(root, { file, state: DEFAULT_STATE, onState, onOpenLake: vi.fn(), isPhone: true, mapDrawer: drawer, loadMapped: async () => null });
    const sheet = role("ovp-map");
    expect(sheet.hidden).toBe(true);
    click([...role("ovp-bar").querySelectorAll("button")].find((b) => b.textContent === "Map")!);
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ map: true }));
    expect(sheet.hidden).toBe(false);
    expect(drawer).toHaveBeenCalled();
  });
  it("every phone control has a 44 px minimum and nothing lowers it", () => {
    expect(rulesFor(phoneCss, ".ovp :is(button, a, select, input)")).toContainEqual(expect.stringMatching(/min-height:\s*44px/));
    for (const sel of [".ovp button", ".ovp a", ".ovp select", ".ovp input"])
      for (const d of rulesFor(phoneCss, sel)) expect(d).not.toMatch(/(min-)?height:\s*([0-3]?\d|4[0-3])px/);
  });
  it("uses 16 px body text", () => expect(rulesFor(phoneCss, ".ovp").join(";")).toMatch(/font-size:\s*16px/));
  it("has no banned claim", () => {
    render(file);
    expect(findBannedClaims(root.textContent!)).toEqual([]);
  });
  it("the phone has the status key above the list, folded shut, and keeps its own chip row", () => {
    render(file);
    const key = role("ov-key") as HTMLDetailsElement;
    expect(key.tagName).toBe("DETAILS");
    expect(key.open).toBe(false);
    expect(key.compareDocumentPosition(role("ovp-list")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(role("ovp-chips").querySelectorAll("[data-filter]").length).toBeGreaterThan(3);
    expect(root.querySelector(".ov-chip")!.getAttribute("title")).toBeTruthy();
  });
});
