import { describe, expect, test } from "vitest";
import { createPreloader } from "./preload";

function controlled() {
  const started: string[] = [];
  const open = new Map<string, { resolve(): void; reject(e: Error): void }>();
  const load = (url: string) =>
    new Promise<void>((resolve, reject) => {
      started.push(url);
      open.set(url, { resolve, reject });
    });
  return { started, open, load };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

describe("preloader", () => {
  test("loads at most two at a time, in the order asked", async () => {
    const c = controlled();
    const p = createPreloader(c.load, 2);
    p.request(["a", "b", "c", "d"]);
    expect(c.started).toEqual(["a", "b"]);
    c.open.get("a")!.resolve();
    await tick();
    expect(c.started).toEqual(["a", "b", "c"]);
    expect(p.progress()).toEqual({ done: 1, total: 4, failed: 0 });
  });

  test("a URL asked for twice is fetched once", () => {
    const c = controlled();
    const p = createPreloader(c.load);
    p.request(["a"]);
    p.request(["a"]);
    expect(c.started).toEqual(["a"]);
    expect(p.progress().total).toBe(1);
  });

  test("prioritize moves a waiting URL to the front", async () => {
    const c = controlled();
    const p = createPreloader(c.load, 1);
    p.request(["a", "b", "c"]);
    p.prioritize("c");
    c.open.get("a")!.resolve();
    await tick();
    expect(c.started).toEqual(["a", "c"]);
  });

  test("whenReady resolves when loaded and rejects when the load fails", async () => {
    const c = controlled();
    const p = createPreloader(c.load);
    const ok = p.whenReady("a");
    const bad = p.whenReady("b");
    c.open.get("a")!.resolve();
    c.open.get("b")!.reject(new Error("404"));
    await expect(ok).resolves.toBeUndefined();
    await expect(bad).rejects.toThrow("404");
    await tick();
    expect(p.progress()).toEqual({ done: 1, total: 2, failed: 1 });
  });

  test("listeners hear every change and can stop listening", async () => {
    const c = controlled();
    const p = createPreloader(c.load);
    let heard = 0;
    const stop = p.onChange(() => (heard += 1));
    p.request(["a"]);
    const afterRequest = heard;
    expect(afterRequest).toBeGreaterThan(0);
    c.open.get("a")!.resolve();
    await tick();
    expect(heard).toBeGreaterThan(afterRequest);
    stop();
    const frozen = heard;
    p.request(["b"]);
    expect(heard).toBe(frozen);
  });
});
