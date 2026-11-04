// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { mountApp, type AppOptions } from "./app";
import { findBannedClaims } from "./content";
import { fixtureLakes } from "./fixtures";
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

describe("views", () => {
  test("starts on the opening screen with no view chosen, and the logo goes back to it", () => {
    const { $ } = setup();
    expect($("hero").hidden).toBe(false);
    expect($("view-name").textContent).toBe("Start");
    for (const v of ["lakes-view", "lakestory-view", "evidence-view"]) expect($(v).hidden).toBe(true);
    $("view-evidence").click();
    expect($("evidence-view").hidden).toBe(false);
    expect($("hero").hidden).toBe(true);
    expect($("view-evidence").getAttribute("aria-pressed")).toBe("true");
    $("home").click();
    expect($("hero").hidden).toBe(false);
    expect(document.title).toBe("SARtale: Start (provisional data)");
  });

  test("the nav is Lake Watch, Story, then How we know, and nothing else", () => {
    const { root } = setup();
    const order = [...root.querySelectorAll<HTMLElement>(".views button")].map((b) => b.dataset.role);
    expect(order).toEqual(["view-lakes", "view-story", "view-evidence"]);
  });

  test("the provisional label is on every view and in the footer, with the warning authorities", () => {
    const { root, $ } = setup();
    for (const r of ["hero-maturity", "lakes-maturity", "lakestory-maturity", "evidence-maturity"]) expect($(r).textContent).toBe("Provisional NISAR data");
    expect(root.querySelector(".foot")!.textContent).toMatch(/Not an official warning service: for warnings, use PMD, NDMA, GBDMA and PDMA/);
  });

  test("without a lakes file Lake Watch says so", () => {
    const { $ } = setup({ lakes: null });
    $("view-lakes").click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-view").textContent).toContain("No lake data in this build");
  });

  test("no Peshawar chapter is left anywhere on the page, and no banned claims", () => {
    const { root } = setup();
    const text = root.textContent!;
    expect(text).not.toMatch(/Peshawar|Tarbela|The Dance|Site Stories|What NISAR Missed/);
    expect(findBannedClaims(text.replace(SUPARCO, ""))).toEqual([]);
  });
});

describe("the lake start screen", () => {
  test("says who it is for and what it shows, and keeps the screening line", () => {
    const { $ } = setup();
    const text = $("hero").textContent!;
    expect(text).toContain("disaster teams in Gilgit-Baltistan and upper Khyber Pakhtunkhwa");
    expect(text).toContain("how often NISAR radar looked at each glacial lake while clouds blocked optical satellites, and whether the radar water area moved beyond its own noise");
    expect(text).toContain("Indicative screening on provisional NISAR data; official warnings come from PMD and NDMA.");
    expect($("hero-finding").hidden).toBe(false);
  });

  test("the start button opens the lake story and the other buttons reach Lake Watch and How we know", () => {
    const { $ } = setup();
    $("hero-story").click();
    expect($("lakestory-view").hidden).toBe(false);
    $("home").click();
    $("hero-lakes").click();
    expect($("lakes-view").hidden).toBe(false);
    $("home").click();
    $("hero-method").click();
    expect($("evidence-view").hidden).toBe(false);
  });

  test("shows Attabad's radar picture with a dated caption", () => {
    const a = realLakes.lakes.find((l) => l.id === "attabad")!;
    const { $ } = setup();
    expect($<HTMLImageElement>("hero-img").getAttribute("src")).toBe(`data/${a.images!.latest_hh}`);
    expect($("hero-caption").textContent).toBe(
      `Attabad Lake, Hunza: NISAR HH radar on 23 Oct 2026. The lake is the long dark band. Radar-geometry picture, not a map. Provisional data.`,
    );
  });

  test("without lakes or without Attabad images there is no picture and no caption", () => {
    const noImages = { ...realLakes, lakes: realLakes.lakes.map((l) => (l.id === "attabad" ? { ...l, images: null } : l)) };
    for (const lakes of [null, noImages]) {
      const { $ } = setup({ lakes });
      expect($<HTMLImageElement>("hero-img").hidden).toBe(true);
      expect($("hero-caption").hidden).toBe(true);
      document.body.innerHTML = "";
    }
  });
});

describe("the lake story", () => {
  const beatId = ($: (r: string) => HTMLElement) => $("lakestory-view").querySelector<HTMLElement>("[data-beat]")!.dataset.beat;

  test("opens on the cloud gap and walks five beats in order", () => {
    const { $ } = setup();
    $("view-story").click();
    expect($("view-name").textContent).toBe("Story");
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
    $("view-story").click();
    expect($("ls-quote").textContent).toBe(SUPARCO);
    expect($("lakestory-view").textContent).toContain("space4climate.gov.pk, 2 Jul 2026");
  });

  test("the Lake Watch headline link goes to beat 1", () => {
    const { root, $ } = setup();
    $("view-story").click();
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
    $("view-story").click();
    for (let n = 0; n < 3; n++) $("ls-next").click();
    expect(beatId($)).toBe("one-lake");
    expect($("ls-title").textContent).toContain("Lake b");
    $("lakestory-view").querySelector<HTMLButtonElement>('[data-action="lake"]')!.click();
    expect($("lakes-view").hidden).toBe(false);
    expect($("lakes-view").querySelector('.lw-row[aria-pressed="true"]')?.getAttribute("data-lake-id")).toBe("b");
  });

  test("the last beat opens How we know", () => {
    const { $ } = setup();
    $("view-story").click();
    for (let n = 0; n < 4; n++) $("ls-next").click();
    $("lakestory-view").querySelector<HTMLButtonElement>('[data-action="evidence"]')!.click();
    expect($("evidence-view").hidden).toBe(false);
  });

  test("no raw {token} shows in the Story view without lake data or without a watch lake", () => {
    const noWatch = { ...fixtureLakes, lakes: fixtureLakes.lakes.map((l) => ({ ...l, role: "control" as const })) };
    for (const lakes of [null, noWatch]) {
      const { $ } = setup({ lakes });
      $("view-story").click();
      for (let n = 0; n < 5; n++) {
        expect($("lakestory-view").textContent).not.toMatch(/\{\w+\}/);
        if (n < 4) $("ls-next").click();
      }
      document.body.innerHTML = "";
    }
  });

  test("every beat is free of banned claims and of the words detect and accurate (outside the quote)", () => {
    const { $ } = setup();
    $("view-story").click();
    for (let n = 0; n < 5; n++) {
      const text = $("lakestory-view").textContent!;
      expect(findBannedClaims(text)).toEqual([]);
      expect(text.replace(SUPARCO, "")).not.toMatch(/detect|accurate|\{\w+\}/i);
      if (n < 4) $("ls-next").click();
    }
  });
});
