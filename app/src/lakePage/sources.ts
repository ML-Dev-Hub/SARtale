import { checkLine } from "../lakeWatchView";
import { methodLimits, type Lake, type LakesFile } from "../lakes";
import { provinceName } from "../provinces";

const DASH = "—";

/** The distinct tracks with a valid pass for this lake. */
function passTracks(l: Lake): string[] {
  return [...new Set(l.series.filter((p) => p.area_km2 !== null && p.excluded === null).map((p) => p.track))].sort();
}

/** The wait for a change to show, as the pipeline words it (lakestatus.latency_text): by number of tracks. */
function latencyText(tracks: number): string {
  return tracks >= 3 ? "5–12 days" : tracks === 2 ? "8–12 days" : "12–24 days";
}

function outlineText(l: Lake): string {
  if (l.outline_source) return l.outline_source;
  const m = /\((\d+(?:\.\d+)?)\s*m circle\)/.exec(l.area_label);
  return m ? `Search circle of ${Number(m[1]) / 1000} km (no mapped outline)` : "Search circle (no mapped outline)";
}

function checkText(l: Lake, file: LakesFile): string {
  const lines = file.checks.filter((c) => c.lake === l.id).map(checkLine);
  const notes = (file.check_notes ?? []).filter((c) => c.lake === l.id).map((c) => `Sentinel-2 check: ${c.note}.`);
  const all = [...lines, ...notes];
  if (all.length) return all.join(" ");
  return l.status.status === "Not yet validated against Sentinel-2" && l.status.reason
    ? l.status.reason
    : "Not validated against Sentinel-2: no check for this lake in this build.";
}

function suparcoText(l: Lake): string {
  const s = l.suparco;
  if (!s || s.match === "possible") return "No SUPARCO PDGL ID matches this lake by map position and area.";
  return s.match === "official"
    ? `SUPARCO PDGL ${s.id}: from SUPARCO's official list (${s.source}).`
    : `SUPARCO PDGL ${s.id}: our match by map position and area to SUPARCO's published IDs; SUPARCO does not publish coordinates.`;
}

function latencyRow(l: Lake): string {
  const t = passTracks(l);
  if (!t.length) return DASH;
  const n = t.length;
  return `${n} ${n === 1 ? "track" : "tracks"} (${t.join(", ")}) ${n === 1 ? "passes" : "pass"} over this lake, so a change shows here ${latencyText(n)} after it begins`;
}

function elevationRow(l: Lake): string {
  if (typeof l.elevation_m !== "number") return DASH;
  const m = `${Math.round(l.elevation_m).toLocaleString("en-GB")} m`;
  return l.elevation_source ? `${m} (${l.elevation_source})` : m;
}

function districtRow(l: Lake): string {
  const src = (l as Lake & { district_source?: string | null }).district_source;
  const place = [l.district, provinceName(l.province)].filter((s): s is string => !!s).join(", ");
  if (!place) return DASH;
  return src ? `${place} (${src})` : place;
}

/** Where each fact on the lake page comes from, in a fixed order; a missing value shows "—". */
export function sourceRows(l: Lake, file: LakesFile): { k: string; v: string }[] {
  return [
    { k: "Coordinates", v: l.coord_source || DASH },
    { k: "Outline", v: outlineText(l) },
    { k: "Sentinel-2 check", v: checkText(l, file) },
    { k: "SUPARCO match", v: suparcoText(l) },
    { k: "Method", v: file.method?.water || DASH },
    { k: "Latency for this lake", v: latencyRow(l) },
    { k: "Elevation", v: elevationRow(l) },
    { k: "District", v: districtRow(l) },
  ];
}

/** The lake's own limits, then the method's standing limits. */
export function limitsList(l: Lake, file: LakesFile): string[] {
  return [...l.limits, ...methodLimits(file)];
}
