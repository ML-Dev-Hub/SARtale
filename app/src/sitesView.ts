import { BADGE_LABELS, cardFor, story } from "./content";
import { toChartSeries, type ChartSeries } from "./sites";
import { formatDate, maturityBanner } from "./timeline";
import type { Manifest, Site } from "./types";

export type ChartData = ChartSeries;

/** Draws the HH and HV curves into the element. The uPlot implementation lives in chart.ts; tests pass a fake. */
export type ChartFactory = (el: HTMLElement, data: ChartData) => { destroy(): void };

export interface SitesViewOptions {
  /** null when data/sites.json is absent. */
  sites: Site[] | null;
  manifest: Manifest;
  createChart?: ChartFactory;
}

export interface SitesViewHandle {
  /** Open the card for a site. Unknown ids are ignored. */
  select(id: string): void;
  destroy(): void;
}

const TEMPLATE = `
<p class="sites-empty" data-role="empty" hidden>No site curves yet</p>
<div class="sites-body" data-role="body" hidden>
  <ul class="site-list" data-role="list" aria-label="Sites"></ul>
  <article class="card" data-role="card" aria-labelledby="card-title" hidden>
    <header class="card-head">
      <h2 class="card-title" id="card-title" data-role="card-title" tabindex="-1"></h2>
      <p class="badge" data-role="card-evidence"></p>
    </header>
    <p class="card-role" data-role="card-role"></p>
    <figure class="chart-fig">
      <div class="chart" data-role="card-chart" role="img" aria-label=""></div>
      <figcaption class="legend">
        <span class="key key-hh">HH</span> <span class="key key-hv">HV</span> backscatter in dB. A break in a line means no valid value on that date.
      </figcaption>
    </figure>
    <p class="slot" data-role="card-dates"></p>
    <p class="slot" data-role="card-observation"></p>
    <p class="slot" data-role="card-hypothesis"></p>
    <p class="slot" data-role="card-test"></p>
    <p class="slot" data-role="card-limits"></p>
    <p class="slot source" data-role="card-source"></p>
    <details class="values">
      <summary>Values by date</summary>
      <table data-role="card-table">
        <thead><tr><th scope="col">Date</th><th scope="col">HH (dB)</th><th scope="col">HV (dB)</th><th scope="col">Valid</th></tr></thead>
        <tbody></tbody>
      </table>
    </details>
  </article>
</div>`;

const NO_DATA = "no data";
const db = (v: number | null | undefined): string => (v == null ? NO_DATA : v.toFixed(1));
const pct = (v: number | null | undefined): string => (v == null ? NO_DATA : `${Math.round(v * 100)}%`);

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
  const cardEl = q("card");
  const sites = opts.sites ?? [];
  let chart: { destroy(): void } | undefined;

  const hasSites = sites.length > 0;
  emptyEl.hidden = hasSites;
  bodyEl.hidden = !hasSites;

  for (const site of sites) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "site-item";
    btn.dataset.site = site.id;
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
    listEl.append(li);
  }

  /** A paragraph with a bold label and plain text, built without innerHTML. */
  function slot(role: string, label: string, text: string): void {
    const p = q(role);
    const strong = document.createElement("strong");
    strong.textContent = `${label}: `;
    p.replaceChildren(strong, document.createTextNode(text));
  }

  function select(id: string): void {
    const site = sites.find((s) => s.id === id);
    if (!site) return;
    const card = cardFor(id);
    const data = toChartSeries(site);
    const sortedDates = site.series.map((r) => r.date).sort();
    for (const b of listEl.querySelectorAll<HTMLButtonElement>("[data-site]")) {
      b.setAttribute("aria-pressed", String(b.dataset.site === id));
    }

    q("card-title").textContent = story[id]?.title ?? site.name;
    q("card-role").textContent = site.role;
    const badge = q("card-evidence");
    badge.textContent = BADGE_LABELS[card.evidence];
    badge.dataset.evidence = card.evidence;

    const range = sortedDates.length
      ? `${formatDate(sortedDates[0])} to ${formatDate(sortedDates[sortedDates.length - 1])}, ${sortedDates.length} acquisitions`
      : "no acquisitions";
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
          for (const text of [formatDate(r.date), db(r.hh_db), db(r.hv_db), pct(r.valid_fraction)]) {
            const td = document.createElement("td");
            td.textContent = text;
            tr.append(td);
          }
          return tr;
        }),
    );

    chart?.destroy();
    chart = undefined;
    const chartEl = q("card-chart");
    chartEl.replaceChildren();
    chartEl.setAttribute("aria-label", `HH and HV backscatter in dB for ${site.name}, ${range}. The values are in the table below.`);
    if (opts.createChart && data.x.length) chart = opts.createChart(chartEl, data);

    cardEl.hidden = false;
    q("card-title").focus({ preventScroll: true });
    cardEl.scrollIntoView?.({ block: "nearest" });
  }

  return {
    select,
    destroy: () => {
      chart?.destroy();
      chart = undefined;
      root.innerHTML = "";
    },
  };
}
