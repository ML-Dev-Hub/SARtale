// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { findBannedClaims } from "../content";
import { fixtureMessage, frozenFixture, makeFile, makeLake } from "../fixtures";
import { sortLakes, type Lake, type LakesFile, type LevelName } from "../lakes";
import { DEFAULT_STATE, type OverviewState } from "./model";
import { createOverview, nameList } from "./overviewView";

const lake = (id: string, over: Partial<Lake> = {}, status: Partial<Lake["status"]> = {}): Lake => {
  const l = makeLake({ id, name: id, ...over });
  const level = status.level as LevelName | null | undefined;
  // A level lake carries the pipeline's message, as every real build does.
  const message = level && level !== "No change" ? fixtureMessage(level, id) : null;
  return { ...l, status: { ...l.status, message, ...status } };
};

/** The Task 12 fixture: four needs-attention lakes and four others. */
const file = makeFile([
  lake("alert_lake", {}, { status: "Alert: growing", level: "Alert: growing", latest_date: "2026-11-09" }),
  lake("forming_site", { lake_state: "lake_forming_check" }, { status: "Lake may be forming", level: null }),
  lake("watch_lake", {}, { status: "Watch", level: "Watch" }),
  lake("decrease_lake", {}, { status: "Decrease noted", level: "Decrease noted" }),
  lake("passu", { district: "Hunza", share_of_largest: 0.96, elevation_m: 2500, previous_status: "Watch" }),
  lake("shazore", { district: "Chitral", share_of_largest: null, elevation_m: null }, { status: "Frozen (likely)", level: null }),
  lake("shisper", { district: "Nagar", lake_state: "no_lake", share_of_largest: null }, { status: "No lake now", level: null }),
  lake("karambar_lake", { district: "Ghizer", suparco: { id: 116, match: "probable", source: "PDGL" }, share_of_largest: 0.97, above_largest: true, elevation_m: 4000 }),
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
  return createOverview(root, { file: f, state, onState, onOpenLake });
}
const role = (name: string) => root.querySelector<HTMLElement>(`[data-role="${name}"]`);
const roles = (name: string) => root.querySelectorAll<HTMLElement>(`[data-role="${name}"]`);
const click = (el: Element) => el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
const tile = (filter: string) => root.querySelector<HTMLElement>(`[data-role="ov-tiles"] [data-filter="${filter}"]`)!;
const cells = (rowRole: string) => [...role(rowRole)!.querySelectorAll('[role="cell"]')].map((c) => c.textContent);
const chip = (status: string) => [...root.querySelectorAll(".ov-chip")].find((c) => c.textContent === status)!;

afterEach(() => {
  document.body.innerHTML = "";
});

describe("overview", () => {
  it("pins the needs-attention lakes and expands the first message in place", () => {
    render(file);
    expect([...roles("ov-pinned")].map((r) => r.getAttribute("data-id"))).toEqual(["alert_lake", "forming_site", "watch_lake", "decrease_lake"]);
    const m = roles("ov-message")[0];
    expect(m.getAttribute("aria-expanded")).toBe("false");
    click(m.querySelector("button")!);
    expect(m.getAttribute("aria-expanded")).toBe("true");
    for (const h of ["What changed", "How sure", "What it is not", "What to do"]) expect(m.textContent).toContain(h);
  });
  it("each count is a filter and writes the URL state", () => {
    render(file);
    click(tile("frozen"));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ show: "frozen" }));
    expect(tile("frozen").getAttribute("aria-pressed")).toBe("false");
    render(file, { ...DEFAULT_STATE, show: "frozen" });
    expect(tile("frozen").getAttribute("aria-pressed")).toBe("true");
  });
  it("an unknown district shows the empty-table message", () => {
    render(file, { ...DEFAULT_STATE, district: "Nowhere" });
    expect(role("ov-empty")!.textContent).toBe("No watched lake matches these filters.");
  });
  it("shows the mapped count only when the file has one", () => {
    render(file);
    expect(tile("all").textContent).toContain("503 more mapped, not watched yet");
    render(makeFile(file.lakes, { mapped_count: null }));
    expect(tile("all").textContent).not.toContain("more mapped");
  });
  it("a row with every new field missing renders", () => {
    render(makeFile([makeLake({ district: undefined, suparco: undefined, largest_extent: undefined, share_of_largest: undefined, elevation_m: undefined })]));
    const c = cells("ov-row");
    expect(c).toHaveLength(7);
    expect(c[0]).toContain("no SUPARCO match");
    expect(c[3]).toContain("—");
    expect(c[6]).toBe("—");
    expect(root.textContent).not.toMatch(/undefined|NaN/);
  });
  it("a status chip has a shape and words, not colour alone", () => {
    render(file);
    expect(chip("Watch").querySelector("svg[aria-hidden]")).not.toBeNull();
  });
  it("long names carry a title", () => {
    const name = "Unnamed lake C006 on the Diamer–Ghizer divide above the valley";
    render(makeFile([makeLake({ name })]));
    expect(role("ov-row")!.querySelector(`[title="${name}"]`)).not.toBeNull();
  });
  it("headers sort and announce it", () => {
    render(file);
    const h = root.querySelector<HTMLButtonElement>('[data-sort="area"]')!;
    click(h);
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "area", dir: "asc" }));
    render(file, { ...DEFAULT_STATE, sort: "area", dir: "desc" });
    expect(root.querySelector('[data-sort="area"]')!.closest("[aria-sort]")!.getAttribute("aria-sort")).toBe("descending");
    expect(root.querySelectorAll('[role="columnheader"]')).toHaveLength(7);
  });
  it("an older build without counts shows no tiles and still lists the lakes", () => {
    render(makeFile(file.lakes, { counts: undefined }));
    expect(role("ov-tiles")).toBeNull();
    expect(roles("ov-row").length + roles("ov-pinned").length).toBe(file.lakes.length);
  });
  it("has no banned claim and names the official sources", () => {
    render(file);
    expect(findBannedClaims(root.textContent!)).toEqual([]);
    expect(root.textContent).toContain("Official warnings come from PMD, NDMA, GBDMA and PDMA.");
  });
});

