// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findBannedClaims } from "./content";
import storyCopy from "./content/storyPage.json";
import { fixtureLakes } from "./fixtures";
import { createRequestsClient, mountAddLake, requestLine, type LakeRequest } from "./lakeRequests";
import { renderStoryPage } from "./storyPage";

const row = (o: Partial<LakeRequest> = {}): LakeRequest => ({
  id: 1, name: "Test lake", lat: 36.42, lon: 74.88, state: "queued", passes: null, tracks: [], first: null, last: null, reason: null, created: "2026-11-04T10:00:00Z", ...o,
});

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

interface Fake {
  rows: LakeRequest[];
  fetch: typeof fetch;
  posts: unknown[];
  postReply?: () => Response;
  down: boolean;
  lists: number;
}

function fakeServer(): Fake {
  const s: Fake = {
    rows: [],
    posts: [],
    down: false,
    lists: 0,
    fetch: (async (url: string, init?: RequestInit) => {
      if (s.down) throw new TypeError("network down");
      if (String(url).endsWith("/health")) return json(200, { ok: true, open: s.rows.length });
      if (init?.method === "POST") {
        s.posts.push(JSON.parse(String(init.body)));
        return s.postReply ? s.postReply() : json(201, s.rows[0]);
      }
      s.lists++;
      return json(200, { requests: s.rows });
    }) as unknown as typeof fetch,
  };
  return s;
}

const tick = () => vi.advanceTimersByTimeAsync(0);

async function setup(s: Fake, onChange: (o: LakeRequest[]) => void = () => {}) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const handle = mountAddLake(root, createRequestsClient(s.fetch), onChange);
  await tick();
  return { root, handle };
}

function fill(root: HTMLElement, v: { name: string; lat: string; lon: string; source: string }) {
  const set = (label: string, value: string) => {
    const input = [...root.querySelectorAll("label")].find((l) => l.textContent?.startsWith(label))!.querySelector("input")!;
    input.value = value;
  };
  set("Lake name", v.name);
  set("Latitude", v.lat);
  set("Longitude", v.lon);
  set("Where the coordinates", v.source);
}

async function submit(root: HTMLElement) {
  root.querySelector("form")!.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  await tick();
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  document.body.replaceChildren();
});

describe("requestLine", () => {
  it("words each state, never as a lake status", () => {
    expect(requestLine(row())).toBe("Queued");
    expect(requestLine(row({ state: "searched", passes: 14, tracks: ["055A", "156A"] }))).toBe("Searched: 14 NISAR passes on tracks 055A, 156A");
    expect(requestLine(row({ state: "search_failed", reason: "catalogue unreachable" }))).toBe("Search failed: catalogue unreachable");
  });
});

