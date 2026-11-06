// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { mountApp, routeFromHash, type AppOptions } from "./app";
import { findBannedClaims } from "./content";
import { fixtureLakes, requestedLake, withRequestedLake } from "./fixtures";
import { featuredLake, type LakesFile } from "./lakes";

const realLakes = lakesJson as unknown as LakesFile;
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
  $("home").click();
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

/** A button on the story page, found by its label. */
function pageButton($: (r: string) => HTMLElement, label: string, nth = 0): HTMLButtonElement {
  return [...$("home-root").querySelectorAll<HTMLButtonElement>("button.sp-btn")].filter((b) => b.textContent === label)[nth];
}

describe("views", () => {
  test("starts on the story page with the cover title, and the logo goes back to it", () => {
    const { $ } = setup();
    expect($("home-root").hidden).toBe(false);
    expect($("home-root").querySelector("h1")!.textContent).toBe(TITLE);
    expect($("shell").dataset.view).toBe("home");
    expect($("view-name").textContent).toBe("The story");
    for (const v of ["lakes-view", "lakestory-view", "evidence-view"]) expect($(v).hidden).toBe(true);
    $("view-evidence").click();
    expect($("evidence-view").hidden).toBe(false);
    expect($("home-root").hidden).toBe(true);
    expect($("view-evidence").getAttribute("aria-pressed")).toBe("true");
    $("view-lakes").click();
    expect(document.title).toBe("SARtale · Lake Watch");
    $("view-evidence").click();
    expect(document.title).toBe("SARtale · How we know");
    $("home").click();
    expect($("home-root").hidden).toBe(false);
    expect(document.title).toBe("SARtale");
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

  test("the nav is The story, Lake Watch, then How we know, and nothing else", () => {
    const { root } = setup();
    const buttons = [...root.querySelectorAll<HTMLElement>(".views button")];
    expect(buttons.map((b) => b.textContent)).toEqual(["The story", "Lake Watch", "How we know"]);
    expect(buttons.map((b) => b.dataset.role)).toEqual(["view-home", "view-lakes", "view-evidence"]);
  });

  test("the nav's The story button goes to the start view", () => {
    const { $ } = setup();
    $("view-lakes").click();
    expect($("view-home").getAttribute("aria-pressed")).toBe("false");
    $("view-home").click();
    expect($("home-root").hidden).toBe(false);
    expect($("view-home").getAttribute("aria-pressed")).toBe("true");
  });

  test("the provisional label is in the header on every view and in the footer, with the warning authorities", () => {
    const { root, $ } = setup();
    for (const go of [() => $("view-lakes").click(), () => openStory($), () => $("view-evidence").click(), () => $("view-home").click()]) {
      go();
      expect($("maturity").textContent).toBe("Provisional NISAR data");
      expect($("maturity").hidden).toBe(false);
    }
    expect(root.querySelector(".foot")!.textContent).toMatch(/Not an official warning service: for warnings, use PMD, NDMA, GBDMA and PDMA/);
  });

  test("without a lakes file Lake Watch says so", () => {
    const { $ } = setup({ lakes: null });
    $("view-lakes").click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-view").textContent).toContain("No lake data in this build");
  });

  test("a #lakes, #evidence or #story hash opens that view on load", () => {
    for (const [hash, view] of [["#lakes", "lakes-view"], ["#evidence", "evidence-view"], ["#story", "lakestory-view"], ["#nonsense", "home-root"]]) {
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
    expect($("home-root").textContent).toContain("official warnings come from PMD, NDMA, GBDMA and PDMA");
  });

  test("Follow the story opens the beat-by-beat Story view, which stays reachable", () => {
    const { $ } = setup();
    pageButton($, "Follow the story").click();
    expect($("lakestory-view").hidden).toBe(false);
    expect($("home-root").hidden).toBe(true);
    expect($("view-name").textContent).toBe("Story walkthrough");
  });

  test("Open Lake Watch and How we know on the story page switch views", () => {
    const { $ } = setup();
    pageButton($, "Open Lake Watch").click();
    expect($("lakes-view").hidden).toBe(false);
    $("home").click();
    pageButton($, "How we know").click();
    expect($("evidence-view").hidden).toBe(false);
  });

  test("the story page's lake list and Add-a-lake slot are in the start view", () => {
    const { $ } = setup();
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

  test("the Lake Watch headline link goes to beat 1", () => {
    const { root, $ } = setup();
    openStory($);
    $("ls-next").click();
    $("view-lakes").click();
    root.querySelector<HTMLAnchorElement>('a[href="#cloud-gap"]')!.click();
    expect($("lakestory-view").hidden).toBe(false);
    expect(beatId($)).toBe("cloud-gap");
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
    expect($("lakes-view").querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe("b");
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
    expect(routeFromHash("")).toEqual({ view: "home" });
    expect(routeFromHash("#")).toEqual({ view: "home" });
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
    expect($("view-evidence").getAttribute("aria-pressed")).toBe("true");
    window.history.replaceState(null, "", "/");
  });

  test("test_a_lake_hash_opens_that_lake", () => {
    const id = lakesJson.lakes[1].id;
    window.history.replaceState(null, "", `#lakes/${id}`);
    const { root } = setup();
    expect(root.querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe(id);
    window.history.replaceState(null, "", "/");
  });
});

describe("after an accept adds a 12th lake", () => {
  test("the app mounts, pins and lists it, and #lakes/<id> opens it", () => {
    const file = withRequestedLake(realLakes);
    window.history.replaceState(null, "", `#lakes/${requestedLake.id}`);
    const { root, $ } = setup({ lakes: file });
    expect(root.querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe(requestedLake.id);
    expect($("lakes-view").querySelectorAll(".lw-row")).toHaveLength(realLakes.lakes.length + 1);
    $("home").click();
    expect($("home-root").querySelectorAll(".sp-pin:not(.sp-pin-request)")).toHaveLength(realLakes.lakes.length + 1);
    expect(root.textContent).not.toMatch(/NaN|undefined/);
    window.history.replaceState(null, "", "/");
  });
});
