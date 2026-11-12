// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import lakesJson from "../public/data/lakes.json";
import { findBannedClaims } from "./content";
import storyCopy from "./content/storyPage.json";
import { fixtureLakes, requestedLake, withRequestedLake } from "./fixtures";
import frozenJson from "./frozen/lakes.json";
import { hasLakeNow, type Lake, type LakesFile } from "./lakes";
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
  it("reads every number from the frozen 11-lake file (historical fixture, latest pass 23 Oct 2026)", () => {
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
    // Invariants, not a catalogue size: a justified retirement must not fail this test. Ids are unique, the
    // Attabad control (the gate's lake) is there and holds a lake, and every site sits inside its own window.
    const ids = real.lakes.map((l) => l.id);
    expect(new Set(ids).size).toBe(ids.length);
    const attabad = real.lakes.find((l) => l.id === "attabad");
    expect(attabad && hasLakeNow(attabad) && attabad.role === "control").toBe(true);
    for (const l of real.lakes) {
      if (!l.bounds) continue;
      const [w, s, e, nn] = l.bounds;
      expect(w <= l.lon && l.lon <= e && s <= l.lat && l.lat <= nn, l.id).toBe(true);
    }
    const now = real.lakes.filter(hasLakeNow);
    expect(n.sites).toBe(String(real.lakes.length));
    expect(n.lakes).toBe(String(now.length));
    // looks at a site with no lake now are not looks at a lake
    expect(n.cloudLooks).toBe(String(now.reduce((k, l) => k + l.cloud_window_looks, 0)));
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
      "https://doi.org/10.1017/jog.2026.10131",
      "https://doi.org/10.1080/01431161.2018.1516314",
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
      expect(storyNumbers(file).sites).toBe(String(base.lakes.length + 1));
      expect(storyNumbers(file).lakes).toBe(String(base.lakes.filter(hasLakeNow).length + 1));
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
    // Not counting Attabad's water layer: it is hidden while the lake is frozen, which the weather decides.
    expect(imgs.filter((i) => !i.classList.contains("sp-water")).length).toBeGreaterThanOrEqual(5);
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
  it("each level has its own colour; the statuses without a level are other", () => {
    expect(statusClass("Alert: growing")).toBe("sp-st-alert");
    expect(statusClass("Watch")).toBe("sp-st-watch");
    expect(statusClass("Decrease noted")).toBe("sp-st-decrease");
    expect(statusClass("No change")).toBe("sp-st-stable");
    for (const s of ["Not measurable", "Not observable", "Not seen this pass", "No lake now"]) expect(statusClass(s)).toBe("sp-st-other");
    // statuses of builds made before the levels keep their colours
    expect(statusClass("Growing")).toBe("sp-st-change");
    expect(statusClass("Stable")).toBe("sp-st-stable");
  });
});

describe("story page Alert banner", () => {
  it("shows a banner at the top of the page when any lake is at Alert: growing, and none otherwise", () => {
    let opened = 0;
    const root = document.createElement("div");
    document.body.appendChild(root);
    renderStoryPage(root, fixtureLakes, { ...opts, onOpenLakes: () => void (opened += 1) });
    const banner = root.querySelector<HTMLElement>('[data-role="sp-alert-banner"]')!;
    expect(banner).not.toBeNull();
    expect(root.querySelector(".sp-page")!.firstElementChild).toBe(banner);
    expect(banner.getAttribute("role")).toBe("alert");
    expect(banner.textContent).toContain("Alert: growing at Fixture grow-new. Alert: growing: the radar water area of Fixture grow-new rose on two passes in a row.");
    expect(banner.textContent).toContain("Not an outburst forecast.");
    expect(banner.textContent).toContain("Official warnings come from PMD, NDMA, GBDMA and PDMA.");
    expect(findBannedClaims(banner.textContent!)).toEqual([]);
    banner.querySelector<HTMLButtonElement>("button")!.click();
    expect(opened).toBe(1);
    const calm = render({ ...fixtureLakes, lakes: fixtureLakes.lakes.filter((l) => l.status.status !== "Alert: growing") }).root;
    expect(calm.querySelector('[data-role="sp-alert-banner"]')).toBeNull();
    // a Watch alone makes no banner
    expect(calm.textContent).not.toContain("Alert: growing at");
  });
});

describe("a site with no lake now", () => {
  const empty = (l: Lake): Lake => ({
    ...l,
    lake_state: "no_lake",
    lake_state_source: "Sentinel-2 shows a dry basin on 17 Aug 2026",
    status: { ...l.status, status: "No lake now", change_km2: null, noise_km2: null, reason: "No lake in recent imagery." },
    images: l.images ? { ...l.images, water: null } : null,
  });
  const file = (): LakesFile => ({ ...frozen, lakes: frozen.lakes.map((l) => (l.id === "khurdopin" ? empty(l) : l)) });

  it("is counted as a site, not a lake, and its looks are not cloud-window looks of a lake", () => {
    const n = storyNumbers(file());
    const k = frozen.lakes.find((l) => l.id === "khurdopin")!;
    expect(n.sites).toBe("11");
    expect(n.lakes).toBe("10");
    expect(n.cloudLooks).toBe(String(60 - k.cloud_window_looks));
    expect(n.passes).toBe("232"); // its passes were still read
  });

  it("gets a hollow pin, a key entry, a neutral status and no area", () => {
    const { root, page } = render(file());
    const pins = [...page.mapEl.querySelectorAll(".sp-pin")];
    const hollow = pins.filter((p) => p.classList.contains("sp-pin-nolake"));
    expect(hollow).toHaveLength(1);
    expect(hollow[0].getAttribute("title")).toContain("No lake now");
    expect(page.mapEl.querySelector(".sp-key-nolake")).not.toBeNull();
    expect(page.mapEl.querySelector(".sp-map-key")?.textContent).toContain("No lake now");
    const row = [...page.listEl.children].find((r) => r.textContent?.includes("Khurdopin"))!;
    expect(row.querySelector(".sp-lake-status")?.className).toContain("sp-st-other");
    expect(row.querySelector(".sp-lake-area")?.textContent).toBe("—");
    expect(root.textContent).not.toMatch(/\{\w+\}|NaN|undefined/);
  });

  it("has no key entry when every site holds a lake", () => {
    const { page } = render(frozen);
    expect(page.mapEl.querySelector(".sp-key-nolake")).toBeNull();
  });
});


