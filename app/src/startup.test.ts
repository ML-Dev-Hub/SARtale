// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import type { MapHost } from "./app";
import { previewManifest } from "./fixtures";
import { mountOrShowError, showStartupError } from "./startup";

afterEach(() => {
  document.body.innerHTML = "";
});

const PREVIEW_TEXT = "REAL NISAR PREVIEW: LOW-RESOLUTION BROWSE IMAGES, NOT CALIBRATED";

function root(): HTMLElement {
  const el = document.createElement("div");
  document.body.append(el);
  return el;
}

describe("startup failures", () => {
  test("a map that cannot start (no WebGL) shows a message and the maturity banner", () => {
    const el = root();
    const handle = mountOrShowError(
      el,
      previewManifest,
      () => {
        throw new Error("Failed to initialize WebGL");
      },
      {},
    );
    expect(handle).toBeNull();
    const alert = el.querySelector('[role="alert"]')!;
    expect(alert.textContent).toContain("Failed to initialize WebGL");
    expect(alert.textContent).toContain("WebGL");
    expect(el.querySelector(".maturity")!.textContent).toBe(PREVIEW_TEXT);
    expect(el.querySelector<HTMLElement>(".maturity")!.dataset.kind).toBe("preview");
  });

  test("a synthetic manifest keeps the synthetic banner on the error page", () => {
    const el = root();
    mountOrShowError(el, { ...previewManifest, maturity: "Synthetic demo" }, () => {
      throw new Error("boom");
    }, {});
    expect(el.querySelector(".maturity")!.textContent).toBe("SYNTHETIC DEMO: NOT NISAR DATA");
  });

  test("a map that starts mounts the app and shows no error", () => {
    const el = root();
    const noop = { setImage: async () => {} };
    const handle = mountOrShowError(el, previewManifest, () => ({ after: noop, before: noop }) satisfies MapHost, {});
    expect(handle).not.toBeNull();
    expect(el.querySelector(".startup-error")).toBeNull();
    expect(el.querySelector('[data-role="maturity"]')!.textContent).toBe(PREVIEW_TEXT);
  });

  test("an error before any manifest is known shows only the message", () => {
    const el = root();
    showStartupError(el, "Could not load the data manifest (404)");
    expect(el.querySelector(".maturity")).toBeNull();
    expect(el.querySelector('[role="alert"]')!.textContent).toBe("Could not load the data manifest (404)");
  });
});
