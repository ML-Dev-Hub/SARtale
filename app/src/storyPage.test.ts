// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { findBannedClaims } from "./content";
import storyCopy from "./content/storyPage.json";
import { fixtureLakes, requestedLake, withRequestedLake } from "./fixtures";
import frozenJson from "./frozen/lakes.json";
import type { LakesFile } from "./lakes";
import { mapPin, renderStoryPage, statusClass, storyNumbers } from "./storyPage";

/** The data this build ships. A rebuild replaces it, so tests on it check only what holds for any build. */
const real = lakesJson as unknown as LakesFile;
/** A frozen copy of the 23 Oct 2026 build, for the tests that check exact numbers. */
const frozen = frozenJson as unknown as LakesFile;
const opts = { onOpenLakes() {}, onOpenEvidence() {}, onFollowStory() {} };

function render(file: LakesFile | null) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const page = renderStoryPage(root, file, opts);
  return { root, page };
}

describe("storyNumbers", () => {
  it("reads every number from the file", () => {
    const n = storyNumbers(frozen);
    expect(n.lakes).toBe("11");
    expect(n.cloudLooks).toBe("60");
    expect(n.passes).toBe("232");
    expect(n.attabadArea).toBe("2.08 km²");
    expect(n.attabadNoise).toBe("±0.52");
    expect(n.attabadLooks).toBe("7");
    expect(n.attabadTrack).toBe("156A");
    expect(n.iou).toBe("IoU 0.013–0.09");
    expect(n.latest).toBe("23 Oct 2026");
  });

  it("reads the shipped file's own totals, whatever it holds", () => {
    const n = storyNumbers(real);
    expect(real.lakes.length).toBeGreaterThanOrEqual(11);
    expect(real.lakes.some((l) => l.id === "attabad")).toBe(true);
    expect(n.lakes).toBe(String(real.lakes.length));
    expect(n.cloudLooks).toBe(String(real.lakes.reduce((k, l) => k + l.cloud_window_looks, 0)));
    expect(n.passes).toBe(String(real.lakes.reduce((k, l) => k + l.series.length, 0)));
    for (const v of Object.values(n)) expect(v).not.toMatch(/NaN|undefined/);
  });

  it("gives a dash for everything when there is no file", () => {
    for (const v of Object.values(storyNumbers(null))) expect(v).toBe("—");
  });
});

describe("renderStoryPage without lakes.json", () => {
  it("shows a dash in every slot and no {token} or NaN", () => {
    const { root } = render(null);
    const text = root.textContent ?? "";
    expect(text).not.toMatch(/[{}]/);
    expect(text).not.toContain("NaN");
    expect(text).not.toContain("undefined");
    expect(text).toContain("—");
  });

  it("takes the look count and observable share from the constants", () => {
    const body = (file: LakesFile) => {
      const t = render(file).root.querySelector("section[aria-label='06 Add a lake']")!.textContent ?? "";
      const shadow = render(file).root.querySelector(".sp-shadow")!.textContent ?? "";
      return { t, shadow };
    };
    const a = body(real);
    expect(a.t).toContain("once it has three looks on one track");
    expect(a.t).toContain("after three looks on one track");
    expect(a.shadow).toContain("less than half of a lake's zone");
    const other = { ...real, constants: { ...real.constants, min_looks: 12, min_observable: 0.6 } } as LakesFile;
    const b = body(other);
    expect(b.t).toContain("once it has 12 looks on one track");
    expect(b.t).not.toContain("three looks");
    expect(b.shadow).toContain("less than 60% of a lake's zone");
  });

  it("copes with a file that has no Attabad", () => {
    const { root } = render(fixtureLakes);
    expect(root.textContent).not.toMatch(/[{}]|NaN|undefined/);
  });
});