describe("a frozen Attabad on the story page (review N1)", () => {
  const base = (): Lake => frozen.lakes.find((l) => l.id === "attabad")!;
  const withLake = (a: Lake): LakesFile => ({ ...frozen, lakes: frozen.lakes.map((l) => (l.id === "attabad" ? a : l)) });
  const frozenStatus = (a: Lake) => ({ ...a.status, status: "Frozen (likely)" as const, change_km2: null, noise_km2: null, reason: "Probably frozen since 8 Jan 2027." });
  const flagNewest = (a: Lake) => a.series.map((p) => (p.date === a.images?.date && p.track === a.images?.track ? { ...p, frozen: true } : p));
  const freeze = { state: "frozen_likely", since: "2027-01-08", freeze_up: "2027-01-08", temp_through: "2027-01-20", cold_run_days: 12, warm_run_days: 0, fdd_since_sep: 80, t2m_mean_7d: -4, s2: null, reason: "Probably frozen since 8 Jan 2027." };

  it("shows the last open-water pass, its picture, water layer, area and noise, and says the lake is frozen now", () => {
    const a = base();
    const lastOpen = { date: "2026-10-16", track: "156A", area_km2: 2.0411, status: "Stable", change_km2: 0.01, noise_km2: 0.0912, looks: 6,
      images: { latest_hh: "lakes/attabad/open_latest_hh.webp", water: "lakes/attabad/open_water.webp", date: "2026-10-16", track: "156A" } };
    const lake: Lake = { ...a, status: frozenStatus(a), series: flagNewest(a), freeze, last_open: lastOpen };
    const n = storyNumbers(withLake(lake));
    expect(n.attabadArea).toBe("2.04 km²");
    expect(n.attabadNoise).toBe("±0.09");
    const { root } = render(withLake(lake));
    const measure = root.querySelector('[aria-label="04 The measure"]')!;
    const imgs = [...measure.querySelectorAll("img")].map((i) => i.getAttribute("src"));
    expect(imgs).toEqual(["data/lakes/attabad/open_latest_hh.webp", "data/lakes/attabad/open_water.webp"]);
    expect(measure.querySelector("figcaption")?.textContent).toContain("16 Oct 2026, track 156A. Blue: water read from radar");
    expect(measure.querySelector('[data-role="sp-frozen-note"]')?.textContent).toBe("Attabad Lake is frozen now (since 8 Jan 2027); this is its last open-water pass.");
    expect(measure.textContent).toContain("water on 16 Oct");
    expect(measure.querySelector(".sp-num-frozen")).toBeNull();
  });

  it("without an open-water pass, hides the water layer and greys the area with what it is not", () => {
    const a = base();
    const lake: Lake = { ...a, status: frozenStatus(a), series: flagNewest(a), freeze, last_open: null };
    const n = storyNumbers(withLake(lake));
    expect(n.attabadNoise).toBe("—");
    const { root } = render(withLake(lake));
    const measure = root.querySelector('[aria-label="04 The measure"]')!;
    expect(measure.querySelector(".sp-water")).toBeNull();
    expect(measure.querySelector("figcaption")?.textContent).toContain("Water layer hidden: not an open-water measurement while frozen.");
    expect(measure.querySelector("figcaption")?.textContent).not.toContain("Blue: water");
    const area = measure.querySelector(".sp-num-frozen")!;
    expect(area.textContent).toBe(n.attabadArea);
    expect(area.nextElementSibling?.textContent).toBe("not an open-water measurement while frozen");
    expect(measure.textContent).not.toMatch(/water on \d/);
  });

  it("an open Attabad whose pictured pass is flagged frozen also shows its last open-water pass", () => {
    const a = base();
    const lastOpen = { date: "2026-10-16", track: "156A", area_km2: 2.0411, status: "Stable", change_km2: 0.01, noise_km2: 0.0912, looks: 6, images: null };
    const lake: Lake = { ...a, series: flagNewest(a), freeze: { ...freeze, state: "open", since: null }, last_open: lastOpen };
    const { root } = render(withLake(lake));
    const measure = root.querySelector('[aria-label="04 The measure"]')!;
    expect(measure.querySelector('[data-role="sp-frozen-note"]')?.textContent).toBe("Attabad Lake's newest pass was taken while it was frozen; this is its last open-water pass.");
    expect(measure.querySelector(".sp-water")).toBeNull();
    expect(storyNumbers(withLake(lake)).attabadArea).toBe("2.04 km²");
    // the open-water pass has no picture of its own: the newest picture stays, without its water layer, and says so
    const pics = [...measure.querySelectorAll("img")];
    expect(pics.map((i) => i.getAttribute("src"))).toEqual([`data/${a.images!.latest_hh}`]);
    expect(pics[0].getAttribute("alt")).toContain("while the lake was frozen; no water layer");
    expect(measure.querySelector("figcaption")?.textContent).toMatch(/track \w+\. Water layer hidden: not an open-water measurement while frozen\.$/);
  });
});
