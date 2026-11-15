// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { fragmentId, mountApp, routeFromHash, type AppOptions } from "./app";
import { mountOrShowError } from "./startup";
import type { LakeRequest } from "./lakeRequests";
import { findBannedClaims } from "./content";
import { fixtureLakes, makeFile, makeLake, requestedLake, withRequestedLake } from "./fixtures";
import { featuredLake, splitChecks, type LakesFile } from "./lakes";

// loaded the way the app loads it (lakes.ts loadLakes): check rows with only a note move to check_notes
const realLakes = splitChecks(lakesJson as unknown as LakesFile);
const SUPARCO =
  "Persistent cloud cover after 16 June 2026 has limited the availability of cloud-free satellite imagery, making it difficult to accurately assess lake area changes during the last three to four days.";
const BEAT_IDS = ["cloud-gap", "how-radar-sees", "lake-watch", "one-lake", "limits-next"];

afterEach(() => {
  document.body.innerHTML = "";
});

function setup(opts: AppOptions = { lakes: realLakes }) {
  const root = document.createElement("div");
  document.body.append(root);
  const app = mountApp(root, opts);
  const $ = <T extends HTMLElement = HTMLElement>(role: string): T => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { app, root, $ };
}

/** Opens the beat-by-beat Story view the way a visitor does: from the story page. */
function openStory($: (r: string) => HTMLElement): void {
  $("view-home").click();
  pageButton($, "Follow the story").click();
}

/** A copy of the fixture lakes made of watch lakes with the given looks and latest dates. */
function lakesWith(rows: [string, number, string, Partial<LakesFile["lakes"][number]>?][]): LakesFile {
  const base = fixtureLakes.lakes[2];
  return {
    ...fixtureLakes,
    lakes: rows.map(([id, looks, latest, extra]) => ({
      ...base,
      id,
      name: `Lake ${id}`,
      role: "watch" as const,
      status: { ...base.status, looks, latest_date: latest },
      ...extra,
    })),
  };
}

const TITLE = "When clouds close in, the lakes stay in view.";

/** A link-button on the story page, found by its label. */
function pageButton($: (r: string) => HTMLElement, label: string, nth = 0): HTMLAnchorElement {
  return [...$("home-root").querySelectorAll<HTMLAnchorElement>("a.sp-btn")].filter((b) => b.textContent === label)[nth];
}