describe("renderStoryPage", () => {
  it("links the SUPARCO quote to the status page", () => {
    const { root } = render(real);
    const quote = root.querySelector("blockquote a") as HTMLAnchorElement;
    expect(quote.getAttribute("href")).toBe("https://space4climate.gov.pk/glof-status-update/");
    expect(quote.textContent).toContain("Persistent cloud cover after 16 June 2026");
  });

  it("has the parts in order, with the shadow panel inside 03", () => {
    const { root } = render(real);
    const labels = [...root.querySelectorAll("section[aria-label]")].map((s) => s.getAttribute("aria-label"));
    expect(labels).toEqual(["Cover", "01 The risk", "02 The gap", "03 The view", "04 The measure", "05 The watch", "06 Add a lake", "07 The videos", "Open Lake Watch"]);
    const view = root.querySelector('section[aria-label="03 The view"]')!;
    expect(view.querySelector(".sp-shadow")?.textContent).toContain("Mountains cast shadows too");
    expect([...view.querySelectorAll(".sp-shadow a")].map((a) => a.getAttribute("href"))).toEqual([
      "https://arxiv.org/abs/2512.24117",
      "https://www.cambridge.org/core/product/DCA97C3F4AF86441028995F9A1656879/core-reader",
      "https://informahealthcare.com/doi/full/10.1080/01431161.2018.1516314",
    ]);
  });

  it("renders no header or nav of its own", () => {
    const { root } = render(real);
    expect(root.querySelector("header, nav")).toBeNull();
  });

  it("exposes the add-a-lake slot with its form, the lake list and the map", () => {
    const { root, page } = render(frozen);
    expect(page.addLakeEl.querySelector("form")).not.toBeNull();
    expect(root.querySelector('section[aria-label="06 Add a lake"]')!.contains(page.addLakeEl)).toBe(true);
    expect(page.listEl.children.length).toBe(11);
    expect(page.mapEl.querySelectorAll(".sp-pin").length).toBe(11);
    // sorted by area, largest first
    expect(page.listEl.children[0].textContent).toContain("Attabad");
  });

  it("lists and pins every lake of the shipped file", () => {
    const { page } = render(real);
    expect(page.listEl.children.length).toBe(real.lakes.length);
    expect(page.mapEl.querySelectorAll(".sp-pin").length).toBe(real.lakes.length);
  });

  it("takes a 12th lake that has no NISAR pass yet, as the rebuild after an accept writes it", () => {
    for (const base of [frozen, real]) {
      const file = withRequestedLake(base);
      const { root, page } = render(file);
      const text = root.textContent ?? "";
      expect(text).not.toMatch(/\{\w+\}|NaN|undefined/);
      expect(page.listEl.children.length).toBe(base.lakes.length + 1);
      expect(page.mapEl.querySelectorAll(".sp-pin").length).toBe(base.lakes.length + 1);
      expect(page.listEl.textContent).toContain(requestedLake.name);
      expect(storyNumbers(file).lakes).toBe(String(base.lakes.length + 1));
      expect(storyNumbers(file).passes).toBe(storyNumbers(base).passes);
      expect(findBannedClaims(text)).toEqual([]);
    }
    expect(withRequestedLake(frozen).lakes).toHaveLength(12);
  });

  it("plays both videos with captions on, a poster and a download link", () => {
    const { root } = render(real);
    const section = root.querySelector("section#videos")!;
    const videos = [...section.querySelectorAll("video")];
    expect(videos.map((v) => v.querySelector("source")?.getAttribute("src"))).toEqual([
      "media/SARtale-lake-watch-demo.mp4",
      "media/SARtale-how-it-works.mp4",
    ]);
    for (const v of videos) {
      const src = v.querySelector("source")!.getAttribute("src")!;
      expect(v.controls).toBe(true);
      expect(v.getAttribute("preload")).toBe("metadata");
      expect(v.getAttribute("poster")).toBe(src.replace("media/", "media/posters/").replace(".mp4", ".jpg"));
      expect(v.getAttribute("aria-label")).toBeTruthy();
      const track = v.querySelector("track")!;
      expect([track.kind, track.srclang, track.default]).toEqual(["captions", "en", true]);
      expect(track.getAttribute("src")).toBe(src.replace(".mp4", ".vtt"));
      expect(v.querySelector("a")?.getAttribute("href")).toBe(src);
      expect(v.closest("figure")?.querySelector("figcaption h3")?.textContent).toBeTruthy();
    }
    expect(root.querySelector('.sp-cover a[href="#videos"]')?.textContent).toBe("Watch the videos");
  });

  it("every image has alt text and a visible source line", () => {
    const { root } = render(real);
    const imgs = [...root.querySelectorAll("img")];
    expect(imgs.length).toBeGreaterThanOrEqual(6);
    for (const img of imgs) {
      expect(img.getAttribute("alt")?.trim()).toBeTruthy();
      const holder = img.closest("figure, section")!;
      const credit = holder.querySelector("figcaption, .sp-credit");
      expect(credit?.textContent?.trim()).toBeTruthy();
    }
  });

  it("wires the buttons to the callbacks", () => {
    const calls: string[] = [];
    const root = document.createElement("div");
    renderStoryPage(root, real, {
      onOpenLakes: () => calls.push("lakes"),
      onOpenEvidence: () => calls.push("evidence"),
      onFollowStory: () => calls.push("story"),
    });
    root.querySelectorAll<HTMLButtonElement>("button").forEach((b) => b.click());
    expect(calls).toContain("lakes");
    expect(calls).toContain("evidence");
    expect(calls).toContain("story");
  });

  it("destroy empties the root", () => {
    const { root, page } = render(real);
    page.destroy();
    expect(root.childElementCount).toBe(0);
  });

  it("has no banned claims and never says detect", () => {
    const { root } = render(real);
    const text = root.textContent ?? "";
    expect(findBannedClaims(text)).toEqual([]);
    expect(text).not.toMatch(/detect/i);
    const raw = JSON.stringify(storyCopy);
    expect(findBannedClaims(raw)).toEqual([]);
    expect(raw).not.toMatch(/detect/i);
  });
});

