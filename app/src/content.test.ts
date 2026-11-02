import readme from "../../README.md?raw";
import demoScript from "../../docs/demo-script.md?raw";
import { describe, expect, test } from "vitest";
import { evidenceCopy } from "./evidenceView";
import { BADGE_LABELS, cardFor, EVIDENCE_LABELS, findBannedClaims, heroCopy, lakeHero, lakeStoryBeats, PLACEHOLDER, siteCards, story, storyBeats } from "./content";

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
    expect(findBannedClaims("This is a detected change")).toEqual(["detected change"]);
    expect(findBannedClaims("Change detected here")).toEqual(["change detected"]);
    expect(findBannedClaims("A change detection layer")).toEqual(["change detection"]);
  });

  test("clean text and the allowed hypothesis wording pass", () => {
    expect(findBannedClaims("A drop in HV may indicate standing water.")).toEqual([]);
    expect(findBannedClaims("")).toEqual([]);
  });
});

describe("app copy", () => {
  test("all app copy is free of banned claims", () => {
    expect(findBannedClaims(JSON.stringify([story, storyBeats, heroCopy, siteCards]))).toEqual([]);
    expect(JSON.stringify([story, storyBeats, heroCopy, siteCards])).not.toMatch(/detect/i);
  });

  test("the lake story, start screen and evidence copy are free of banned claims", () => {
    expect(findBannedClaims(JSON.stringify([lakeStoryBeats, lakeHero, evidenceCopy]))).toEqual([]);
    const quote = lakeStoryBeats.find((b) => b.quote)!.quote!.text;
    expect(JSON.stringify([lakeStoryBeats, lakeHero, evidenceCopy]).replace(quote, "")).not.toMatch(/detect|accurate/i);
  });

  test("the evidence labels are the four allowed ones", () => {
    expect(Object.values(EVIDENCE_LABELS)).toEqual(["Observed", "Reference agrees", "Hypothesis", "Not observed"]);
  });

  test("no placeholder demo cards or stories ship: only real cards and the missed-view copy", () => {
    expect(Object.keys(story)).toEqual(["what-nisar-missed"]);
    expect(JSON.stringify([storyBeats, heroCopy])).not.toMatch(/demo|placeholder/i);
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

  test("story copy is written, not placeholder", () => {
    for (const s of Object.values(story)) expect(s.summary).not.toMatch(/placeholder/i);
  });

  test("real cards carry an evidence class, and only a site without a card gets the Placeholder badge", () => {
    for (const c of Object.values(siteCards)) {
      expect(c.observation).not.toMatch(/placeholder/i);
      expect(Object.keys(EVIDENCE_LABELS)).toContain(c.evidence);
    }
    expect(cardFor("no-such-site").evidence).toBe("placeholder");
    expect(BADGE_LABELS.placeholder).toBe("Placeholder");
    expect(Object.values(EVIDENCE_LABELS)).not.toContain("Placeholder");
  });

  test("copy keeps the honesty rules: a hypothesis is never a finding, change is never flood probability", () => {
    const text = JSON.stringify(siteCards);
    expect(text).not.toMatch(/flood probability|floodwater|inundat|proves|confirms/i);
    for (const c of Object.values(siteCards)) expect(c.hypothesis).toContain("may indicate");
  });

  test("cardFor falls back to a placeholder card for an unknown site", () => {
    const c = cardFor("no-such-site");
    expect(c.observation.startsWith(PLACEHOLDER)).toBe(true);
    expect(findBannedClaims(JSON.stringify(c))).toEqual([]);
  });
});

describe("the guided story", () => {
  test("walks the six beats in order, each with at least one step", () => {
    const beats = storyBeats.map((s) => s.beat);
    expect([...new Set(beats)]).toEqual([1, 2, 3, 4, 5, 6]);
    expect([...beats].sort()).toEqual(beats);
    expect(storyBeats.map((s) => s.label).filter((l, i, all) => all.indexOf(l) === i)).toEqual([
      "Why the valley matters",
      "Meet NISAR",
      "The season plays",
      "Why it moved",
      "What NISAR missed",
      "Why it matters",
    ]);
  });

  test("beat 4 covers Tarbela, Attock and HH against HV, and beat 5 the 2 July interference, the 23 July peak and the gap", () => {
    expect(storyBeats.filter((s) => s.beat === 4).map((s) => s.stop)).toEqual(["Tarbela", "Attock", "HH against HV"]);
    expect(storyBeats.filter((s) => s.beat === 5).map((s) => s.stop)).toEqual(["2 July", "23 July", "The gap"]);
  });

  test("every step has an id, a title, written text and a place for the map to go", () => {
    expect(new Set(storyBeats.map((s) => s.id)).size).toBe(storyBeats.length);
    for (const s of storyBeats) {
      expect(s.title.length, s.id).toBeGreaterThan(0);
      expect(s.body.length, s.id).toBeGreaterThan(0);
      expect(s.body.join(" "), s.id).not.toMatch(/placeholder/i);
      expect(s.map.date, s.id).toMatch(/^2026-\d\d-\d\d$/);
      if ("center" in s.camera) {
        expect(s.camera.zoom, s.id).toBeGreaterThan(5);
        expect(s.camera.center, s.id).toHaveLength(2);
      } else {
        expect(s.camera.fit, s.id).toBe(true);
      }
    }
  });

  test("a hypothesis in the story says may indicate, and no step claims a cause as fact", () => {
    for (const s of storyBeats) {
      const text = s.body.join(" ");
      if (/(rising water|sand or gravel)/.test(text)) expect(text, s.id).toContain("may indicate");
      expect(text, s.id).not.toMatch(/proves|confirms|caused by|flood probability/i);
    }
  });

  test("the story and hero never name a land cover nobody has checked", () => {
    expect(JSON.stringify([storyBeats, heroCopy])).not.toMatch(/farm|cropland|wheat|rice|orchard|village|paddy/i);
  });

  test("the hero's finding is a hypothesis and names the provisional status", () => {
    expect(heroCopy.finding).toContain("may indicate");
    expect(heroCopy.findingSource).toContain("Provisional");
  });
});

describe("project documents", () => {
  test.each([["README.md", readme], ["docs/demo-script.md", demoScript]])("%s is free of banned claims", (_name, text) => {
    expect(text.length).toBeGreaterThan(500);
    expect(findBannedClaims(text)).toEqual([]);
  });
});