describe("views", () => {
  test("starts on Lake Watch, the story page is one click away, and the logo returns to Lake Watch", () => {
    const { $ } = setup();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-view").dataset.mode).toBe("overview");
    expect($("home-root").hidden).toBe(true);
    expect($("shell").dataset.view).toBe("lakes");
    expect($("view-name").textContent).toBe("Lake Watch");
    expect(document.title).toBe("SARtale · Lake Watch");
    expect($("home").getAttribute("aria-label")).toBe("SARtale: Lake Watch");
    $("view-home").click();
    expect($("home-root").hidden).toBe(false);
    expect($("home-root").querySelector("h1")!.textContent).toBe(TITLE);
    expect(window.location.hash).toBe("#start");
    $("view-evidence").click();
    expect($("evidence-view").hidden).toBe(false);
    expect($("home-root").hidden).toBe(true);
    expect($("view-evidence").getAttribute("aria-current")).toBe("page");
    expect(document.title).toBe("SARtale · How we know");
    $("home").click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("home-root").hidden).toBe(true);
    expect(document.title).toBe("SARtale · Lake Watch");
    window.location.hash = "";
  });

  test("there is one header: logo, SARtale, the nav and the provisional pill", () => {
    const { root, $ } = setup();
    expect(root.querySelectorAll("header.top")).toHaveLength(1);
    expect($("home-root").querySelector("nav, header")).toBeNull(); // the story page renders no header of its own
    expect(root.querySelector("header.top")!.textContent).toContain("SARtale");
    expect(root.querySelector("header.top .brand")!.textContent).toBe("SARtale");
    expect(root.querySelector("header.top")!.contains($("maturity"))).toBe(true);
    expect(root.querySelector("header.top img.logo")).not.toBeNull();
  });

  test("the nav is Lake Watch, How we know, then The story, and nothing else", () => {
    const { root } = setup();
    const buttons = [...root.querySelectorAll<HTMLElement>(".views a")];
    expect(root.querySelectorAll(".views button")).toHaveLength(0);
    expect(buttons.map((b) => b.getAttribute("href"))).toEqual(["#lakes", "#evidence", "#start"]);
    expect(buttons.map((b) => b.textContent)).toEqual(["Lake Watch", "How we know", "The story"]);
    expect(buttons.map((b) => b.dataset.role)).toEqual(["view-lakes", "view-evidence", "view-home"]);
    expect(buttons[0].classList.contains("view-primary")).toBe(true);
    expect(buttons.slice(1).some((b) => b.classList.contains("view-primary"))).toBe(false);
  });

  test("navigation actions are real links, so right-click and open in a new tab work", () => {
    const { root, $ } = setup();
    expect($("home").tagName).toBe("A");
    expect($("home").getAttribute("href")).toBe("#lakes");
    expect(root.querySelectorAll("header.top button")).toHaveLength(0);
    for (const label of ["Open Lake Watch", "Follow the story"]) expect(pageButton($, label)?.getAttribute("href")).toMatch(/^#/);
    expect(pageButton($, "Follow the story").getAttribute("href")).toBe("#story");
  });

  test("a plain click is handled in the app, a modified click is left to the browser", () => {
    const { $ } = setup();
    const plain = new MouseEvent("click", { bubbles: true, cancelable: true });
    $("view-evidence").dispatchEvent(plain);
    expect(plain.defaultPrevented).toBe(true);
    expect($("evidence-view").hidden).toBe(false);
    const ctrl = new MouseEvent("click", { bubbles: true, cancelable: true, ctrlKey: true });
    $("view-home").dispatchEvent(ctrl);
    expect(ctrl.defaultPrevented).toBe(false);
    expect($("evidence-view").hidden).toBe(false);
    const middle = new MouseEvent("click", { bubbles: true, cancelable: true, button: 1 });
    $("view-home").dispatchEvent(middle);
    expect(middle.defaultPrevented).toBe(false);
  });

  test("the nav's The story link goes to the start view", () => {
    const { $ } = setup();
    $("view-lakes").click();
    expect($("view-home").getAttribute("aria-current")).toBeNull();
    $("view-home").click();
    expect($("home-root").hidden).toBe(false);
    expect($("view-home").getAttribute("aria-current")).toBe("page");
  });

  test("the provisional label is in the header on every view and in the footer, with the warning authorities", () => {
    const { root, $ } = setup();
    for (const go of [() => $("view-lakes").click(), () => openStory($), () => $("view-evidence").click(), () => $("view-home").click()]) {
      go();
      expect($("maturity").textContent).toBe("Provisional NISAR data");
      expect($("maturity").hidden).toBe(false);
    }
    expect(root.querySelector(".foot")!.textContent).toMatch(/Not an official warning service\. For warnings, use PMD, NDMA, GBDMA and PDMA/);
  });

  test("without a lakes file Lake Watch says so", () => {
    const { $ } = setup({ lakes: null });
    $("view-lakes").click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-view").textContent).toContain("No lake data in this build");
  });

  test("a #lakes, #evidence or #story hash opens that view on load", () => {
    for (const [hash, view] of [["#lakes", "lakes-view"], ["#evidence", "evidence-view"], ["#story", "lakestory-view"], ["#start", "home-root"], ["", "lakes-view"], ["#", "lakes-view"], ["#nonsense", "lakes-view"]]) {
      window.location.hash = hash;
      const { $ } = setup();
      expect($(view).hidden).toBe(false);
      document.body.innerHTML = "";
    }
    window.location.hash = "";
  });

  test("no Peshawar chapter is left anywhere on the page, and no banned claims", () => {
    const { root } = setup();
    const text = root.textContent!;
    expect(text).not.toMatch(/Peshawar|Tarbela|The Dance|Site Stories|What NISAR Missed/);
    expect(findBannedClaims(text.replace(SUPARCO, ""))).toEqual([]);
  });
});

