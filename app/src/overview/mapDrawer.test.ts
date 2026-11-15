// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { fixtureMessage, makeFile, makeLake } from "../fixtures";
import type { Lake, LakesFile, LevelName } from "../lakes";
import { BASE_ASPECT } from "../lakeLocator";
import { mappedFixture } from "./mappedFixture";
import { createReadyGate, pinElement } from "./mapDrawer";
import { loadMappedLakes, watchThisLakeUrl } from "./mappedLakes";
import { DEFAULT_STATE, type MapDrawerFactory, type OverviewState } from "./model";
import { createOverview } from "./overviewView";

const lake = (id: string, over: Partial<Lake> = {}, status: Partial<Lake["status"]> = {}): Lake => {
  const l = makeLake({ id, name: id, ...over });
  const level = status.level as LevelName | null | undefined;
  const message = level && level !== "No change" ? fixtureMessage(level, id) : null;
  return { ...l, status: { ...l.status, message, ...status } };
};
const file = makeFile([
  lake("alert_lake", {}, { status: "Alert: growing", level: "Alert: growing", latest_date: "2026-11-09" }),
  lake("passu", { district: "Hunza", share_of_largest: 0.96, elevation_m: 2500, largest_extent: { km2: 1.2, source: "Hi-MAG", year: 2014 } }),
  lake("shazore", { district: "Chitral", share_of_largest: null, elevation_m: null }, { status: "Frozen (likely)", level: null }),
]);

const fakeDrawer = Object.assign(
  vi.fn<MapDrawerFactory>((_el, opts) => {
    fakeDrawer.lakes = opts.lakes;
    fakeDrawer.onPick = opts.onPick;
    return { highlight: (id) => { fakeDrawer.highlighted = id; }, setMappedVisible: (on) => { fakeDrawer.visible = on; }, destroy: () => {} };
  }),
  { lakes: [] as Lake[], highlighted: undefined as string | null | undefined, visible: undefined as boolean | undefined, onPick: (_id: string) => {}, pick: (id: string) => fakeDrawer.onPick(id) },
);

let root: HTMLDivElement;
let onState: Mock<(s: OverviewState) => void>;
let onOpenLake: Mock<(id: string) => void>;
let fetchFn: Mock;

function render(f: LakesFile = file, state: OverviewState = DEFAULT_STATE) {
  document.body.innerHTML = "";
  root = document.createElement("div");
  document.body.append(root);
  onState = vi.fn<(s: OverviewState) => void>();
  onOpenLake = vi.fn<(id: string) => void>();
  return createOverview(root, { file: f, state, onState, onOpenLake, mapDrawer: fakeDrawer, loadMapped: () => loadMappedLakes("x", fetchFn) });
}
const role = (name: string) => root.querySelector<HTMLElement>(`[data-role="${name}"]`)!;
const click = (el: Element) => el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
const tick = () => new Promise((r) => setTimeout(r));
const text = () => root.textContent ?? "";
const toggle = () => role("ov-map-toggle");

beforeEach(() => {
  fetchFn = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(mappedFixture))));
  fakeDrawer.mockClear();
  fakeDrawer.highlighted = undefined;
  fakeDrawer.lakes = [];
});
afterEach(() => {
  document.body.innerHTML = "";
});

