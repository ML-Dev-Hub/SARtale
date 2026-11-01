import { BADGE_LABELS, cardFor, story, type SiteCard } from "./content";
import { toChartSeries, type ChartSeries } from "./sites";
import { changeExclusion, flagFor, formatDate, maturityBanner } from "./timeline";
import type { Manifest, Site } from "./types";

export type ChartData = ChartSeries;

export interface ChartHooks {
  /** Called with the index of the date the person tapped or clicked on the chart. */
  onPick?(index: number): void;
}

/** Draws the HH and HV curves into the element. The uPlot implementation lives in chart.ts; tests pass a fake. */
export type ChartFactory = (el: HTMLElement, data: ChartData, hooks?: ChartHooks) => { destroy(): void };

export interface SitesViewOptions {
  /** null when data/sites.json is absent. */
  sites: Site[] | null;
  manifest: Manifest;
  createChart?: ChartFactory;
  /** Show the map on a date, centred on the site. Without it the card has no map buttons. */
  onShowDate?(date: string, site: Site): void;
}

export interface SitesViewHandle {
  /** Open the card for a site. Unknown ids are ignored. */
  select(id: string): void;
  destroy(): void;
}

const TEMPLATE = `
<p class="sites-empty" data-role="empty" hidden>No site curves yet</p>
<p class="sites-why" data-role="empty-why" hidden>Curves appear once the calibrated build has run.</p>
<div class="sites-body" data-role="body" hidden>
  <nav class="site-nav" aria-label="Sites" data-role="nav">
    <h2 class="site-group-title" data-role="controls-title">Controls</h2>
    <p class="site-group-note" data-role="controls-note">Expected to stay steady. They were used when the Change map's limits were set.</p>
    <ul class="site-list" data-role="controls-list" aria-labelledby="controls-title-id"></ul>
    <h2 class="site-group-title" data-role="moved-title">Where something moved</h2>
    <ul class="site-list" data-role="list"></ul>
  </nav>
  <article class="card" data-role="card" aria-labelledby="card-title" hidden>
    <header class="card-head">
      <div class="card-heading">
        <h2 class="card-title" id="card-title" data-role="card-title" tabindex="-1"></h2>
        <p class="card-role" data-role="card-role"></p>
      </div>
      <div class="card-tags">
        <p class="badge" data-role="card-evidence"></p>
        <p class="tag-control" data-role="card-control-tag" hidden>Control</p>
      </div>
    </header>
    <div class="card-grid">
      <div class="card-visual">
        <figure class="chart-fig">
          <div class="chart" data-role="card-chart" role="img" aria-label=""></div>
          <figcaption class="legend">
            <span class="key key-hh">HH</span> <span class="key key-hv">HV</span> backscatter in dB. A break in a line means no valid value on that date.
            <span data-role="card-tap-hint" hidden>Tap a point on the chart, or a date in the table, to see the map on that day.</span>
          </figcaption>
        </figure>
        <div class="picked" data-role="card-pick" role="status" hidden>
          <p class="picked-text" data-role="card-pick-text"></p>
          <button type="button" class="btn small-teal" data-role="card-pick-go">Show this date on the map</button>
        </div>
        <button type="button" class="btn small-teal" data-role="card-map" hidden>See this site on the map</button>
      </div>
      <div class="card-text">
        <p class="slot control-note" data-role="card-control" hidden></p>
        <p class="slot lead" data-role="card-observation"></p>
        <p class="slot hypothesis" data-role="card-hypothesis"></p>
        <p class="slot test" data-role="card-test"></p>
        <p class="slot limits" data-role="card-limits"></p>
        <p class="slot step" data-role="card-step" hidden></p>
      </div>
    </div>
    <p class="slot" data-role="card-change" hidden></p>
    <p class="slot fine" data-role="card-dates"></p>
    <p class="slot fine source" data-role="card-source"></p>
    <details class="values">
      <summary>Values by date</summary>
      <table data-role="card-table">
        <thead><tr><th scope="col">Date</th><th scope="col">HH (dB)</th><th scope="col">HV (dB)</th><th scope="col">Valid</th><th scope="col" data-role="card-change-col" hidden>Unusual dates score</th></tr></thead>
        <tbody></tbody>
      </table>
    </details>
  </article>
</div>`;

const NO_DATA = "no data";
const db = (v: number | null | undefined): string => (v == null ? NO_DATA : v.toFixed(1));
const withUnit = (v: number | null | undefined): string => (v == null ? NO_DATA : `${v.toFixed(1)} dB`);
const pct = (v: number | null | undefined): string => (v == null ? NO_DATA : `${Math.round(v * 100)}%`);
const dayMonth = (iso: string): string => formatDate(iso).split(" ").slice(0, 2).join(" ");

/** A control is a site chosen because it should not change. The role says so in words. */
export function isControl(site: Pick<Site, "role">): boolean {
  return /\bcontrol\b/i.test(site.role);
}