describe("add a lake form", () => {
  it("with no server the form is disabled and says requests are not open on this copy of the site", async () => {
    const s = fakeServer();
    s.down = true;
    const { root } = await setup(s);
    expect(root.textContent).toContain("Requests are not open on this copy of the site.");
    for (const i of root.querySelectorAll("input, button")) expect((i as HTMLInputElement).disabled).toBe(true);
  });

  it("a health reply that is not ok also disables the form", async () => {
    const s = fakeServer();
    s.fetch = (async () => json(200, { ok: false })) as unknown as typeof fetch;
    const { root } = await setup(s);
    expect(root.textContent).toContain("Requests are not open on this copy of the site.");
  });

  it("a submit shows the queued request and then its searched line after a poll", async () => {
    const s = fakeServer();
    const seen: LakeRequest[][] = [];
    const { root } = await setup(s, (o) => seen.push(o));
    for (const i of root.querySelectorAll("input, button")) expect((i as HTMLInputElement).disabled).toBe(false);
    s.rows = [row()];
    fill(root, { name: "Test lake", lat: "36.42", lon: "74.88", source: "manual test" });
    await submit(root);
    expect(s.posts).toEqual([{ name: "Test lake", lat: "36.42", lon: "74.88", source: "manual test" }]);
    const card = root.querySelector(".sp-add-card")!;
    expect(card.textContent).toContain("Test lake");
    expect(card.textContent).toContain("Queued");
    s.rows = [row({ state: "searched", passes: 14, tracks: ["055A", "156A"] })];
    await vi.advanceTimersByTimeAsync(5000);
    expect(root.querySelector(".sp-add-card")!.textContent).toContain("Searched: 14 NISAR passes on tracks 055A, 156A");
    expect(seen.at(-1)).toEqual(s.rows);
  });

  it("stops polling after a minute", async () => {
    const s = fakeServer();
    const { root } = await setup(s);
    s.rows = [row()];
    fill(root, { name: "Test lake", lat: "36.42", lon: "74.88", source: "manual test" });
    await submit(root);
    await vi.advanceTimersByTimeAsync(60000);
    const after = s.lists;
    expect(after).toBeGreaterThan(5);
    await vi.advanceTimersByTimeAsync(30000);
    expect(s.lists).toBe(after);
  });

  it("the server's 400 and 429 messages are shown as written", async () => {
    const s = fakeServer();
    const { root } = await setup(s);
    fill(root, { name: "x", lat: "99", lon: "74", source: "s" });
    s.postReply = () => json(400, { error: "Latitude must be between 34.4 and 37.6." });
    await submit(root);
    expect(root.querySelector('[role="alert"]')!.textContent).toBe("Latitude must be between 34.4 and 37.6.");
    s.postReply = () => json(429, { error: "Too many requests today. Try again tomorrow." });
    await submit(root);
    expect(root.querySelector('[role="alert"]')!.textContent).toBe("Too many requests today. Try again tomorrow.");
  });

  it("a failed fetch shows the approved network wording, not the browser text", async () => {
    const s = fakeServer();
    const { root } = await setup(s);
    fill(root, { name: "x", lat: "36.2", lon: "73.9", source: "s" });
    const inner = s.fetch;
    s.fetch = ((u: string, i?: RequestInit) => (i?.method === "POST" ? Promise.reject(new TypeError("Failed to fetch")) : inner(u, i))) as typeof fetch;
    const root2 = document.createElement("div");
    document.body.appendChild(root2);
    mountAddLake(root2, createRequestsClient(s.fetch), () => {});
    await tick();
    fill(root2, { name: "x", lat: "36.2", lon: "73.9", source: "s" });
    await submit(root2);
    const text = root2.querySelector('[role="alert"]')!.textContent;
    expect(text).toBe(storyCopy.add.form.networkError);
    expect(text).not.toContain("Failed to fetch");
  });

  it("a name with HTML is shown as text", async () => {
    const s = fakeServer();
    const name = "<img src=x onerror=alert(1)>";
    s.rows = [row({ name })];
    const { root } = await setup(s);
    fill(root, { name, lat: "36.42", lon: "74.88", source: "manual test" });
    await submit(root);
    expect(root.querySelector(".sp-add-card")!.textContent).toContain(name);
    expect(root.querySelector("img")).toBeNull();
  });
});

describe("open requests on the story page", () => {
  it("appear in the lake list and on the map as Queued, never with a lake status", async () => {
    const s = fakeServer();
    s.rows = [row({ name: "<b>Hidden lake</b>" }), row({ id: 2, name: "Done lake", state: "accepted" })];
    const root = document.createElement("div");
    document.body.appendChild(root);
    const page = renderStoryPage(root, fixtureLakes, { onOpenLakes() {}, onOpenEvidence() {}, onFollowStory() {}, requests: createRequestsClient(s.fetch) });
    await tick();
    const cards = page.listEl.querySelectorAll(".sp-request");
    expect(cards).toHaveLength(1);
    expect(cards[0].textContent).toContain("<b>Hidden lake</b>");
    expect(cards[0].textContent).toContain("Queued");
    expect(cards[0].querySelector("b")).toBeNull();
    expect(cards[0].querySelector(".sp-lake-status")).toBeNull();
    for (const w of ["Stable", "Growing", "Shrinking", "Insufficient"]) expect(cards[0].textContent).not.toContain(w);
    expect(page.mapEl.querySelectorAll(".sp-pin-request")).toHaveLength(1);
    expect(page.mapEl.querySelectorAll(".sp-pin:not(.sp-pin-request)").length).toBeGreaterThan(0);
  });

  it("the add-a-lake copy passes the claims check", () => {
    const raw = JSON.stringify(storyCopy.add);
    expect(findBannedClaims(raw)).toEqual([]);
    expect(raw).not.toMatch(/detect/i);
  });
});

describe("createRequestsClient base", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("uses VITE_REQUESTS_API when set and 'api' otherwise", async () => {
    const urls: string[] = [];
    const f = (async (url: string) => {
      urls.push(url);
      return json(200, { ok: true, open: 0 });
    }) as unknown as typeof fetch;
    await createRequestsClient(f).health();
    vi.stubEnv("VITE_REQUESTS_API", "https://lakes.example.org/api");
    await createRequestsClient(f).health();
    expect(urls).toEqual(["api/health", "https://lakes.example.org/api/health"]);
  });
});
