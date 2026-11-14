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
    expect(authorityFor("GB")!.id).toBe("NDMA");
    expect(authorityFor("KP")!.id).toBe("PDMA-KP");
    expect(authorityFor(null)).toBeNull();
  });
  it("each URL is https on the authority's own domain and has a check date", () => {
    for (const a of Object.values(AUTHORITIES)) {
      const u = new URL(a.url!);
      expect(u.protocol).toBe("https:");
      expect(u.hostname).toBe(a.domain);
      expect(a.checked).toMatch(/^2026-\d\d-\d\d$/);
    }
    expect(AUTHORITIES.GB.domain).toBe("ndma.gov.pk");
    expect(AUTHORITIES.KP.domain).toBe("pdma.gov.pk");
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
  it("a GB lake shows Contact NDMA with its URL and the note; a KP lake has no note", () => {
    const mk = (province: "GB" | "KP") => {
      const el = document.createElement("div");
      const l = makeLake({ province, status: { ...makeLake().status, status: "Watch", level: "Watch", message: fixtureMessage("Watch", "Lake A") } });
      createLakePage(el, { file: makeFile([l]), lakeId: l.id, onRoute: vi.fn() });
      return el;
    };
    const gb = mk("GB");
    const a = gb.querySelector<HTMLAnchorElement>('a[data-action="authority"]')!;
    expect(a.textContent).toBe("Contact NDMA");
    expect(a.href).toBe(AUTHORITIES.GB.url);
    expect(gb.querySelector(".lp-authority-note")!.textContent).toBe(AUTHORITIES.GB.note);
    expect(mk("KP").querySelector(".lp-authority-note")).toBeNull();
  });
});
