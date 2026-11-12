// @vitest-environment jsdom
import { afterEach, describe, expect, test } from "vitest";
import { fixtureLakes } from "./fixtures";
import { mountOrShowError, showStartupError } from "./startup";

afterEach(() => {
  document.body.innerHTML = "";
});

function root(): HTMLElement {
  const el = document.createElement("div");
  document.body.append(el);
  return el;
}

describe("startup", () => {
  test("mounts the app and shows no error", () => {
    const el = root();
    expect(mountOrShowError(el, { lakes: fixtureLakes })).not.toBeNull();
    expect(el.querySelector(".startup-error")).toBeNull();
    expect(el.querySelector(".shell")).not.toBeNull();
  });

  test("an error message keeps the data label above it", () => {
    const el = root();
    showStartupError(el, "Something went wrong");
    expect(el.querySelector(".maturity")!.textContent).toBe("Provisional NISAR data");
    expect(el.querySelector('[role="alert"]')!.textContent).toBe("Something went wrong");
  });
});
