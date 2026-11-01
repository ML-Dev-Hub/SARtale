// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
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
});