/** What the map's own test says around a site, in words that never show a small sample as a bare percentage. */
export function mapCheckText(card: SiteCard, step: { map_share: number }, pixelM: number): string {
  const c = card.mapCheck;
  if (c) {
    const where = `within ${c.radius_m} m of the site`;
    return c.flagged_pct === 0
      ? `None of the ${c.pixels} map pixels (${pixelM} m) ${where} are flagged.`
      : `${c.flagged_pct}% of the ${c.pixels} map pixels (${pixelM} m) ${where} are flagged.`;
  }
  return step.map_share > 0
    ? "Some of the few map pixels within 150 m of the site are flagged, too few to give a percentage."
    : "None of the few map pixels within 150 m of the site are flagged.";
}

export function createSitesView(root: HTMLElement, opts: SitesViewOptions): SitesViewHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => {
    const el = root.querySelector<T>(`[data-role="${role}"]`);
    if (!el) throw new Error(`missing element ${role}`);
    return el;
  };
  const emptyEl = q("empty");
  const bodyEl = q("body");
  const listEl = q("list");
  const controlsList = q("controls-list");
  const cardEl = q("card");
  const sites = opts.sites ?? [];
  q("card-change-col").hidden = !opts.manifest.change;
  q("controls-title").id = "controls-title-id";
  controlsList.setAttribute("aria-labelledby", "controls-title-id");
  q("moved-title").id = "moved-title-id";
  listEl.setAttribute("aria-labelledby", "moved-title-id");
  let chart: { destroy(): void } | undefined;
  let current: Site | undefined;
  let picked: string | undefined;

  const hasSites = sites.length > 0;
  emptyEl.hidden = hasSites;
  q("empty-why").hidden = hasSites;
  bodyEl.hidden = !hasSites;
  const controls = sites.filter(isControl);
  q("controls-title").hidden = controls.length === 0;
  q("controls-note").hidden = controls.length === 0;
  controlsList.hidden = controls.length === 0;
  // With no controls in the list there is nothing to tell apart, so the second heading goes too.
  q("moved-title").hidden = controls.length === 0;

  for (const site of sites) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "site-item";
    btn.dataset.site = site.id;
    if (isControl(site)) btn.dataset.control = "true";
    btn.setAttribute("aria-pressed", "false");
    const name = document.createElement("span");
    name.className = "site-name";
    name.textContent = story[site.id]?.title ?? site.name;
    const role = document.createElement("span");
    role.className = "site-role";
    role.textContent = site.role;
    btn.append(name, role);
    btn.addEventListener("click", () => select(site.id));
    li.append(btn);
    (isControl(site) ? controlsList : listEl).append(li);
  }

  /** A paragraph with a label and plain text, built without innerHTML. */
  function slot(role: string, label: string, text: string): void {
    const p = q(role);
    const strong = document.createElement("strong");
    strong.textContent = label;
    const span = document.createElement("span");
    span.textContent = text;
    p.replaceChildren(strong, span);
  }

  /** One date's change score as text, keeping the reason for a missing score and the caution on a flagged date. */
  function scoreText(date: string, score: number | null | undefined): string {
    if (changeExclusion(opts.manifest, date)) return "Excluded from change analysis";
    if (score == null) return NO_DATA;
    return `${score.toFixed(1)}${flagFor(opts.manifest, date) ? " (flagged date)" : ""}`;
  }

  /** The site's largest step, read from its own curve, and what the map's own test says around it. */
  function stepSlot(site: Site, card: SiteCard): void {
    const step = site.step;
    const rule = opts.manifest.change?.step;
    const p = q("card-step");
    p.hidden = !step || !rule;
    if (!step || !rule) return;
    const sign = (v: number): string => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
    const size = `HH ${sign(step.hh_db)} dB, HV ${sign(step.hv_db)} dB between ${dayMonth(step.previous_date)} and ${dayMonth(step.date)}.`;
    // The card judges the site's averaged curve. The map judges each 90 m pixel, which is stricter, so the two can differ.
    const verdict = step.flagged
      ? "On the site's averaged curve this step passes the limits the map uses. That is more lenient than the map's own test, which judges each pixel."
      : "On the site's averaged curve this step is under the limits the map uses.";
    slot("card-step", step.flagged ? "On the Change map" : "Largest step, below the Change map's limits", [size, verdict, mapCheckText(card, step, rule.pixel_m), card.changeNote].filter(Boolean).join(" "));
  }

  /** The scores next to the curves, or nothing for a build with no change layer. */
  function changeSlot(site: Site): void {
    const change = opts.manifest.change;
    const p = q("card-change");
    p.hidden = !change;
    if (!change) return;
    const rows = [...site.series].sort((a, b) => (a.date < b.date ? -1 : 1));
    const scores = rows.map((r) => `${dayMonth(r.date)} ${scoreText(r.date, r.change_score)}`).join(", ");
    slot("card-change", "Unusual dates score", `The typical pixel here, where ${change.threshold} or more is highlighted on that view. ${scores}.`);
  }

  function pickDate(date: string): void {
    if (!current) return;
    picked = date;
    const row = current.series.find((r) => r.date === date);
    const hint = flagFor(opts.manifest, date);
    q("card-pick-text").textContent =
      `${formatDate(date)}: HH ${withUnit(row?.hh_db)}, HV ${withUnit(row?.hv_db)}.` + (hint ? ` ${hint}` : "");
    q("card-pick").hidden = !opts.onShowDate;
    for (const tr of q("card-table").querySelectorAll<HTMLElement>("tbody tr")) {
      tr.classList.toggle("picked-row", tr.dataset.date === date);
    }
  }

  function select(id: string): void {
    const site = sites.find((s) => s.id === id);
    if (!site) return;
    current = site;
    picked = undefined;
    const card = cardFor(id);
    const data = toChartSeries(site);
    const sortedDates = site.series.map((r) => r.date).sort();
    for (const b of root.querySelectorAll<HTMLButtonElement>("[data-site]")) {
      b.setAttribute("aria-pressed", String(b.dataset.site === id));
    }

    q("card-title").textContent = story[id]?.title ?? site.name;
    q("card-role").textContent = site.role;
    const badge = q("card-evidence");
    badge.textContent = BADGE_LABELS[card.evidence];
    badge.dataset.evidence = card.evidence;
    const control = isControl(site);
    q("card-control-tag").hidden = !control;
    q("card-control").hidden = !control;
    if (control) {
      slot(
        "card-control",
        "A control",
        "This place is expected to stay steady, so a quiet curve here is the right result. The controls were used in setting the Change map's limits, so they are not an independent test. An independent reviewer found that five fresh cities not used for the limits also stayed quiet (0% flagged within 450 m).",
      );
    }

    const range = sortedDates.length
      ? `${formatDate(sortedDates[0])} to ${formatDate(sortedDates[sortedDates.length - 1])}, ${sortedDates.length} acquisitions`
      : "no acquisitions";
    stepSlot(site, card);
    changeSlot(site);
    slot("card-dates", "Dates", card.dates.length ? card.dates.map(formatDate).join(", ") : "not set yet");
    slot("card-observation", "Observation", card.observation);
    slot("card-hypothesis", "Hypothesis", card.hypothesis);
    slot("card-test", "What would test it", card.test);
    slot("card-limits", "Limits", card.limits);
    slot("card-source", "Source", `${maturityBanner(opts.manifest).text}, ${range}. Mean backscatter in dB near the site, HH and HV.`);

    const tbody = q("card-table").querySelector("tbody")!;
    tbody.replaceChildren(
      ...[...site.series]
        .sort((a, b) => (a.date < b.date ? -1 : 1))
        .map((r) => {
          const tr = document.createElement("tr");
          tr.dataset.date = r.date;
          const cells = [formatDate(r.date), db(r.hh_db), db(r.hv_db), pct(r.valid_fraction)];
          if (opts.manifest.change) cells.push(scoreText(r.date, r.change_score));
          cells.forEach((text, i) => {
            const td = document.createElement("td");
            if (i === 0 && opts.onShowDate) {
              const b = document.createElement("button");
              b.type = "button";
              b.className = "date-link";
              b.textContent = text;
              b.setAttribute("aria-label", `${text}: show this date`);
              b.addEventListener("click", () => pickDate(r.date));
              td.append(b);
            } else td.textContent = text;
            tr.append(td);
          });
          return tr;
        }),
    );

    q("card-pick").hidden = true;
    q("card-map").hidden = !opts.onShowDate;
    q("card-tap-hint").hidden = !opts.onShowDate || !opts.createChart;

    chart?.destroy();
    chart = undefined;
    const chartEl = q("card-chart");
    chartEl.replaceChildren();
    const hhs = data.hh.filter((v): v is number => v != null);
    const hvs = data.hv.filter((v): v is number => v != null);
    const span = (v: number[]): string => (v.length ? `${Math.min(...v).toFixed(1)} to ${Math.max(...v).toFixed(1)} dB` : "no values");
    chartEl.setAttribute(
      "aria-label",
      `HH and HV backscatter in dB for ${site.name}, ${range}. HH runs from ${span(hhs)} and HV from ${span(hvs)}. Every value is in the table below.`,
    );
    if (opts.createChart && data.x.length) {
      chart = opts.createChart(chartEl, data, { onPick: (i) => data.x[i] !== undefined && pickDate(sortedDates[i]) });
    }

    cardEl.hidden = false;
    q("card-title").focus({ preventScroll: true });
    cardEl.scrollIntoView?.({ block: "nearest" });
  }

  q("card-pick-go").addEventListener("click", () => {
    if (current && picked) opts.onShowDate?.(picked, current);
  });
  q("card-map").addEventListener("click", () => {
    if (!current) return;
    const step = current.step;
    opts.onShowDate?.(picked ?? (step && step.flagged ? step.date : sitesLastDate(current)), current);
  });

  return {
    select,
    destroy: () => {
      chart?.destroy();
      chart = undefined;
      root.innerHTML = "";
    },
  };
}

/** The latest date on a site's curve. */
function sitesLastDate(site: Site): string {
  return site.series.map((r) => r.date).sort().at(-1) ?? "";
}
