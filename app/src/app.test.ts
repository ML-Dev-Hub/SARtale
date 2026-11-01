// @vitest-environment jsdom
import { afterEach, describe, expect, test, vi } from "vitest";
import { mountApp, type MapHost } from "./app";
import { fixtureManifest } from "./fixtures";
import type { MapLike } from "./map";

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

function setup(manifest = fixtureManifest, failing = false) {
  const root = document.createElement("div");
  document.body.append(root);
  const host = { after: fakeMap(failing), before: fakeMap() } satisfies MapHost;
  const app = mountApp(root, manifest, () => host);
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