describe("the story page as the start view", () => {
  test("keeps the screening line and the old hero markup is gone", () => {
    const { root, $ } = setup();
    expect(root.querySelector(".hero")).toBeNull();
    expect($("home-root").textContent).toContain("Official warnings come from PMD, NDMA, GBDMA and PDMA");
  });

  test("Follow the story opens the beat-by-beat Story view, which stays reachable", () => {
    const { $ } = setup();
    $("view-home").click();
    pageButton($, "Follow the story").click();
    expect($("lakestory-view").hidden).toBe(false);
    expect($("home-root").hidden).toBe(true);
    expect($("view-name").textContent).toBe("Story walkthrough");
  });

  test("Open Lake Watch and How we know on the story page switch views", () => {
    const { $ } = setup();
    $("view-home").click();
    pageButton($, "Open Lake Watch").click();
    expect($("lakes-view").hidden).toBe(false);
    $("view-home").click();
    pageButton($, "How we know").click();
    expect($("evidence-view").hidden).toBe(false);
  });

  test("the story page's lake list and Add-a-lake slot are in the story view", () => {
    const { $ } = setup();
    $("view-home").click();
    expect($("home-root").querySelector(".sp-lakes")).not.toBeNull();
    expect($("home-root").querySelector(".sp-add-slot")).not.toBeNull();
  });
});

describe("the lake story", () => {
  const beatId = ($: (r: string) => HTMLElement) => $("lakestory-view").querySelector<HTMLElement>("[data-beat]")!.dataset.beat;

  test("opens on the cloud gap and walks five beats in order", () => {
    const { $ } = setup();
    openStory($);
    expect($("view-name").textContent).toBe("Story walkthrough");
    const seen = [beatId($)];
    for (let n = 0; n < 4; n++) {
      $("ls-next").click();
      seen.push(beatId($));
    }
    expect(seen).toEqual(BEAT_IDS);
    expect($("ls-count").textContent).toBe("5 of 5");
    expect($<HTMLButtonElement>("ls-next").disabled).toBe(true);
  });

  test("beat 1 quotes SUPARCO verbatim and cites the page and date", () => {
    const { $ } = setup();
    openStory($);
    expect($("ls-quote").textContent).toBe(SUPARCO);
    expect($("lakestory-view").textContent).toContain("space4climate.gov.pk, 2 Jul 2026");
  });

  test("featuredLake picks the watch lake with most looks, ties to the newest look, never a control or story lake", () => {
    const f = lakesWith([
      ["a", 6, "2026-10-23"],
      ["b", 8, "2026-10-11"],
      ["c", 8, "2026-10-23"],
      ["ctl", 12, "2026-10-23", { role: "control" }],
      ["sto", 12, "2026-10-23", { role: "story" }],
    ]);
    expect(featuredLake(f)?.id).toBe("c");
    expect(featuredLake({ ...f, lakes: f.lakes.filter((l) => l.role !== "watch") })).toBeNull();
    // a site with no lake now, or a lake recent imagery does not confirm, is never featured
    const unsure = { ...f, lakes: f.lakes.map((l) => (l.id === "c" ? { ...l, lake_state: "no_lake" as const } : l.id === "b" ? { ...l, lake_state: "unconfirmed" as const } : l)) };
    expect(featuredLake(unsure)?.id).toBe("a");
    expect(featuredLake(null)).toBeNull();
  });

  test("beat 4 shows the lake chosen from the data, and opens it in Lake Watch", () => {
    const lakes = lakesWith([["a", 5, "2026-10-23"], ["b", 9, "2026-10-01"]]);
    const { $ } = setup({ lakes });
    openStory($);
    for (let n = 0; n < 3; n++) $("ls-next").click();
    expect(beatId($)).toBe("one-lake");
    expect($("ls-title").textContent).toContain("Lake b");
    $("lakestory-view").querySelector<HTMLButtonElement>('[data-action="lake"]')!.click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-root").hidden).toBe(false);
    expect($("lakes-root").querySelector(".lp-name")?.textContent).toBe(lakes.lakes.find((l) => l.id === "b")!.name);
    expect(window.location.hash).toBe("#lakes/b");
    window.history.replaceState(null, "", "/");
  });

  test("the last beat opens How we know", () => {
    const { $ } = setup();
    openStory($);
    for (let n = 0; n < 4; n++) $("ls-next").click();
    $("lakestory-view").querySelector<HTMLButtonElement>('[data-action="evidence"]')!.click();
    expect($("evidence-view").hidden).toBe(false);
  });

  test("no raw {token} shows in the Story view without lake data or without a watch lake", () => {
    const noWatch = { ...fixtureLakes, lakes: fixtureLakes.lakes.map((l) => ({ ...l, role: "control" as const })) };
    for (const lakes of [null, noWatch]) {
      const { $ } = setup({ lakes });
      openStory($);
      for (let n = 0; n < 5; n++) {
        expect($("lakestory-view").textContent).not.toMatch(/\{\w+\}/);
        if (n < 4) $("ls-next").click();
      }
      document.body.innerHTML = "";
    }
  });

  test("every beat is free of banned claims and of the words detect and accurate (outside the quote)", () => {
    const { $ } = setup();
    openStory($);
    for (let n = 0; n < 5; n++) {
      const text = $("lakestory-view").textContent!;
      expect(findBannedClaims(text)).toEqual([]);
      expect(text.replace(SUPARCO, "")).not.toMatch(/detect|accurate|\{\w+\}/i);
      if (n < 4) $("ls-next").click();
    }
  });
});

