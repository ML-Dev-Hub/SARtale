import { describe, expect, it } from "vitest";
import overviewCss from "./overview/overview.css?raw";
import styles from "./styles.css?raw";
import { rulesFor } from "./testCss";

const has = (rules: string[], re: RegExp): boolean => rules.some((d) => re.test(d));

describe("the phone header (max-width 760px)", () => {
  it("is one 56 px row: the nav shares the row with the logo and nothing wraps", () => {
    expect(has(rulesFor(styles, ":root"), /--header-h:\s*56px/)).toBe(true);
    expect(has(rulesFor(styles, ".top"), /flex-wrap:\s*nowrap/)).toBe(true);
    for (const d of rulesFor(styles, ".views")) expect(d).not.toMatch(/flex:\s*1 1 100%/);
  });
  it("hides the wordmark and the provisional pill in the phone bar, and keeps 44 px targets and the primary pill", () => {
    expect(has(rulesFor(styles, ".top .brand"), /display:\s*none/)).toBe(true);
    expect(has(rulesFor(styles, ".top .maturity"), /display:\s*none/)).toBe(true);
    expect(has(rulesFor(styles, ".view-btn"), /min-height:\s*44px/)).toBe(true);
    expect(has(rulesFor(styles, ".view-btn.view-primary"), /background:\s*var\(--accent\)/)).toBe(true);
  });
});

describe("accessibility quick wins", () => {
  it("uses one cyan focus ring, 2px with a 2px offset", () => {
    const d = rulesFor(styles, ":focus-visible").join(";");
    expect(d).toMatch(/outline:\s*2px solid var\(--accent\)/);
    expect(d).toMatch(/outline-offset:\s*2px/);
    expect(d).not.toContain("--warm");
    expect(has(rulesFor(overviewCss, ".ovp :is(button, a, select, input):focus-visible"), /outline:\s*2px solid var\(--accent\)/)).toBe(true);
  });
  it("the evidence contents links, sort buttons, selects and search are 44 px", () => {
    expect(has(rulesFor(styles, ".evidence-toc a"), /min-height:\s*44px/)).toBe(true);
    expect(has(rulesFor(overviewCss, ".ov-sort"), /min-height:\s*44px/)).toBe(true);
    expect(has(rulesFor(overviewCss, ".ov-select"), /min-height:\s*44px/)).toBe(true);
    expect(has(rulesFor(overviewCss, ".ov-search"), /min-height:\s*44px/)).toBe(true);
  });
});

describe("the desktop map", () => {
  it("takes the picture's drawn shape (the --ov-map-aspect set from its bounds, about 1.47) up to 1040 px wide, with 44 px controls", () => {
    const d = rulesFor(overviewCss, '.ov[data-map="true"] .ov-map').join(";");
    expect(d).toMatch(/max-width:\s*1040px/);
    expect(d).toMatch(/aspect-ratio:\s*var\(--ov-map-aspect/);
    expect(d).toMatch(/width:\s*100%/);
    expect(overviewCss).not.toMatch(/1740 \/ 960/);
    for (const sel of [".ov-map", ".ovp-sheet .ov-map"]) {
      const all = rulesFor(overviewCss, sel).join(";");
      expect(all).not.toMatch(/min-height:\s*[1-9]/);
      expect(all).not.toMatch(/aspect-ratio:\s*[\d.]+ \/ [\d.]+/);
    }
    expect(has(rulesFor(overviewCss, ".ov-locate"), /min-height:\s*44px/)).toBe(true);
    expect(has(rulesFor(styles, ".maplibregl-map .maplibregl-ctrl-group button"), /width:\s*44px;\s*height:\s*44px/)).toBe(true);
  });
});
