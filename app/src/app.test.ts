// @vitest-environment jsdom
import { afterEach, describe, expect, test, vi } from "vitest";
import { mountApp, type MapHost } from "./app";
import { findBannedClaims } from "./content";
import { calibratedManifest, FORECAST_FLAG, fixtureManifest, INTERFERENCE_FLAG, previewManifest } from "./fixtures";
import type { MapLike } from "./map";
import type { Site } from "./types";

function fakeMap(fail = false): MapLike & { urls: string[] } {
  const urls: string[] = [];
  return {
    urls,
    setImage: async (url) => {
      if (fail) throw new Error("image 404");
      urls.push(url);
    },
  };
}

function setup(manifest = fixtureManifest, failing = false, opts?: Parameters<typeof mountApp>[3], hostExtra: Partial<MapHost> = {}) {
  const root = document.createElement("div");
  document.body.append(root);
  const host = { after: fakeMap(failing), before: fakeMap() } satisfies MapHost;
  const app = mountApp(root, manifest, () => ({ ...host, ...hostExtra }), opts);
  const $ = <T extends HTMLElement>(role: string) => root.querySelector<T>(`[data-role="${role}"]`)!;
  return { root, host, app, $ };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("app shell", () => {
  test("provisional data shows the provisional label", async () => {
    const { app, $ } = setup();
    await app.settled();
    expect($("maturity").textContent).toBe("Provisional NISAR data");
    expect($("maturity").dataset.kind).toBe("provisional");
  });

  test("non-provisional data shows the permanent synthetic banner", async () => {
    const { app, $ } = setup({ ...fixtureManifest, maturity: "Synthetic demo" });
    await app.settled();
    expect($("maturity").textContent).toBe("SYNTHETIC DEMO: NOT NISAR DATA");
    expect($("maturity").dataset.kind).toBe("synthetic");
    expect($("maturity").hidden).toBe(false);
  });

  test("moving the slider shows that date's frame", async () => {
    const { app, host, $ } = setup();
    const slider = $<HTMLInputElement>("slider");
    slider.value = "2";
    slider.dispatchEvent(new Event("input"));
    await app.settled();
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-07-26_HH.webp");
  });

  test("switching polarization shows the HV frame", async () => {
    const { app, host, root } = setup();
    const hv = root.querySelector<HTMLInputElement>('input[value="HV"]')!;
    hv.checked = true;
    hv.dispatchEvent(new Event("change", { bubbles: true }));
    await app.settled();
    expect(host.after.urls.at(-1)).toBe("data/frames/2026-07-02_HV.webp");
  });

  test("composite on shows the composite and locks the date controls", async () => {
    const { app, host, $ } = setup();
    $("composite-toggle").click();
    await app.settled();
    expect(host.after.urls.at(-1)).toBe("data/frames/composite_HH.webp");
    expect($<HTMLInputElement>("slider").disabled).toBe(true);
    expect($("hint").hidden).toBe(false);
  });

  test("before and after loads the chosen earlier frame into the before map", async () => {
    const { app, host, $ } = setup();
    $("swipe-toggle").click();
    await app.settled();
    expect($("before").hidden).toBe(false);
    expect(host.before.urls.at(-1)).toBe("data/frames/2026-07-02_HH.webp");
  });

  test("a missing overlay shows a visible message and the controls stay usable", async () => {
    const { app, $ } = setup(fixtureManifest, true);
    await app.settled();
    expect($("notice").hidden).toBe(false);
    expect($("notice-text").textContent).toContain("overlay");
    expect($("stamp-after").textContent).toContain("not loaded");
    expect($<HTMLInputElement>("slider").disabled).toBe(false);
    expect($<HTMLButtonElement>("play").disabled).toBe(false);
    expect($<HTMLButtonElement>("composite-toggle").disabled).toBe(false);
  });

  test("the message clears once a frame loads", async () => {
    const root = document.createElement("div");
    document.body.append(root);
    let fail = true;
    const after: MapLike = { setImage: async () => { if (fail) throw new Error("image 404"); } };
    const app = mountApp(root, fixtureManifest, () => ({ after, before: fakeMap() }));
    await app.settled();
    const notice = root.querySelector<HTMLElement>('[data-role="notice"]')!;
    expect(notice.hidden).toBe(false);
    fail = false;
    root.querySelector<HTMLButtonElement>('[data-role="retry"]')!.click();
    await app.settled();
    expect(notice.hidden).toBe(true);
  });

  describe("a date with no HV frame", () => {
    const noHv = {
      ...fixtureManifest,
      dates: fixtureManifest.dates.map((d) =>
        d.date === "2026-07-14" ? { ...d, frames: { HH: d.frames.HH } as typeof d.frames } : d,
      ),
    };
    const pickHv = (root: HTMLElement) => {
      const hv = root.querySelector<HTMLInputElement>('input[value="HV"]')!;
      hv.checked = true;
      hv.dispatchEvent(new Event("change", { bubbles: true }));
    };

    test("shows a notice instead of breaking", async () => {
      const { app, root, $ } = setup(noHv);
      await app.settled();
      pickHv(root);
      const slider = $<HTMLInputElement>("slider");
      slider.value = "1";
      slider.dispatchEvent(new Event("input"));
      await app.settled();
      expect($("notice").hidden).toBe(false);
      expect($("notice-text").textContent).toContain("overlay");
      expect(slider.disabled).toBe(false);
    });

    test("mounting on a first date with no HV frame does not throw", async () => {
      const first = { ...fixtureManifest, dates: fixtureManifest.dates.map((d, i) => (i === 0 ? { ...d, frames: { HH: d.frames.HH } as typeof d.frames } : d)) };
      const { app, root, $ } = setup(first);
      pickHv(root);
      await app.settled();
      expect($("notice").hidden).toBe(false);
    });

    test("play stops and the button goes back to Play", async () => {
      const { app, root, $ } = setup(noHv);
      await app.settled();
      pickHv(root);
      await app.settled();
      $("play").click();
      expect(["Pause", "Play"]).toContain($("play").textContent);
      await vi.waitFor(() => expect($("notice").hidden).toBe(false));
      await app.settled();
      expect($("play").textContent).toBe("Play");
      expect($("play").getAttribute("aria-pressed")).toBe("false");
      await new Promise((r) => setTimeout(r, 1000));
      expect($("slider").getAttribute("aria-valuetext")).toBe("14 Jul 2026");
    });
  });
});

describe("views", () => {
  const demoSites: Site[] = [
    {
      id: "demo-a",
      name: "Demo site A",
      lon: 0.3,
      lat: 0.4,
      role: "demo",
      stack: fixtureManifest.stack,
      crid: fixtureManifest.crid,
      series: [
        { date: "2026-07-02", hh_db: -10, hv_db: -18, valid_fraction: 1 },
        { date: "2026-07-14", hh_db: -11, hv_db: null, valid_fraction: 0 },
      ],
    },
  ];

  test("starts on The Dance with the sites view hidden", async () => {
    const { app, $ } = setup();
    await app.settled();
    expect($("stage").hidden).toBe(false);
    expect($("sites-view").hidden).toBe(true);
    expect($("view-dance").getAttribute("aria-pressed")).toBe("true");
    expect($("view-sites").getAttribute("aria-pressed")).toBe("false");
  });

  test("the switch shows Site Stories and hides the map and its controls", async () => {
    const { app, $ } = setup(fixtureManifest, false, { sites: demoSites });
    await app.settled();
    $("view-sites").click();
    expect($("sites-view").hidden).toBe(false);
    expect($("stage").hidden).toBe(true);
    expect($("dock").hidden).toBe(true);
    expect($("view-sites").getAttribute("aria-pressed")).toBe("true");
    expect($("view-name").textContent).toBe("Site Stories");
    $("view-dance").click();
    expect($("stage").hidden).toBe(false);
    expect($("sites-view").hidden).toBe(true);
    expect($("view-name").textContent).toBe("The Dance");
  });

  test("the maturity label stays visible in the sites view", async () => {
    const { app, $ } = setup({ ...fixtureManifest, maturity: "Synthetic demo" });
    await app.settled();
    $("view-sites").click();
    expect($("sites-maturity").textContent).toBe("SYNTHETIC DEMO: NOT NISAR DATA");
    expect($("sites-maturity").hidden).toBe(false);
  });

  test("without a sites file the view says No site curves yet", async () => {
    const { app, $ } = setup(fixtureManifest, false, { sites: null });
    await app.settled();
    $("view-sites").click();
    expect($("empty").textContent).toBe("No site curves yet");
    expect($("empty").hidden).toBe(false);
  });

  test("tapping a list item opens its card", async () => {
    const { app, root, $ } = setup(fixtureManifest, false, { sites: demoSites });
    await app.settled();
    $("view-sites").click();
    root.querySelector<HTMLButtonElement>('[data-site="demo-a"]')!.click();
    expect($("card").hidden).toBe(false);
    expect($("card-title").textContent).toBe("Demo site A");
  });

  test("site markers on the map open the card and switch view", async () => {
    let tap: ((id: string) => void) | undefined;
    const placed: Site[][] = [];
    const { app, $ } = setup(fixtureManifest, false, { sites: demoSites }, {
      setSiteMarkers: (list, onSelect) => {
        placed.push(list);
        tap = onSelect;
      },
    });
    await app.settled();
    expect(placed).toEqual([demoSites]);
    tap!("demo-a");
    expect($("sites-view").hidden).toBe(false);
    expect($("stage").hidden).toBe(true);
    expect($("card-title").textContent).toBe("Demo site A");
  });

  test("the visible text of both views is free of banned claims", async () => {
    const { app, root, $ } = setup(fixtureManifest, false, { sites: demoSites });
    await app.settled();
    expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
    $("view-sites").click();
    root.querySelector<HTMLButtonElement>('[data-site="demo-a"]')!.click();
    expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
  });

  test("no markers are placed when there are no sites", async () => {
    let called = false;
    const { app } = setup(fixtureManifest, false, { sites: null }, { setSiteMarkers: () => (called = true) as unknown as void });
    await app.settled();
    expect(called).toBe(false);
  });

  test("switching away from The Dance stops playback", async () => {
    const { app, $ } = setup();
    await app.settled();
    $("play").click();
    expect($("play").textContent).toBe("Pause");
    $("view-sites").click();
    expect($("play").textContent).toBe("Play");
  });
});

describe("What NISAR Missed view", () => {
  const withGap = { ...fixtureManifest, gap: { start: "2026-07-27T22:03:25Z", end: "2026-08-10T00:55:27Z" } };

  test("the nav has a third button and the view starts hidden", async () => {
    const { app, $ } = setup(withGap);
    await app.settled();
    expect($("view-missed").textContent).toBe("What NISAR Missed");
    expect($("view-missed").getAttribute("aria-pressed")).toBe("false");
    expect($("missed-view").hidden).toBe(true);
  });

  test("the switch shows the view and hides the map, controls and other views", async () => {
    const { app, $ } = setup(withGap);
    await app.settled();
    $("view-missed").click();
    expect($("missed-view").hidden).toBe(false);
    expect($("stage").hidden).toBe(true);
    expect($("dock").hidden).toBe(true);
    expect($("sites-view").hidden).toBe(true);
    expect($("view-missed").getAttribute("aria-pressed")).toBe("true");
    expect($("view-dance").getAttribute("aria-pressed")).toBe("false");
    expect($("view-name").textContent).toBe("What NISAR Missed");
    expect(document.title).toContain("What NISAR Missed");
    $("view-sites").click();
    expect($("missed-view").hidden).toBe(true);
    expect($("sites-view").hidden).toBe(false);
    $("view-missed").click();
    $("view-dance").click();
    expect($("missed-view").hidden).toBe(true);
    expect($("stage").hidden).toBe(false);
  });

  test("the SYNTHETIC DEMO banner stays visible in this view", async () => {
    const { app, $ } = setup({ ...withGap, maturity: "Synthetic demo" });
    await app.settled();
    $("view-missed").click();
    expect($("missed-maturity").textContent).toBe("SYNTHETIC DEMO: NOT NISAR DATA");
    expect($("missed-maturity").dataset.kind).toBe("synthetic");
    expect($("missed-maturity").hidden).toBe(false);
    expect($("missed-view").hidden).toBe(false);
  });

  test("the view shows the gap text and no banned claims", async () => {
    const { app, root, $ } = setup(withGap);
    await app.settled();
    $("view-missed").click();
    expect($("gap-facts").textContent).toContain("NISAR has no data from 27 Jul 2026, 22:03:25 UTC");
    expect(findBannedClaims(root.textContent ?? "")).toEqual([]);
  });

  test("switching to this view stops playback", async () => {
    const { app, $ } = setup(withGap);
    await app.settled();
    $("play").click();
    $("view-missed").click();
    expect($("play").textContent).toBe("Play");
  });
});

describe("real preview manifest", () => {
  const PREVIEW_TEXT = "REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED";
  const go = (slider: HTMLInputElement, i: number) => {
    slider.value = String(i);
    slider.dispatchEvent(new Event("input"));
  };

  test("the banner is the preview wording on all three views", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    expect($("maturity").textContent).toBe(PREVIEW_TEXT);
    expect($("maturity").dataset.kind).toBe("preview");
    expect($("sites-maturity").textContent).toBe(PREVIEW_TEXT);
    expect($("missed-maturity").textContent).toBe(PREVIEW_TEXT);
    expect($("missed-maturity").dataset.kind).toBe("preview");
    expect(document.title).toContain("real NISAR preview");
  });

  test("a flagged date shows its flag in text next to the date stamp", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    expect($("flag-after").hidden).toBe(false);
    expect($("flag-after").textContent).toBe(INTERFERENCE_FLAG);
    go($("slider"), 1);
    await app.settled();
    expect($("flag-after").textContent).toBe(FORECAST_FLAG);
    expect($("stamp-after").textContent).toBe("14 Jul 2026, HH");
  });

  test("an unflagged date shows no flag", async () => {
    const { app, $ } = setup(previewManifest);
    go($("slider"), 2);
    await app.settled();
    expect($("flag-after").hidden).toBe(true);
    expect($("flag-after").textContent).toBe("");
  });

  test("the before map's date carries its own flag", async () => {
    const { app, $ } = setup(previewManifest);
    go($("slider"), 2);
    $("swipe-toggle").click();
    await app.settled();
    expect($("flag-before").hidden).toBe(false);
    expect($("flag-before").textContent).toBe(INTERFERENCE_FLAG);
    const pick = $<HTMLSelectElement>("before-select");
    pick.value = "2";
    pick.dispatchEvent(new Event("change"));
    await app.settled();
    expect($("flag-before").hidden).toBe(true);
  });

  test("the composite view shows no per-date flag and says which dates it uses", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    $("composite-toggle").click();
    await app.settled();
    expect($("flag-after").hidden).toBe(true);
    expect($("hint").textContent).toContain("26 Jul 2026");
    expect($("hint").textContent).toContain("12 Sep 2026");
    expect($("hint").textContent).toContain("18 Oct 2026");
    expect($("hint").textContent).not.toMatch(/backscatter/i);
  });

  test("the composite hint blames display scaling, not backscatter, for colour differences", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    $("composite-toggle").click();
    await app.settled();
    expect($("hint").textContent).toContain("Colour differences may come from display scaling");
    expect($("hint").textContent).not.toMatch(/display brightness|backscatter/i);
  });

  test("the lede for the preview says the images are scaled for display, not that bright areas sent more signal back", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    expect($("lede").textContent).toContain("scaled for display");
    expect($("lede").textContent).not.toContain("sent more of the signal back");
  });

  test("the lede for calibrated data keeps the plain description", async () => {
    const { app, $ } = setup(fixtureManifest);
    await app.settled();
    expect($("lede").textContent).toContain("Brighter areas sent more of the signal back");
  });

  test("calibrated data names its composite dates when the manifest has them", async () => {
    const { app, $ } = setup({ ...fixtureManifest, composite_dates: ["2026-07-26", "2026-09-12", "2026-10-18"] });
    await app.settled();
    $("composite-toggle").click();
    await app.settled();
    const t = $("hint").textContent ?? "";
    expect(t).toContain("red is 26 Jul 2026, green is 12 Sep 2026, blue is 18 Oct 2026");
    expect(t).toContain("backscatter");
  });

  test("the maturity banner is on the page before the map is created", () => {
    const root = document.createElement("div");
    document.body.append(root);
    let seen = "";
    let seenKind = "";
    mountApp(root, previewManifest, () => {
      seen = root.querySelector('[data-role="maturity"]')!.textContent ?? "";
      seenKind = root.querySelector<HTMLElement>('[data-role="missed-maturity"]')!.dataset.kind ?? "";
      return { after: fakeMap(), before: fakeMap() } satisfies MapHost;
    });
    expect(seen).toBe("REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED");
    expect(seenKind).toBe("preview");
  });

  test("the Dance view states the pixel size and that brightness is not a measurement", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    expect($("limits").hidden).toBe(false);
    const t = $("limits").textContent ?? "";
    expect(t).toContain("174 m");
    expect(t).toContain("scaled for display");
    expect(t).toContain("cannot be compared as a measurement");
  });

  test("calibrated data shows its own limits line: Provisional, 30 m analysis, RTC gamma-0, the display pixel and stretch", async () => {
    const { app, $ } = setup(calibratedManifest);
    await app.settled();
    expect($("limits").hidden).toBe(false);
    const t = $("limits").textContent ?? "";
    expect(t).toContain("Provisional NISAR data");
    expect(t).toContain("RTC gamma-0");
    expect(t).toContain("30 m");
    expect(t).toContain("about 68 m");
    expect(t).toContain("HH -12.9 to 2.2 dB");
    expect(t).toContain("HV -21.0 to -6.0 dB");
    expect(t).toContain("not proof of what changed on the ground");
    expect(findBannedClaims(t)).toEqual([]);
    expect(t).not.toMatch(/scaled for display|preview/i);
  });

  test("the composite shows the flag of any flagged date it uses, with that date", async () => {
    const { app, $ } = setup({ ...previewManifest, composite_dates: ["2026-07-14", "2026-09-12", "2026-10-18"] });
    await app.settled();
    $("composite-toggle").click();
    await app.settled();
    expect($("flag-after").hidden).toBe(false);
    expect($("flag-after").textContent).toBe(`14 Jul 2026: ${FORECAST_FLAG}`);
  });

  test("the composite shows no flag when none of its dates is flagged", async () => {
    const { app, $ } = setup(previewManifest);
    await app.settled();
    $("composite-toggle").click();
    await app.settled();
    expect($("flag-after").hidden).toBe(true);
  });

  test("the limits line and the flags do not appear for synthetic data", async () => {
    const { app, $ } = setup({ ...fixtureManifest, maturity: "Demo" });
    await app.settled();
    expect($("limits").hidden).toBe(true);
    expect($("flag-after").hidden).toBe(true);
  });

  /** Text a person can see: skips anything inside an element with the hidden attribute. */
  function visibleText(el: Element): string {
    if ((el as HTMLElement).hidden) return "";
    return [...el.childNodes].map((n) => (n.nodeType === 3 ? n.textContent ?? "" : n.nodeType === 1 ? visibleText(n as Element) : "")).join(" ");
  }

  test("the visible text of every preview view has no banned claims and never says dB", async () => {
    const { app, root, $ } = setup(previewManifest, false, { sites: null });
    await app.settled();
    for (const view of ["view-dance", "view-sites", "view-missed"]) {
      $(view).click();
      const text = visibleText(root);
      expect(text.length).toBeGreaterThan(100);
      expect(findBannedClaims(text)).toEqual([]);
      expect(text).not.toMatch(/\bdB\b|decibel/i);
    }
  });

  test("Site Stories with no sites explains why in one sentence and shows no card", async () => {
    const { app, root, $ } = setup(previewManifest, false, { sites: null });
    await app.settled();
    $("view-sites").click();
    expect($("empty").textContent).toBe("No site curves yet");
    expect($("empty-why").textContent).toBe("Curves appear once the calibrated build has run.");
    expect($("empty-why").hidden).toBe(false);
    expect($("body").hidden).toBe(true);
    expect($("card").hidden).toBe(true);
    expect(root.querySelectorAll("[data-site]").length).toBe(0);
    expect(root.textContent).not.toMatch(/Placeholder|Demo site/);
  });

  test("What NISAR Missed lists the manifest dates and carries the flags in text", async () => {
    const { app, root, $ } = setup(previewManifest);
    await app.settled();
    $("view-missed").click();
    const items = [...root.querySelectorAll('[data-role="passes"] li')].map((li) => li.textContent ?? "");
    expect(items).toHaveLength(3);
    expect(items[0]).toContain("2 Jul 2026");
    expect(items[0]).toContain(INTERFERENCE_FLAG);
    expect(items[1]).toContain(FORECAST_FLAG);
    expect(items[2]).toBe("26 Jul 2026");
  });
});