describe("overview details", () => {
  it("states the build, the newest pass and the next refresh", () => {
    render(makeFile(file.lakes, { newest_pass: "2026-11-09" }));
    expect(role("ov-asof")!.textContent).toBe("As of 13 Nov 2026 (data built) · latest NISAR pass 9 Nov 2026 · next refresh Mon 16 Nov 2026");
    expect(root.querySelector("h1")!.textContent).toBe("Lake Watch: 8 watched lakes");
  });
  it("without newest_pass the latest pass comes from the lakes", () => {
    render(file);
    expect(role("ov-asof")!.textContent).toContain("latest NISAR pass 9 Nov 2026");
  });
  it("rows keep the filter order and show the counts in the filter chips", () => {
    render(file, { ...DEFAULT_STATE, show: "suparco" });
    expect([...roles("ov-row")].map((r) => r.dataset.id)).toEqual(["karambar_lake"]);
    expect(role("ov-shown")!.textContent).toBe("Showing 1 of 8 watched lakes");
    const f = root.querySelector('[data-role="ov-filters"] [data-filter="suparco"]')!;
    expect(f.getAttribute("aria-pressed")).toBe("true");
    expect(f.textContent).toContain("1");
  });
  it("the district select lists each district with its count, and picking one writes the state", () => {
    render(file);
    const sel = role("ov-district") as HTMLSelectElement;
    expect([...sel.options].map((o) => o.textContent)).toEqual(["All districts", "Chitral (1)", "Ghizer (1)", "Hunza (1)", "Nagar (1)"]);
    sel.value = "Hunza";
    sel.dispatchEvent(new Event("change"));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ district: "Hunza" }));
  });
  it("search writes the state and update keeps the input", () => {
    const view = render(file);
    const input = role("ov-search") as HTMLInputElement;
    input.value = "pas";
    input.dispatchEvent(new Event("input"));
    expect(onState).toHaveBeenLastCalledWith(expect.objectContaining({ q: "pas" }));
    view.update({ ...DEFAULT_STATE, q: "pas" });
    expect(role("ov-search")).toBe(input);
    expect([...roles("ov-row")].map((r) => r.dataset.id)).toEqual(["passu"]);
  });
  it("cells: SUPARCO short line, area and change, share, latest pass and elevation", () => {
    render(file, { ...DEFAULT_STATE, show: "suparco" });
    const c = cells("ov-row");
    expect(c[0]).toContain("Ghizer · SUPARCO 116 (probable)");
    expect(c[2]).toContain("0.131");
    expect(c[2]).toContain("+0.001 km²");
    expect(c[3]).toContain("97%");
    expect(c[3]).toContain("Above");
    expect(c[5]).toContain("9 Nov");
    expect(c[5]).toContain("track 055A");
    expect(c[6]).toBe("4,000");
    expect(role("ov-row")!.querySelector("svg path.ov-spark")!.getAttribute("d")).toMatch(/^M/);
  });
  it("a share it cannot give shows — with the reason on hover", () => {
    render(makeFile([makeLake({ share_of_largest: null, share_note: "outline only 80% inside the radar window" })]));
    const share = role("ov-row")!.querySelectorAll('[role="cell"]')[3];
    expect(share.textContent).toContain("—");
    expect(share.querySelector('[title="outline only 80% inside the radar window"]')).not.toBeNull();
  });
  it("a site with no lake now shows no lake, not an area", () => {
    render(file, { ...DEFAULT_STATE, show: "no-lake" });
    expect(cells("ov-row")[2]).toContain("no lake");
  });
  it("a frozen lake's sparkline stops at its last open-water reading", () => {
    render(makeFile([frozenFixture("ice")]));
    const c = cells("ov-row");
    expect(c[2]).toContain("0.159");
    expect(c[2]).toContain("last open water 18 Sep");
    expect(role("ov-row")!.querySelector("path.ov-spark")!.getAttribute("d")!.match(/[ML]/g)).toHaveLength(5);
  });
  it("by default the rows follow the status order of sortLakes, and descending reverses them (moved from the old list)", () => {
    const rest = file.lakes.filter((l) => !["alert_lake", "forming_site", "watch_lake", "decrease_lake"].includes(l.id));
    const ids = (dir: "asc" | "desc") => {
      render(file, { ...DEFAULT_STATE, dir });
      return [...roles("ov-row")].map((r) => r.dataset.id);
    };
    expect(ids("asc")).toEqual(sortLakes(rest).map((l) => l.id));
    expect(ids("desc")).toEqual(sortLakes(rest).map((l) => l.id).reverse());
  });
  it("tile name lists read as a sentence", () => {
    expect(nameList([])).toBe("");
    expect(nameList(["A"])).toBe("A");
    expect(nameList(["A", "B"])).toBe("A and B");
    expect(nameList(["A", "B", "C"])).toBe("A, B and 1 more");
    expect(nameList(["A", "B", "C"], 3)).toBe("A, B and C");
  });
  it("column heads read as given, units included", () => {
    render(file);
    expect([...root.querySelectorAll('[role="columnheader"]')].map((h) => h.textContent!.replace(/ /g, " ").trim())).toEqual([
      "Lake · district · SUPARCO", "Status", "Area (km²)", "% of largest extent", "Trend (status track)", "Latest pass", "Elev. (m)",
    ]);
  });
  it("a possible SUPARCO match shows as no match", () => {
    render(makeFile([makeLake({ district: "Hunza", suparco: { id: 12, match: "possible", source: "PDGL" } })]));
    expect(cells("ov-row")[0]).toContain("Hunza · no SUPARCO match");
    expect(root.textContent).not.toContain("not on SUPARCO list");
  });
  it("a share of 100% or more with unknown noise says so, not Above or Within", () => {
    render(makeFile([makeLake({ share_of_largest: 1.55, above_largest: null })]));
    const share = role("ov-row")!.querySelectorAll('[role="cell"]')[3];
    expect(share.textContent).toContain("155%");
    expect(share.textContent).toContain("noise unknown");
    expect(share.textContent).not.toMatch(/Above|Within/);
    expect(share.querySelector(".ov-sub")!.getAttribute("title")).toMatch(/noise/);
  });
  it("a share of 100% or more that is not Above reads Within noise; below 100% reads Within", () => {
    render(makeFile([makeLake({ share_of_largest: 1.18, above_largest: false })]));
    let sub = role("ov-row")!.querySelectorAll('[role="cell"]')[3].querySelector(".ov-sub")!;
    expect(sub.textContent).toBe("Within noise");
    expect(sub.getAttribute("title")).toBe("Above 100% but less than 2× radar noise beyond the largest mapped outline");
    render(makeFile([makeLake({ share_of_largest: 0.96, above_largest: false })]));
    sub = role("ov-row")!.querySelectorAll('[role="cell"]')[3].querySelector(".ov-sub")!;
    expect(sub.textContent).toBe("Within");
    render(makeFile([makeLake({ share_of_largest: 1.3, above_largest: true })]));
    expect(role("ov-row")!.querySelectorAll('[role="cell"]')[3].querySelector(".ov-sub")!.textContent).toBe("Above");
  });
  it("a Not measurable lake keeps its area, greyed, as info only with the reason on hover", () => {
    const l = makeLake();
    render(makeFile([{ ...l, status: { ...l.status, status: "Not measurable", level: null, change_km2: null, reason: "Radar water failed the Sentinel-2 check (IoU 0.21)." } }]));
    const area = role("ov-row")!.querySelectorAll<HTMLElement>('[role="cell"]')[2];
    expect(area.textContent).toContain("0.131");
    expect(area.dataset.info).toBe("true");
    const sub = area.querySelector(".ov-sub")!;
    expect(sub.textContent).toBe("info only");
    expect(sub.getAttribute("title")).toBe("Radar water failed the Sentinel-2 check (IoU 0.21).");
  });
  it("one group label heads the pinned rows; rows carry no eyebrow and mark their status for the accent bar", () => {
    render(file);
    expect(role("ov-pinned-label")!.textContent).toBe("Needs attention (4)");
    expect(root.querySelectorAll(".ov-kicker")).toHaveLength(0);
    expect(root.querySelector('[data-role="ov-pinned"][data-id="watch_lake"]')!.getAttribute("data-status")).toBe("watch");
    expect(root.querySelector('[data-role="ov-pinned"][data-id="alert_lake"]')!.getAttribute("data-status")).toBe("alert-growing");
  });
  it("each sort arrow sits inside its header's text", () => {
    render(file);
    for (const b of root.querySelectorAll('[data-sort]')) expect(b.querySelector(".ov-sort-label svg")).not.toBeNull();
  });
  it("the lake name opens the lake", () => {
    render(file);
    click(role("ov-row")!.querySelector("button.ov-name")!);
    expect(onOpenLake).toHaveBeenCalledWith(role("ov-row")!.dataset.id);
  });
  it("leaves an empty actions container and a footer", () => {
    render(file);
    expect(role("ov-actions")!.childElementCount).toBe(0);
    expect(role("ov-footer")!.textContent).toContain("Screening on NISAR radar, not a warning.");
    expect(role("ov-table")!.getAttribute("role")).toBe("table");
  });
});
