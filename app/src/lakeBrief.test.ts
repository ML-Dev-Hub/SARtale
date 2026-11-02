// @vitest-environment jsdom
import { afterEach, describe, expect, test, vi } from "vitest";
import { findBannedClaims } from "./content";
import { fixtureLakes } from "./fixtures";
import { briefHtml, printBrief } from "./lakeBrief";
import type { Lake, LakeSeriesPoint } from "./lakes";

const NOW = new Date("2026-11-02T10:00:00Z");
const pass = (date: string, area: number | null, share: number | null, excluded: string | null = null, track = "156A"): LakeSeriesPoint => ({ date, track, area_km2: area, observable_share: share, excluded });
const lakeOf = (extra: Partial<Lake> = {}): Lake => ({ ...fixtureLakes.lakes.find((l) => l.id === "stable")!, ...extra });
const text = (html: string) => {
  const d = document.createElement("div");
  d.innerHTML = html;
  return d.textContent ?? "";
};

afterEach(() => {
  document.body.innerHTML = "";
});

describe("lake brief", () => {
  test("test_brief_has_footer_and_built_date", () => {
    const html = briefHtml(lakeOf(), fixtureLakes, NOW);
    expect(text(html)).toContain("Indicative screening from provisional NISAR data. Not an official warning; official warnings come from PMD and NDMA. Built 2026-11-02T00:00:00Z.");
    expect(html).toContain("Fixture stable");
    expect(html).toContain("Coordinates");
  });

  test("lists the latest 6 valid passes, newest first, skipping invalid ones", () => {
    const series = [
      pass("2026-10-01", 0.1, 0.9),
      pass("2026-10-02", 0.2, 0.9),
      pass("2026-10-03", 0.3, 0.9),
      pass("2026-10-04", 0.4, 0.9),
      pass("2026-10-05", 0.5, 0.9),
      pass("2026-10-06", 0.6, 0.9),
      pass("2026-10-07", 0.7, 0.9),
      pass("2026-10-08", 9.999, 0.9, "bright outlier"),
      pass("2026-10-09", 8.888, 0.2),
      pass("2026-10-10", null, 0.9),
    ];
    const html = briefHtml(lakeOf({ series }), fixtureLakes, NOW);
    const rows = [...new DOMParser().parseFromString(html, "text/html").querySelectorAll(".lake-brief-passes tbody tr")].map((r) => r.textContent);
    expect(rows).toHaveLength(6);
    expect(rows[0]).toContain("7 Oct 2026");
    expect(rows[0]).toContain("0.700");
    expect(rows[0]).toContain("90%");
    expect(rows[5]).toContain("2 Oct 2026");
    expect(html).not.toContain("9.999");
    expect(html).not.toContain("8.888");
  });

  test("with no valid passes on the status track it prints the status reason", () => {
    const hidden = fixtureLakes.lakes.find((l) => l.id === "hidden")!;
    const t = text(briefHtml({ ...hidden, series: [] }, fixtureLakes, NOW));
    expect(t).toContain("Fixture reason for hidden.");
    expect(t).not.toContain("No valid NISAR passes yet.");
  });

  test("lists only the status track's passes, under a heading that names the track", () => {
    const series = [pass("2026-10-01", 0.1, 0.9), pass("2026-10-02", 0.555, 0.9, null, "055A"), pass("2026-10-03", 0.3, 0.9)];
    const t = text(briefHtml(lakeOf({ series }), fixtureLakes, NOW));
    expect(t).toContain("Latest valid passes on track 156A (the status compares only these)");
    expect(t).not.toContain("0.555");
    expect(t).toContain("0.300");
  });

  test("brief date is the reader's local date, not the UTC date", () => {
    const late = new Date(2026, 10, 2, 23, 30); // 23:30 local on 2 Nov
    expect(text(briefHtml(lakeOf(), fixtureLakes, late))).toContain("Brief made 2 Nov 2026.");
  });

  test("standing method limits appear even when the lake has no limits of its own", () => {
    const file = {
      ...fixtureLakes,
      notes: "Areas are water within a 1 km search circle.",
      checks: [
        { lake: "a", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "x", days_apart: 0, s2_window_cloud_pct: 1, scope: "w", radar_km2: 0.1, optical_km2: 0.2, area_error_pct: 50, iou: 0.1137, zone_valid_share: 1, window_radar_km2: 0, window_optical_km2: 0, window_area_error_pct: null, window_iou: null },
        { lake: "b", nisar_date: "2026-08-17", nisar_track: "055A", s2_date: "2026-08-17", s2_id: "y", days_apart: 0, s2_window_cloud_pct: 1, scope: "w", radar_km2: 0.1, optical_km2: 0.2, area_error_pct: 50, iou: 0.0049, zone_valid_share: 1, window_radar_km2: 0, window_optical_km2: 0, window_area_error_pct: null, window_iou: null },
      ],
    };
    const t = text(briefHtml(lakeOf({ limits: [] }), file, NOW));
    expect(t).toContain("Areas are water within a 1 km search circle.");
    expect(t).toContain("Not validated: frozen lakes, lakes under 0.05 km², and wind-roughened water.");
    expect(t).toContain("radar water overlapped optical water poorly at every lake checked (IoU 0.005–0.11); treat areas as indicative.");
    const own = text(briefHtml(lakeOf({ limits: ["Shadow hides the north shore."] }), file, NOW));
    expect(own).toContain("Shadow hides the north shore.");
    expect(own).toContain("Not validated:");
  });

  test("never prints 'None recorded'", () => {
    for (const lake of fixtureLakes.lakes) expect(text(briefHtml({ ...lake, limits: [] }, fixtureLakes, NOW))).not.toContain("None recorded");
  });

  test("test_brief_lists_excluded_passes", () => {
    const lake = lakeOf({ excluded: [{ pass: "2026-07-07 156A", reason: "HH 25 dB above the track median" }] });
    const t = text(briefHtml(lake, fixtureLakes, NOW));
    expect(t).toContain("2026-07-07 156A: HH 25 dB above the track median");
  });

  test("test_brief_without_downstream_says_not_in_build", () => {
    expect(text(briefHtml(lakeOf({ downstream: null }), fixtureLakes, NOW))).toContain("Downstream exposure: not in this build");
    const t = text(briefHtml(lakeOf({ downstream: "Hassanabad bridge", downstream_source: "OSM" }), fixtureLakes, NOW));
    expect(t).toContain("Downstream: Hassanabad bridge (OSM)");
    expect(t).not.toContain("not in this build");
  });

  test("unmeasured statuses show the reason and never a zero area", () => {
    const hidden = fixtureLakes.lakes.find((l) => l.id === "hidden")!;
    const t = text(briefHtml(hidden, fixtureLakes, NOW));
    expect(t).toContain("Not observable");
    expect(t).toContain("Fixture reason for hidden.");
    expect(t).not.toContain("0 km²");
    expect(t).not.toContain("0.000");
  });

  test("includes the Sentinel-2 cross-check for the lake", () => {
    const file = {
      ...fixtureLakes,
      checks: [{ lake: "stable", nisar_date: "2026-10-23", nisar_track: "156A", s2_date: "2026-10-21", s2_id: "x", days_apart: 2, s2_window_cloud_pct: 4, scope: "w", radar_km2: 0.127, optical_km2: 0.13, area_error_pct: 2, iou: 0.8, zone_valid_share: 1, window_radar_km2: 0, window_optical_km2: 0, window_area_error_pct: null, window_iou: null }],
    };
    const t = text(briefHtml(lakeOf(), file, NOW));
    expect(t).toContain("One NISAR pass vs one Sentinel-2 scene:");
    expect(t).toContain("23 Oct 2026");
    expect(text(briefHtml(lakeOf({ id: "other" }), file, NOW))).not.toContain("One NISAR pass vs one Sentinel-2 scene");
  });

  test("escapes text from data", () => {
    const lake = lakeOf({ name: "<img src=x onerror=alert(1)>", coord_source: "<b>src</b>", limits: ["<script>1</script>"] });
    const html = briefHtml(lake, fixtureLakes, NOW);
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<b>src");
    expect(html).toContain("&lt;img");
  });

  test("test_brief_has_no_banned_claims", () => {
    for (const lake of fixtureLakes.lakes) {
      const withSeries = { ...lake, series: [pass("2026-10-01", 0.1, 0.9)], excluded: [{ pass: "p", reason: "r" }], limits: ["l"] };
      expect(findBannedClaims(text(briefHtml(withSeries, fixtureLakes, NOW)))).toEqual([]);
    }
  });

  test("test_printBrief_calls_print", () => {
    const print = vi.fn();
    const win = { document, print } as unknown as Window;
    printBrief(lakeOf(), fixtureLakes, win);
    expect(print).toHaveBeenCalledTimes(1);
    expect(document.querySelectorAll(".lake-brief")).toHaveLength(1);
    printBrief(lakeOf({ name: "Second" }), fixtureLakes, win);
    expect(print).toHaveBeenCalledTimes(2);
    expect(document.querySelectorAll(".lake-brief")).toHaveLength(1);
    expect(document.querySelector(".lake-brief")!.textContent).toContain("Second");
  });
});
