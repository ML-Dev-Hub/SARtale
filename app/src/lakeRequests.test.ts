// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { findBannedClaims } from "./content";
import storyCopy from "./content/storyPage.json";
import { fixtureLakes } from "./fixtures";
import { checkRequest, issueUrl, loadRequests, mountAddLake, requestLine, type LakeRequest } from "./lakeRequests";
import { renderStoryPage } from "./storyPage";

const row = (o: Partial<LakeRequest> = {}): LakeRequest => ({
  issue: 7, name: "Test lake", lat: 36.42, lon: 74.88, state: "searched", passes: null, tracks: [], first: null, last: null, reason: null, lake_id: null, created: "2026-11-04T10:00:00Z", ...o,
});
const form = { name: "Test lake", lat: "36.42", lon: "74.88", source: "manual test" };
const watched = fixtureLakes.lakes;

afterEach(() => document.body.replaceChildren());

describe("issueUrl", () => {
  it("prefills every field", () => {
    const f = { name: "Lake & co #1", lat: "36.42", lon: "74.88", source: "Inventory, p. 4" };
    const u = new URL(issueUrl(f));
    expect(u.origin + u.pathname).toBe("https://github.com/saeedahmadicp/SARtale/issues/new");
    expect(u.searchParams.get("template")).toBe("add-lake.yml");
    expect(u.searchParams.get("title")).toBe("Add a lake: Lake & co #1");
    for (const k of ["name", "lat", "lon", "source"] as const) expect(u.searchParams.get(k)).toBe(f[k]);
    expect(issueUrl(f)).toContain("title=Add%20a%20lake%3A%20Lake%20%26%20co%20%231");
  });
});

describe("loadRequests", () => {
  const reply = (body: unknown, ok = true) => (async () => ({ ok, json: async () => body })) as unknown as typeof fetch;
  it("a bad shape or failure is empty", async () => {
    expect(await loadRequests("x", reply({ requests: "no" }))).toEqual([]);
    expect(await loadRequests("x", reply([]))).toEqual([]);
    expect(await loadRequests("x", reply({ requests: [] }, false))).toEqual([]);
    expect(await loadRequests("x", (async () => { throw new TypeError("down"); }) as unknown as typeof fetch)).toEqual([]);
  });
  it("returns the requests", async () => {
    expect(await loadRequests("x", reply({ updated: null, requests: [row()] }))).toEqual([row()]);
  });
});

describe("checkRequest", () => {
  it("applies the same rules as the Python validate", () => {
    expect(checkRequest(form, watched, [])).toBeNull();
    expect(checkRequest({ ...form, lat: "40" }, watched, [])).toBe("The point must be in Gilgit-Baltistan or upper KP: 34.4–37.6 °N, 70.8–76.6 °E.");
    expect(checkRequest({ ...form, lat: "abc" }, watched, [])).toBe("lat must be a number.");
    expect(checkRequest({ ...form, name: "x" }, watched, [])).toBe("name must be 2–80 characters.");
    expect(checkRequest({ ...form, source: "ab" }, watched, [])).toBe("source must be 3–200 characters.");
    expect(checkRequest({ ...form, name: "ab​cd" }, watched, [])).toBe("name must not contain control or invisible formatting characters.");
    const w = watched[0];
    expect(checkRequest({ ...form, lat: String(w.lat), lon: String(w.lon) }, watched, [])).toBe(`Already watched: ${w.name}.`);
  });
  it("blocks near a live request and ignores invalid or rejected ones", () => {
    for (const state of ["searched", "too_few_passes", "check_failed", "accepted"] as const)
      expect(checkRequest(form, watched, [row({ state, issue: 12 })])).toBe("Already requested: issue #12.");
    for (const state of ["invalid", "rejected"] as const) expect(checkRequest(form, watched, [row({ state })])).toBeNull();
  });
});

