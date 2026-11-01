// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { mountApp } from "./app";
import { fixtureManifest } from "./fixtures";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("header logo", () => {
  function logo(): HTMLImageElement {
    const root = document.createElement("div");
    document.body.append(root);
    mountApp(root, fixtureManifest, () => ({ after: { setImage: async () => {} }, before: { setImage: async () => {} } }));
    return root.querySelector<HTMLImageElement>("header img.logo")!;
  }

  test("renders with its alt text", () => {
    expect(logo().alt).toBe("SARtale Pakistan logo");
  });

  test("loads from a relative path so the ./ base build works offline", () => {
    const src = logo().getAttribute("src")!;
    expect(src).toBe("brand/logo-256.png");
    expect(src).not.toMatch(/^([a-z]+:)?\/\//i);
    expect(src.startsWith("/")).toBe(false);
  });

  test("the files it points at ship in public/brand", () => {
    const shipped = Object.keys(import.meta.glob("../public/brand/*.png")).map((p) => p.replace("../public/", ""));
    expect(shipped).toContain(logo().getAttribute("src"));
    expect(shipped).toContain("brand/favicon-64.png");
  });

  test("has fixed width and height so the header does not jump while it loads", () => {
    const img = logo();
    expect(img.getAttribute("width")).toBeTruthy();
    expect(img.getAttribute("height")).toBeTruthy();
  });
});