describe("routing", () => {
  test("test_routeFromHash_names_views_and_lakes_and_ignores_anchors", () => {
    expect(routeFromHash("")).toEqual({ view: "lakes" });
    expect(routeFromHash("#")).toEqual({ view: "lakes" });
    expect(routeFromHash("#start")).toEqual({ view: "home" });
    expect(routeFromHash("#story")).toEqual({ view: "story" });
    expect(routeFromHash("#evidence")).toEqual({ view: "evidence" });
    expect(routeFromHash("#lakes/attabad")).toEqual({ view: "lakes", lake: "attabad" });
    expect(routeFromHash("#main")).toBeNull();
    expect(routeFromHash("#lakes/<b>")).toBeNull();
  });

  test("test_switching_views_updates_the_address_and_back_returns", () => {
    window.history.replaceState(null, "", "/");
    const { $ } = setup();
    $("view-evidence").click();
    expect(window.location.hash).toBe("#evidence");
    $("view-lakes").click();
    expect(window.location.hash).toBe("#lakes");
    window.history.replaceState(null, "", "#evidence");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    expect($("view-evidence").getAttribute("aria-current")).toBe("page");
    window.history.replaceState(null, "", "/");
  });

  test("test_a_lake_hash_opens_that_lake", () => {
    const id = lakesJson.lakes[1].id;
    window.history.replaceState(null, "", `#lakes/${id}`);
    const { root, $ } = setup();
    expect($("overview-root").hidden).toBe(true);
    expect(root.querySelector(".lp-name")?.textContent).toBe(lakesJson.lakes[1].name);
    window.history.replaceState(null, "", "/");
  });

  test("#lakes and #lakes?<filters> show the overview, with the filters from the hash", () => {
    const lakes = makeFile([makeLake({ id: "a", name: "Lake A", district: "Hunza" }), makeLake({ id: "b", name: "Lake B", district: "Chitral" })]);
    window.history.replaceState(null, "", "#lakes?district=Chitral");
    const { root, $ } = setup({ lakes });
    expect($("lakes-view").hidden).toBe(false);
    expect($("overview-root").hidden).toBe(false);
    expect($("lakes-root").hidden).toBe(true);
    expect([...root.querySelectorAll<HTMLElement>('[data-role="ov-row"]')].map((r) => r.dataset.id)).toEqual(["b"]);
    window.history.replaceState(null, "", "/");
  });

  test("a filter writes the hash, a lake name opens the lake, and Lake Watch in the nav goes back to the overview", () => {
    const lakes = makeFile([makeLake({ id: "a", name: "Lake A" }), makeLake({ id: "b", name: "Lake B", district: "Chitral" })]);
    window.history.replaceState(null, "", "#lakes");
    const { root, $ } = setup({ lakes });
    root.querySelector<HTMLButtonElement>('[data-role="ov-filters"] [data-filter="suparco"]')!.click();
    expect(window.location.hash).toBe("#lakes?show=suparco");
    expect(root.querySelector('[data-role="ov-empty"]')).not.toBeNull();
    root.querySelector<HTMLButtonElement>('[data-role="ov-tiles"] [data-filter="all"]')!.click();
    expect(window.location.hash).toBe("#lakes");
    root.querySelector<HTMLButtonElement>('[data-role="ov-row"][data-id="b"] button.ov-name')!.click();
    expect(window.location.hash).toBe("#lakes/b");
    expect($("overview-root").hidden).toBe(true);
    expect($("lakes-root").querySelector(".lp-name")?.textContent).toBe("Lake B");
    $("view-lakes").click();
    expect(window.location.hash).toBe("#lakes");
    expect($("overview-root").hidden).toBe(false);
    window.history.replaceState(null, "", "/");
  });

  test("an unknown lake in the hash shows the overview", () => {
    window.history.replaceState(null, "", "#lakes/no_such_lake");
    const { $ } = setup({ lakes: makeFile([makeLake()]) });
    expect($("overview-root").hidden).toBe(false);
    window.history.replaceState(null, "", "/");
  });
});

