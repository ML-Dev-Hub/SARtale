import readme from "../../README.md?raw";
import { describe, expect, test } from "vitest";
import { evidenceCopy } from "./evidenceView";
import { findBannedClaims, lakeHero, lakeStoryBeats } from "./content";

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
  });

  test("allows Watch and Alert as level names only", () => {
    expect(findBannedClaims("Watch: one radar pass is beyond 2× noise. Alert: growing on two passes in a row.")).toEqual([]);
    expect(findBannedClaims("A GLOF alert for Hunza")).toEqual(["glof alert"]);
    expect(findBannedClaims("Flood watch issued")).toEqual(["flood watch"]);
    expect(findBannedClaims("Red alert: alert issued")).toEqual(["red alert", "alert issued"]);
    expect(findBannedClaims("an outburst alert")).toEqual(["outburst alert"]);
    // hazard, risk, prediction and "safe" wording stays banned
    expect(findBannedClaims("predict a safe lake with no risk")).toEqual(["predict", "safe", "no risk"]);
    expect(findBannedClaims("")).toEqual([]);
  });
});

describe("app copy", () => {
  test("the lake story, start screen and evidence copy are free of banned claims", () => {
    expect(findBannedClaims(JSON.stringify([lakeStoryBeats, lakeHero, evidenceCopy]))).toEqual([]);
    const quote = lakeStoryBeats.find((b) => b.quote)!.quote!.text;
    expect(JSON.stringify([lakeStoryBeats, lakeHero, evidenceCopy]).replace(quote, "")).not.toMatch(/detect|accurate/i);
  });

  test("the copy is about the lakes only: no Peshawar chapter is left", () => {
    expect(JSON.stringify([lakeStoryBeats, lakeHero, evidenceCopy])).not.toMatch(/Peshawar|Tarbela|Attock|OPERA/);
  });

  test("the story beats are numbered 1 to n in order", () => {
    expect(lakeStoryBeats.map((b) => b.beat)).toEqual(lakeStoryBeats.map((_, i) => i + 1));
  });
});

describe("project documents", () => {
  test("README.md is free of banned claims", () => {
    expect(readme.length).toBeGreaterThan(500);
    expect(findBannedClaims(readme)).toEqual([]);
  });
});