describe("closing band wording follows the IoU values", () => {
  const check = (iou: number) => ({ lake: "x", nisar_date: "2026-10-01", nisar_track: "1", s2_date: "2026-10-01", s2_id: "s", days_apart: 0, s2_window_cloud_pct: 0, scope: "w", radar_km2: 1, optical_km2: 1, area_error_pct: 0, iou, zone_valid_share: 1, window_radar_km2: 1, window_optical_km2: 1, window_area_error_pct: 0, window_iou: iou });
  const closing = (file: LakesFile) => render(file).root.querySelector(".sp-closing-text p")!.textContent ?? "";

  it("says poorly when every IoU is low", () => {
    expect(closing(frozen)).toContain("overlapped optical water poorly");
    expect(closing(frozen)).toContain("IoU 0.013–0.09");
  });

  it("does not say poorly when the IoU is high", () => {
    const text = closing({ ...fixtureLakes, checks: [check(0.8), check(0.7)] });
    expect(text).not.toContain("poorly");
    expect(text).toContain("overlapped optical water with IoU 0.7–0.8 across the 2 lakes checked");
  });

  it("drops the sentence when there are no checks", () => {
    expect(closing(fixtureLakes)).not.toContain("Sentinel-2");
  });
});

describe("mapPin", () => {
  it("places Attabad inside the map and refuses a point outside", () => {
    expect(mapPin(74.86, 36.33)).toEqual({ left: "70.0%", top: "39.7%" });
    expect(mapPin(70.0, 36)).toBeNull();
    expect(mapPin(74, 38)).toBeNull();
    expect(mapPin(77, 36)).toBeNull();
    expect(mapPin(74, 34)).toBeNull();
  });
});

describe("story page status colours", () => {
  it("only a confirmed change gets the change colour", () => {
    expect(statusClass("Growing")).toBe("sp-st-change");
    expect(statusClass("Shrinking")).toBe("sp-st-change");
    expect(statusClass("Stable")).toBe("sp-st-stable");
    expect(statusClass("Change not confirmed yet")).toBe("sp-st-other");
  });
});