describe("after an accept adds a lake", () => {
  test("the app mounts, pins and lists it, and #lakes/<id> opens it", () => {
    const file = withRequestedLake(realLakes);
    window.history.replaceState(null, "", `#lakes/${requestedLake.id}`);
    const { root, $ } = setup({ lakes: file });
    expect($("lakes-root").querySelector(".lp-name")?.textContent).toBe(requestedLake.name);
    $("view-lakes").click();
    expect($("lakes-view").querySelectorAll('[data-role="ov-row"], [data-role="ov-pinned"]')).toHaveLength(realLakes.lakes.length + 1);
    $("view-home").click();
    expect($("home-root").querySelectorAll(".sp-pin:not(.sp-pin-request)")).toHaveLength(realLakes.lakes.length + 1);
    expect(root.textContent).not.toMatch(/NaN|undefined/);
    window.history.replaceState(null, "", "/");
  });
});


describe("startup robustness", () => {
  test("C11: a malformed fragment does not stop the app", () => {
    expect(fragmentId("#%")).toBeNull();
    expect(fragmentId("#videos")).toBe("videos");
    history.replaceState(null, "", "#%");
    const el = document.createElement("div");
    document.body.append(el);
    expect(mountOrShowError(el, { lakes: realLakes })).not.toBeNull();
    expect(el.querySelector(".startup-error")).toBeNull();
    history.replaceState(null, "", "#");
  });

  test("R01: the app mounts without the request list and shows it when it arrives", () => {
    const { app, root } = setup({ lakes: realLakes, requests: [] });
    expect(root.querySelectorAll(".sp-request").length).toBe(0);
    app.setRequests([{ issue: 7, name: "Asked-for pond", lat: 36.0, lon: 72.5, state: "searched", passes: 4, tracks: ["084A"], first: "2026-07-01", last: "2026-10-30", reason: null, lake_id: null, created: "2026-11-04T10:00:00Z" } as LakeRequest]);
    expect(root.querySelectorAll(".sp-request").length).toBe(1);
  });
});

describe("routeFromHash, new routes", () => {
  test("routes the new hashes", () => {
    expect(routeFromHash("#lakes?show=frozen")).toEqual({ view: "lakes", query: "show=frozen" });
    expect(routeFromHash("#lakes/passu/pass/2026-11-09_055A_P05036")).toEqual({ view: "lakes", lake: "passu", pass: "2026-11-09_055A_P05036" });
    expect(routeFromHash("#lakes/passu/compare/a_1/b_2")).toEqual({ view: "lakes", lake: "passu", compare: ["a_1", "b_2"] });
    expect(routeFromHash("#lakes/passu")).toEqual({ view: "lakes", lake: "passu" });
    expect(routeFromHash("#share")).toEqual({ view: "share" });
    expect(routeFromHash("#lakes/Passu<script>")).toBeNull();
  });
});
