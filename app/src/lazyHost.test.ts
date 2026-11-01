import { describe, expect, test } from "vitest";
import type { HostFactory, MapHost } from "./app";
import { fixtureManifest } from "./fixtures";
import { lazyHostFactory } from "./lazyHost";
import type { Corners } from "./types";

const corners: Corners = [[0, 1], [1, 1], [1, 0], [0, 0]];
const el = {} as HTMLElement;

function fakeLibrary() {
  const calls: string[] = [];
  const host: MapHost = {
    after: { setImage: async (u) => void calls.push(`after:${u}`), setOverlay: async (u) => void calls.push(`overlay:${u}`) },
    before: { setImage: async (u) => void calls.push(`before:${u}`) },
    setSiteMarkers: () => void calls.push("markers"),
    moveTo: (c) => void calls.push(`move:${JSON.stringify(c)}`),
  };
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const factory: HostFactory = () => host;
  return { calls, release, load: async () => (await gate, { hostFactoryFor: () => factory }) };
}

describe("lazy map host", () => {
  test("calls made before the library arrives wait for it and then run in order", async () => {
    const lib = fakeLibrary();
    const host = lazyHostFactory(fixtureManifest, lib.load)(el, el);
    const first = host.after.setImage("a.webp", corners);
    host.moveTo!({ fit: true }, { top: 0, right: 0, bottom: 0, left: 0 });
    const second = host.before.setImage("b.webp", corners);
    expect(lib.calls).toEqual([]);
    lib.release();
    await Promise.all([first, second]);
    await new Promise((r) => setTimeout(r, 0));
    expect(lib.calls).toEqual(["after:a.webp", 'move:{"fit":true}', "before:b.webp"]);
  });

  test("the overlay and site markers are forwarded too", async () => {
    const lib = fakeLibrary();
    lib.release();
    const host = lazyHostFactory(fixtureManifest, lib.load)(el, el);
    await host.after.setOverlay!("o.webp", corners);
    host.setSiteMarkers!([], () => {});
    await new Promise((r) => setTimeout(r, 0));
    expect(lib.calls).toEqual(["overlay:o.webp", "markers"]);
  });

  test("if the library cannot start, the calls that need it fail with its message and the rest stay quiet", async () => {
    const host = lazyHostFactory(fixtureManifest, async () => {
      throw new Error("WebGL is not available");
    })(el, el);
    await expect(host.after.setImage("a.webp", corners)).rejects.toThrow("WebGL is not available");
    expect(() => host.moveTo!({ fit: true }, { top: 0, right: 0, bottom: 0, left: 0 })).not.toThrow();
    expect(() => host.setSiteMarkers!([], () => {})).not.toThrow();
  });
});
