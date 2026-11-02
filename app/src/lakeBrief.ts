import { statusSentence, type Lake, type LakesFile } from "./lakes";
import { checkLine } from "./lakeWatchView";
import { formatDate } from "./timeline";

const PASS_ROWS = 6;

const esc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

function list(items: string[]): string {
  return `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

/** The one-page brief for a lake, as an HTML fragment. Every piece of data text is escaped. */
export function briefHtml(lake: Lake, file: LakesFile, generatedAt: Date): string {
  const minShare = file.constants.min_observable;
  const valid = lake.series
    .filter((p) => p.excluded === null && p.area_km2 !== null && p.observable_share !== null && p.observable_share >= minShare)
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, PASS_ROWS);
  const passes = valid.length
    ? `<table class="lake-brief-passes"><thead><tr><th>Date</th><th>Track</th><th>Area (km²)</th><th>Observable share</th></tr></thead><tbody>${valid
        .map((p) => `<tr><td>${esc(formatDate(p.date))}</td><td>${esc(p.track)}</td><td>${(p.area_km2 as number).toFixed(3)}</td><td>${Math.round((p.observable_share as number) * 100)}%</td></tr>`)
        .join("")}</tbody></table>`
    : `<p>No valid NISAR passes yet.</p>`;
  const checks = file.checks.filter((c) => c.lake === lake.id).map((c) => `<p>${esc(checkLine(c))}</p>`).join("");
  const downstream = lake.downstream
    ? `Downstream: ${esc(lake.downstream)}${lake.downstream_source ? ` (${esc(lake.downstream_source)})` : ""}`
    : "Downstream exposure: not in this build";
  const outline = lake.outline_source ? `<p>Outline: ${esc(lake.outline_source)}</p>` : "";
  return `<section class="lake-brief" aria-label="Lake brief">
<h1>${esc(lake.name)}</h1>
<p class="lake-brief-meta">Coordinates ${lake.lat.toFixed(4)}, ${lake.lon.toFixed(4)}. Source: ${esc(lake.coord_source)}</p>${outline}
<p class="lake-brief-meta">Measures: ${esc(lake.area_label)}. Brief made ${esc(formatDate(generatedAt.toISOString().slice(0, 10)))}.</p>
<h2>Status</h2>
<p class="lake-brief-status">${esc(statusSentence(lake))}</p>
<h2>Latest valid passes</h2>
${passes}${checks}
<h2>Excluded passes</h2>
${lake.excluded.length ? list(lake.excluded.map((x) => `${x.pass}: ${x.reason}`)) : "<p>None.</p>"}
<h2>Limits</h2>
${lake.limits.length ? list(lake.limits) : "<p>None recorded.</p>"}
<h2>Downstream</h2>
<p>${downstream}</p>
<p class="lake-brief-footer">Indicative screening from provisional NISAR data. Not an official warning; official warnings come from PMD and NDMA. Built ${esc(file.built)}.</p>
</section>`;
}

/** Puts the brief at the end of <body>, replacing any earlier one, and opens the print dialog. Print CSS hides everything else. */
export function printBrief(lake: Lake, file: LakesFile, win: Window = window): void {
  const doc = win.document;
  doc.querySelectorAll(".lake-brief").forEach((e) => e.remove());
  const host = doc.createElement("div");
  host.innerHTML = briefHtml(lake, file, new Date());
  doc.body.append(...host.children);
  win.print();
}