describe("ready gate", () => {
  it("fires once when the style is ready first", () => {
    const g = createReadyGate<number>(); const fn = vi.fn(); g.onReady(fn);
    g.styleReady(); expect(fn).not.toHaveBeenCalled(); g.dataReady(7); g.dataReady(8);
    expect(fn).toHaveBeenCalledTimes(1); expect(fn).toHaveBeenCalledWith(7);
  });
  it("fires once when the data is ready first", () => {
    const g = createReadyGate<number>(); const fn = vi.fn(); g.onReady(fn);
    g.dataReady(7); expect(fn).not.toHaveBeenCalled(); g.styleReady(); g.styleReady();
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("map drawer", () => {
  it("is closed and has fetched nothing until opened", () => {
    render();
    expect(toggle().textContent).toBe("Show map");
    expect(role("ov-drawer").hidden).toBe(true);
    expect(fetchFn).not.toHaveBeenCalled();
    expect(fakeDrawer).not.toHaveBeenCalled();
  });
  it("loads mapped lakes only when the drawer opens", async () => {
    render();
    expect(fetchFn).not.toHaveBeenCalled();
    click(toggle());
    await tick();
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(toggle().textContent).toBe("Hide map");
    expect(role("ov-drawer").hidden).toBe(false);
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ map: true }));
    click(toggle());
    click(toggle());
    await tick();
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });
  it("a missing or invalid file leaves the watched lakes and says so", async () => {
    fetchFn.mockResolvedValue(new Response("nope", { status: 404 }));
    render();
    click(toggle());
    await tick();
    expect(text()).toContain("Mapped lakes could not be loaded.");
    expect(fakeDrawer.lakes).toHaveLength(file.lakes.length);
  });
  it("offers the grey dots with their count and passes the switch to the map", async () => {
    render();
    click(toggle());
    await tick();
    const box = root.querySelector<HTMLInputElement>('[data-role="ov-mapped-switch"]')!;
    expect(box.parentElement!.textContent).toContain("Show 3 mapped lakes, not watched yet (grey dots)");
    box.checked = false;
    box.dispatchEvent(new Event("change", { bubbles: true }));
    expect(fakeDrawer.visible).toBe(false);
  });
  it("row and marker selection follow each other", async () => {
    render();
    click(toggle());
    await tick();
    fakeDrawer.pick("passu");
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ sel: "passu", map: true }));
    render(file, { ...DEFAULT_STATE, map: true, sel: "shazore" });
    await tick();
    expect(fakeDrawer.highlighted).toBe("shazore");
    const shazore = root.querySelector('[data-role="ov-row"][data-id="shazore"]')!;
    expect(shazore.getAttribute("data-selected")).toBe("true");
    expect(shazore.hasAttribute("aria-pressed")).toBe(false);
    expect(shazore.querySelector("button.ov-locate")!.getAttribute("aria-pressed")).toBe("true");
    click(root.querySelector('[data-role="ov-row"][data-id="passu"]')!);
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ sel: "passu", map: true }));
  });
  it("shows the selected lake's card with the district only and opens its history", async () => {
    render(file, { ...DEFAULT_STATE, map: true, sel: "passu" });
    await tick();
    const card = role("ov-card");
    for (const label of ["District", "SUPARCO list", "Area", "Largest mapped outline", "Latest pass", "Elevation"]) expect(card.textContent).toContain(label);
    expect(card.textContent).toContain("Hunza");
    expect(card.textContent).not.toMatch(/Gilgit|Khyber|Hunza,/);
    click([...card.querySelectorAll("a")].find((b) => b.textContent === "Open lake history")!);
    expect(onOpenLake).toHaveBeenCalledWith("passu");
  });
  it("picking a grey dot shows it with Watch this lake", async () => {
    render();
    click(toggle());
    await tick();
    fakeDrawer.pick("m0001");
    const card = role("ov-card");
    expect(card.textContent).toContain("m0001");
    expect(card.textContent).toContain("HKH-PK-2020");
    const a = card.querySelector<HTMLAnchorElement>("a")!;
    expect(a.textContent).toBe("Watch this lake");
    expect(a.href).toBe(watchThisLakeUrl(mappedFixture.lakes[0]));
    expect(fakeDrawer.highlighted).toBe("m0001");
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ sel: null }));
  });
  it("shows the legend and the ODbL and CC BY notices", async () => {
    render();
    click(toggle());
    await tick();
    expect(role("ov-legend").textContent).toContain("Alert: growing");
    expect(role("ov-legend").textContent).toContain("Mapped, not watched yet");
    expect(text()).toContain(mappedFixture.notice.odbl);
    expect(text()).toContain(mappedFixture.notice.cc_by);
  });
  it("credits the map data in one line with links, and keeps the full notices in a shut details", async () => {
    render();
    click(toggle());
    await tick();
    const line = role("ov-attribution");
    expect(line.textContent).toBe("Map data: OpenStreetMap (ODbL), HKH-PK-2020 and Hi-MAG (CC BY 4.0), NASA MODIS");
    expect([...line.querySelectorAll("a")].map((a) => a.textContent)).toEqual(["OpenStreetMap", "HKH-PK-2020", "Hi-MAG", "NASA MODIS"]);
    expect([...line.querySelectorAll("a")].every((a) => /^https:\/\//.test(a.getAttribute("href")!))).toBe(true);
    const det = role("ov-notices") as HTMLDetailsElement;
    expect(det.tagName).toBe("DETAILS");
    expect(det.open).toBe(false);
    expect(det.querySelector("summary")!.textContent).toBe("Licence notices");
    expect(det.textContent).toContain(mappedFixture.notice.odbl);
    expect(det.textContent).toContain(mappedFixture.notice.cc_by);
  });
  it("gives the map frame the shape of the picture's real drawn bounds", async () => {
    render();
    click(toggle());
    await tick();
    expect(role("ov-map").style.getPropertyValue("--ov-map-aspect")).toBe(BASE_ASPECT.toFixed(4));
  });
  it("the legend lists one marker and label per family present, once", async () => {
    render();
    click(toggle());
    await tick();
    const items = [...role("ov-legend").querySelectorAll("li")];
    expect(items.map((li) => li.textContent)).toEqual(["Alert: growing", "No change", "Frozen", "Mapped, not watched yet"]);
    for (const li of items.slice(0, 3)) expect(li.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });
  it("a pin takes its family's marker and name", () => {
    const l = lake("f", {}, { status: "Frozen (seen by Sentinel-2)", level: null });
    const b = pinElement(l, () => {});
    expect(b.dataset.family).toBe("frozen");
    expect(b.getAttribute("aria-label")).toBe("f, Frozen");
    expect(b.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });
  it("Close map closes the drawer", async () => {
    render();
    click(toggle());
    await tick();
    click(role("ov-map-close"));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ map: false }));
  });
  it("the table stays usable when no map drawer is supplied", () => {
    document.body.innerHTML = "";
    root = document.createElement("div");
    document.body.append(root);
    createOverview(root, { file, state: DEFAULT_STATE, onState: vi.fn(), onOpenLake: vi.fn() });
    expect(root.querySelector('[data-role="ov-map-toggle"]')).toBeNull();
  });
});
