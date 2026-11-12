import { freezeFacts, freezeHeadline, frozenAreaLine, hasLakeNow, hasLevel, isFrozen, isTrendPass, levelMessage, loadLakes, methodLimits, processingVersions, statusSentence, type Lake, type LakesFile } from "./lakes";
import { checkLine } from "./lakeWatchView";
import { formatDate } from "./format";

const PASS_ROWS = 6;

const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

function list(items: string[]): string {
  return `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

/** YYYY-MM-DD of `d` in the reader's own time zone (the day they printed it), not UTC. */
export function localIsoDate(d: Date): string {
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "Data: newest NISAR pass for this lake 4 Nov 2026; data built 9 Nov 2026." so a reader can see how fresh the printout is. */
export function dataLine(lake: Lake, file: LakesFile): string {
  const newest = lake.series.reduce<string | null>((m, p) => (m === null || p.date > m ? p.date : m), null);
  const built = file.built ? formatDate(file.built.slice(0, 10)) : "unknown";
  return `Data: newest NISAR pass for this lake ${newest ? formatDate(newest) : "none yet"}; data built ${built}.`;
}

/**
 * The lake's initial message (a Watch, an Alert or a Decrease noted) as the brief's first block, or "" without one.
 */
export function briefMessage(lake: Lake): string {
  const m = levelMessage(lake);
  if (!m) return "";
  const since = lake.status.level_since ? `<p>${esc(`${m.level} since ${formatDate(lake.status.level_since)}.`)}</p>` : "";
  return `<div class="lake-brief-message" data-level="${esc(m.level)}">
<p class="lake-brief-message-title"><strong>${esc(m.title)}</strong></p>
<p>${esc(m.what)}</p>
<p>${esc(m.how_sure)}</p>
<p>${esc(m.not)}</p>
<p><strong>${esc(m.do)}</strong></p>${since}
</div>
`;
}

const zText = (z: number | null | undefined): string =>
  typeof z === "number" ? `${z > 0 ? "+" : z < 0 ? "−" : ""}${Math.abs(z).toFixed(1)}` : "–";

/** The one-page brief for a lake, as an HTML fragment. Every piece of data text is escaped. */
export function briefHtml(lake: Lake, file: LakesFile, generatedAt: Date): string {
  const minShare = file.constants.min_observable;
  const track = lake.status.track;
  const levels = hasLevel(lake) || lake.series.some((p) => p.z !== undefined);
  // With the levels every valid pass is compared with its own track: the latest of any track. An older build compared
  // only the status track's passes. A site with no lake now lists no areas: its dark radar area is not lake area.
  const valid = lake.series
    .filter((p) => hasLakeNow(lake) && (levels || p.track === track) && isTrendPass(p, minShare))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.track.localeCompare(a.track)))
    .slice(0, PASS_ROWS);
  const passesHead = isFrozen(lake) ? `Latest open-water passes${!levels && track ? ` on track ${esc(track)}` : ""} (no comparison while the lake is frozen)`
    : levels ? "Latest valid passes (each compared with the median of earlier passes on its own track)"
    : !track ? "Latest valid passes"
    : `Latest valid passes on track ${esc(track)} (the status compares only these)`;
  const extraHead = levels ? "<th>Baseline (km²)</th><th>z</th><th>Level set</th>" : "";
  const extra = (p: Lake["series"][number]): string => levels
    ? `<td>${typeof p.baseline_km2 === "number" ? p.baseline_km2.toFixed(3) : "–"}</td><td>${esc(zText(p.z))}</td><td>${esc(p.after_open ? "None (baseline rebuilding)" : p.level_contrib ?? "–")}</td>`
    : "";
  const passes = valid.length
    ? `<table class="lake-brief-passes"><thead><tr><th>Date</th><th>Track</th><th>Area (km²)</th><th>Observable share</th>${extraHead}<th>Processing version</th></tr></thead><tbody>${valid
        .map((p) => `<tr><td>${esc(formatDate(p.date))}</td><td>${esc(p.track)}</td><td>${(p.area_km2 as number).toFixed(3)}</td><td>${Math.round((p.observable_share as number) * 100)}%</td>${extra(p)}<td>${esc(p.crid ?? "")}</td></tr>`)
        .join("")}</tbody></table>`
    : `<p>${esc(lake.status.reason)}</p>`;
  const lakeLimits = lake.limits.length ? `<h3>Limits for this lake</h3>${list(lake.limits)}` : "";
  const checks = file.checks.filter((c) => c.lake === lake.id).map((c) => `<p>${esc(checkLine(c))}</p>`).join("")
    + (file.check_notes ?? []).filter((c) => c.lake === lake.id).map((c) => `<p>${esc(`Sentinel-2 check: ${c.note}.`)}</p>`).join("");
  const downstream = lake.downstream
    ? `Downstream: ${esc(lake.downstream)}${lake.downstream_source ? ` (${esc(lake.downstream_source)})` : ""}`
    : "Downstream exposure: not in this build";
  const outline = lake.outline_source ? `<p>Outline: ${esc(lake.outline_source)}</p>` : "";
  // The freeze state, as on the lake's card: the state and since when, the latest area greyed while frozen, the facts.
  const f = lake.freeze;
  const area = frozenAreaLine(lake);
  const ice = f
    ? `<h2>Lake ice</h2>
<p class="lake-brief-freeze">${esc(freezeHeadline(f))}.</p>${area ? `<p class="lake-brief-frozen-area">${esc(area)}</p>` : ""}${list(freezeFacts(lake))}${isFrozen(lake) ? "" : `<p>${esc(f.reason)}</p>`}
`
    : "";
  return `<section class="lake-brief" aria-label="Lake brief">
${briefMessage(lake)}<h1>${esc(lake.name)}</h1>
<p class="lake-brief-meta">Coordinates ${lake.lat.toFixed(4)}, ${lake.lon.toFixed(4)}. Source: ${esc(lake.coord_source)}</p>${outline}
<p class="lake-brief-meta">Measures: ${esc(lake.area_label)}. Brief made ${esc(formatDate(localIsoDate(generatedAt)))}.</p>
<p class="lake-brief-meta">${esc(dataLine(lake, file))}</p>
<h2>Status</h2>
<p class="lake-brief-status">${esc(statusSentence(lake, file.constants.change_factor))}</p>
${ice}<h2>${passesHead}</h2>
${passes}${checks}
<h2>Excluded passes</h2>
${lake.excluded.length ? list(lake.excluded.map((x) => `${x.pass}: ${x.reason}`)) : "<p>None.</p>"}
<h2>Limits</h2>
${list(methodLimits(file))}${lakeLimits}
<h2>Downstream</h2>
<p>${downstream}</p>
<p class="lake-brief-footer">Indicative screening from NISAR data (${esc(processingVersions(file.crid))}). Not an official warning; official warnings come from PMD, NDMA, GBDMA and PDMA. Built ${esc(file.built)}.</p>
</section>`;
}

/** Puts the brief at the end of <body>, replacing any earlier one, and opens the print dialog. Print CSS hides everything else. */
export function printBrief(lake: Lake, file: LakesFile, win: Window = window): void {
  const doc = win.document;
  doc.querySelectorAll(".lake-brief, .lake-brief-notice").forEach((e) => e.remove());
  const host = doc.createElement("div");
  host.innerHTML = briefHtml(lake, file, new Date());
  doc.body.append(...host.children);
  win.print();
}

/** Shows a short notice in place of a brief (no print): used when the newest data cannot be loaded or no longer list
 * the lake. */
function showNotice(text: string, win: Window): void {
  const doc = win.document;
  doc.querySelectorAll(".lake-brief, .lake-brief-notice").forEach((e) => e.remove());
  const p = doc.createElement("p");
  p.className = "lake-brief-notice";
  p.setAttribute("role", "alert");
  p.textContent = text;
  doc.body.append(p);
}

/** What printLatestBrief did: printed the newest data, refused because the newest data could not be loaded, or
 * refused a removed lake. */
export type BriefOutcome = "fresh" | "unavailable" | "removed";

export const BRIEF_UNAVAILABLE =
  "The latest lake data could not be loaded, so no brief is printed. Check the connection and try again, or reload the page.";

/**
 * Prints from the newest data on the server, so a tab left open across a weekly update still prints today's numbers.
 * When the newest data cannot be loaded (no connection, a timeout, or a file this page cannot read), prints nothing
 * and says so: the page's own copy may be out of date, or list a site the newest data removed. When the newest data no
 * longer list the lake (a site removed from the register), prints nothing and says so too: a removed site must never
 * get a newly dated brief.
 */
export async function printLatestBrief(
  lake: Lake,
  load: () => Promise<LakesFile | null> = () => loadLakes("data/lakes.json"),
  win: Window = window,
): Promise<BriefOutcome> {
  const fresh = await load();
  if (!fresh) {
    showNotice(BRIEF_UNAVAILABLE, win);
    return "unavailable";
  }
  const freshLake = fresh.lakes.find((l) => l.id === lake.id);
  if (!freshLake) {
    const built = fresh.built ? formatDate(fresh.built.slice(0, 10)) : "the newest build";
    showNotice(`${lake.name} is not in SARtale's data built ${built}: the site was removed or renamed, so no brief is printed. Reload the page to see the current list.`, win);
    return "removed";
  }
  printBrief(freshLake, fresh, win);
  return "fresh";
}