describe("requestLine", () => {
  it("words all six states", () => {
    expect(requestLine(row({ state: "searched", passes: 14, tracks: ["055A", "156A"] }))).toBe("Searched: 14 NISAR passes on tracks 055A, 156A");
    expect(requestLine(row({ state: "too_few_passes", passes: 2 }))).toBe("Searched: 2 NISAR passes, fewer than 3");
    expect(requestLine(row({ state: "check_failed", reason: "catalogue unreachable" }))).toBe("Search failed: catalogue unreachable");
    expect(requestLine(row({ state: "accepted" }))).toBe("Accepted");
    expect(requestLine(row({ state: "rejected", reason: "duplicate" }))).toBe("Not added: duplicate");
    expect(requestLine(row({ state: "rejected" }))).toBe("Not added");
    expect(requestLine(row({ state: "invalid", reason: "no coordinates" }))).toBe("Not valid: no coordinates");
  });
});

function mount(requests: LakeRequest[] = []) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const open = vi.fn();
  mountAddLake(root, { watched, requests, open });
  return { root, open };
}
function fill(root: HTMLElement, v: typeof form) {
  for (const [label, value] of [["Lake name", v.name], ["Latitude", v.lat], ["Longitude", v.lon], ["Where the coordinates", v.source]])
    [...root.querySelectorAll("label")].find((l) => l.textContent?.startsWith(label))!.querySelector("input")!.value = value;
}
const submit = (root: HTMLElement) => root.querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));

describe("add a lake form", () => {
  it("submit opens the issue and shows the finish card", () => {
    const { root, open } = mount();
    fill(root, form);
    submit(root);
    expect(open).toHaveBeenCalledWith(issueUrl(form));
    const card = root.querySelector(".sp-add-card")!;
    expect(card.textContent).toContain("Almost done: press Submit new issue on GitHub. The team reviews every request.");
    const a = card.querySelector("a")!;
    expect(a.textContent).toBe("See all requests");
    expect(a.getAttribute("href")).toBe("https://github.com/saeedahmadicp/SARtale/issues?q=label%3Alake-request");
  });

  it("an error is shown and nothing opens", () => {
    const { root, open } = mount();
    fill(root, { ...form, lat: "99" });
    submit(root);
    expect(open).not.toHaveBeenCalled();
    expect(root.querySelector('[role="alert"]')!.textContent).toMatch(/Gilgit-Baltistan/);
  });
});

describe("requests on the story page", () => {
  const options = { onOpenLakes() {}, onOpenEvidence() {}, onFollowStory() {} };

  it("a name with HTML renders as text", () => {
    const name = "<img src=x onerror=alert(1)>";
    const page = document.createElement("div");
    document.body.appendChild(page);
    const sp = renderStoryPage(page, fixtureLakes, { ...options, requests: [row({ name })] });
    expect(sp.listEl.querySelector(".sp-request")!.textContent).toContain(name);
    expect(page.querySelector("img[src='x']")).toBeNull();
  });

  it("live requests appear as cards without a lake status; invalid and rejected do not", () => {
    const page = document.createElement("div");
    document.body.appendChild(page);
    const requests = [row({ name: "<b>Hidden lake</b>", passes: 5, tracks: ["055A"] }), row({ issue: 8, name: "Bad", state: "invalid" }), row({ issue: 9, name: "No", state: "rejected" })];
    const sp = renderStoryPage(page, fixtureLakes, { ...options, requests });
    const cards = sp.listEl.querySelectorAll(".sp-request");
    expect(cards).toHaveLength(1);
    expect(cards[0].textContent).toContain("Searched: 5 NISAR passes on tracks 055A");
    expect(cards[0].querySelector("b")).toBeNull();
    expect(cards[0].querySelector(".sp-lake-status")).toBeNull();
    expect(sp.mapEl.querySelectorAll(".sp-pin-request")).toHaveLength(1);
  });

  it("the add-a-lake copy passes the claims check", () => {
    const raw = JSON.stringify(storyCopy.add);
    expect(findBannedClaims(raw)).toEqual([]);
    expect(raw).not.toMatch(/detect/i);
  });
});
