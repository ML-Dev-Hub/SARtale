// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import shipped from "../public/data/lakes.json";
import { AUTHORITIES, authorityFor } from "./contacts";
import { fixtureMessage, makeFile, makeLake } from "./fixtures";
import { keepValidLakes, type LakesFile } from "./lakes";
import { createLakePage } from "./lakePage/lakePage";

describe("contacts", () => {
  it("every lake with a province maps to exactly one authority", () => {
    const lakes = keepValidLakes(shipped as unknown as LakesFile).lakes;
    for (const l of lakes) {
      const hits = [AUTHORITIES.GB, AUTHORITIES.KP].filter((a) => a === authorityFor(l.province));
      expect(hits).toHaveLength(l.province === "GB" || l.province === "KP" ? 1 : 0);
    }
    expect(lakes.filter((l) => !l.province)).toEqual([]);
  });
  it("GB lakes get GBDMA and KP lakes PDMA", () => {
    expect(authorityFor("GB")!.id).toBe("GBDMA");
    expect(authorityFor("KP")!.id).toBe("PDMA-KP");
    expect(authorityFor(null)).toBeNull();
  });
  it("each verified URL is https on the authority's own domain and has a check date", () => {
    for (const a of Object.values(AUTHORITIES)) expect(a.checked).toMatch(/^2026-\d\d-\d\d$/);
    expect(new URL(AUTHORITIES.KP.url!).protocol).toBe("https:");
    expect(new URL(AUTHORITIES.KP.url!).hostname).toBe("pdma.gov.pk");
    // GBDMA stays null until a URL is verified on its own domain; a non-null value must be a gov.pk https URL.
    if (AUTHORITIES.GB.url) { const u = new URL(AUTHORITIES.GB.url); expect(u.protocol).toBe("https:"); expect(u.hostname).toMatch(/gbdma\.(gog|gov)\.pk$/); }
  });
  it("SARtale shows no phone number or email of its own", () => expect(JSON.stringify(AUTHORITIES)).not.toMatch(/@|\+92|\btel:/));
  it("the lake page shows the lake's own authority", () => {
    const el = document.createElement("div");
    const l = makeLake({ province: "KP", status: { ...makeLake().status, status: "Watch", level: "Watch", message: fixtureMessage("Watch", "Lake A") } });
    createLakePage(el, { file: makeFile([l]), lakeId: l.id, onRoute: vi.fn() });
    const a = el.querySelector<HTMLAnchorElement>('a[data-action="authority"]')!;
    expect(a.textContent).toBe("Contact PDMA");
    expect(a.href).toBe(AUTHORITIES.KP.url);
  });
  it("a GB lake shows no authority button while the GBDMA URL is unverified", () => {
    const el = document.createElement("div");
    const l = makeLake({ province: "GB", status: { ...makeLake().status, status: "Watch", level: "Watch", message: fixtureMessage("Watch", "Lake A") } });
    createLakePage(el, { file: makeFile([l]), lakeId: l.id, onRoute: vi.fn() });
    expect(el.querySelector('a[data-action="authority"]') !== null).toBe(AUTHORITIES.GB.url !== null);
  });
});
