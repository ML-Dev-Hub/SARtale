import { describe, expect, test } from "vitest";
import { BADGE_LABELS, cardFor, EVIDENCE_LABELS, findBannedClaims, PLACEHOLDER, siteCards, story } from "./content";

describe("findBannedClaims", () => {
  test("catches banned wording in any case", () => {
    expect(findBannedClaims("Flood Detected near the bridge")).toEqual(["flood detected"]);
  });

  test("returns every banned phrase once, in a stable order", () => {
    expect(findBannedClaims("EARLY WARNING: a risk score of 3, early warning")).toEqual(["risk score", "early warning"]);
  });

  test("damage and damaged are separate words", () => {
    expect(findBannedClaims("Damage here")).toEqual(["damage"]);
    expect(findBannedClaims("it was damaged")).toEqual(["damaged"]);
    expect(findBannedClaims("damage and damaged")).toEqual(["damage", "damaged"]);
  });

  test("catches the other banned phrases", () => {
    expect(findBannedClaims("an isolated village")).toEqual(["isolated"]);
    expect(findBannedClaims("flood detected")).toEqual(["flood detected"]);
  });

  test("clean text and the allowed hypothesis wording pass", () => {
    expect(findBannedClaims("A drop in HV may indicate standing water.")).toEqual([]);
    expect(findBannedClaims("")).toEqual([]);
  });
});

describe("app copy", () => {
  test("all app copy is free of banned claims", () => {
    expect(findBannedClaims(JSON.stringify([story, siteCards]))).toEqual([]);
  });

  test("the evidence labels are the four allowed ones", () => {
    expect(Object.values(EVIDENCE_LABELS)).toEqual(["Observed", "Reference agrees", "Hypothesis", "Not observed"]);
  });

  test("no placeholder demo cards or stories ship: only real cards and the missed-view copy", () => {
    expect(Object.keys(story)).toEqual(["what-nisar-missed"]);
    expect(Object.keys(siteCards).filter((id) => /^demo-/.test(id))).toEqual([]);
    expect(JSON.stringify([story, siteCards])).not.toMatch(/demo/i);
  });

  test("every shipped card has all slots, and hypotheses say may indicate unless still placeholder text", () => {
    for (const c of [...Object.values(siteCards), cardFor("no-such-site")]) {
      for (const k of ["observation", "hypothesis", "test", "limits"] as const) expect(c[k].length).toBeGreaterThan(0);
      expect(Object.keys(BADGE_LABELS)).toContain(c.evidence);
      expect(Array.isArray(c.dates)).toBe(true);
      expect(c.hypothesis.startsWith(PLACEHOLDER) || c.hypothesis.includes("may indicate")).toBe(true);
    }
  });

  test("placeholder copy is labelled as placeholder", () => {
    for (const [id, s] of Object.entries(story)) {
      if (id === "what-nisar-missed") expect(s.summary).not.toMatch(/placeholder/i); // written from the data, not a placeholder
      else expect(s.summary.startsWith(PLACEHOLDER)).toBe(true);
    }
    for (const c of Object.values(siteCards)) expect(c.observation.startsWith(PLACEHOLDER)).toBe(true);
  });

  test("placeholder cards carry the neutral Placeholder badge, not an evidence class", () => {
    for (const c of Object.values(siteCards)) {
      expect(c.observation.startsWith(PLACEHOLDER)).toBe(true);
      expect(c.evidence).toBe("placeholder");
    }
    expect(cardFor("no-such-site").evidence).toBe("placeholder");
    expect(BADGE_LABELS.placeholder).toBe("Placeholder");
    expect(Object.values(EVIDENCE_LABELS)).not.toContain("Placeholder");
  });

  test("cardFor falls back to a placeholder card for an unknown site", () => {
    const c = cardFor("no-such-site");
    expect(c.observation.startsWith(PLACEHOLDER)).toBe(true);
    expect(findBannedClaims(JSON.stringify(c))).toEqual([]);
  });
});
