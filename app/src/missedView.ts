import { story } from "./content";
import { coverageSegments, gapSummary, stateLabel, UNUSED_LABEL, type Segment } from "./gap";
import { acquisitionDates, flagFor, formatDate, orderedDates } from "./timeline";
import type { Manifest } from "./types";

export interface MissedViewOptions {
  manifest: Manifest;
}

export interface MissedViewHandle {
  destroy(): void;
}

const TEMPLATE = `
<div class="missed-scroll" data-role="scroll" role="region" tabindex="0" aria-label="What NISAR Missed: observation timeline and data gap">
  <h2 class="missed-title" data-role="title"></h2>
  <p class="slot gap-facts" data-role="gap-facts"></p>
  <figure class="missed-fig">
    <div class="strip" data-role="strip" role="img" aria-label=""></div>
    <div class="strip-ends" aria-hidden="true"><span data-role="strip-first"></span><span data-role="strip-last"></span></div>
    <figcaption>
      <ul class="legend-keys" data-role="legend" aria-label="Legend">
        <li><span class="swatch swatch-observed" aria-hidden="true"></span>Observed</li>
        <li><span class="swatch swatch-unused" aria-hidden="true"></span>Observed, not used in this build</li>
        <li><span class="swatch swatch-between" aria-hidden="true"></span>No observation, between passes (expected)</li>
        <li><span class="swatch swatch-gap" aria-hidden="true"></span>No observation, permanent data gap</li>
      </ul>
    </figcaption>
  </figure>
  <h3 class="missed-sub">Timeline in words</h3>
  <ol class="runs" data-role="runs"></ol>
  <h3 class="missed-sub">Dates NISAR observed (<span data-role="pass-count"></span>)</h3>
  <ul class="passes" data-role="passes"></ul>
  <p class="slot event-copy" data-role="event-copy"></p>
</div>`;

export interface Run {
  kind: "observed" | "unused" | "between" | "gap";
  from: string;
  to: string;
  days: number;
}

function kindOf(s: Segment): Run["kind"] {
  if (s.state === "observed") return "observed";
  if (s.state === "observed-unused") return "unused";
  return s.inGap ? "gap" : "between";
}

/** Consecutive days of the same kind joined into one run. */
export function toRuns(segments: Segment[]): Run[] {
  const runs: Run[] = [];
  for (const s of segments) {
    const kind = kindOf(s);
    const prev = runs[runs.length - 1];
    if (prev && prev.kind === kind) {
      prev.to = s.date;
      prev.days += 1;
    } else {
      runs.push({ kind, from: s.date, to: s.date, days: 1 });
    }
  }
  return runs;
}

function runText(r: Run): string {
  const span = r.from === r.to ? formatDate(r.from) : `${formatDate(r.from)} to ${formatDate(r.to)}`;
  if (r.kind === "observed") return `${stateLabel("observed")}: ${span}`;
  if (r.kind === "unused") return `${stateLabel("observed-unused")}: ${span}`;
  return `${stateLabel("no-observation")}, ${r.kind === "gap" ? "permanent data gap" : "between passes"}: ${span}`;
}

/** First and last day to draw: every date NISAR imaged, widened to the whole days the gap touches. */
function timelineRange(m: Manifest): [string, string] | null {
  const days = acquisitionDates(m);
  if (m.gap) {
    for (const t of [Date.parse(m.gap.start), Date.parse(m.gap.end)]) {
      if (Number.isFinite(t)) days.push(new Date(t).toISOString().slice(0, 10));
    }
  }
  days.sort();
  return days.length ? [days[0], days[days.length - 1]] : null;
}

export function createMissedView(root: HTMLElement, opts: MissedViewOptions): MissedViewHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => {
    const el = root.querySelector<T>(`[data-role="${role}"]`);
    if (!el) throw new Error(`missing element ${role}`);
    return el;
  };
  const m = opts.manifest;
  const copy = story["what-nisar-missed"];

  q("title").textContent = copy.title;

  // Verified facts, from the manifest only.
  const facts = gapSummary(m);
  q("gap-facts").textContent = facts
    ? `${facts} Days in the gap say ${stateLabel("no-observation")}. That says nothing about what happened on the ground.`
    : "This data lists no data gap.";

  // The only event copy is the labelled placeholder from story.json.
  q("event-copy").textContent = copy.summary;

  const built = new Set(orderedDates(m));
  const dates = acquisitionDates(m);
  q("pass-count").textContent = String(dates.length);
  q("passes").replaceChildren(
    ...dates.map((d) => {
      const li = document.createElement("li");
      const notes = [flagFor(m, d), built.has(d) ? undefined : `${UNUSED_LABEL}.`].filter(Boolean);
      li.textContent = notes.length ? `${formatDate(d)}. ${notes.join(" ")}` : formatDate(d);
      return li;
    }),
  );

  const range = timelineRange(m);
  const runs = range ? toRuns(coverageSegments(m, range[0], range[1])) : [];

  const strip = q("strip");
  strip.replaceChildren(
    ...runs.map((r) => {
      const cell = document.createElement("span");
      cell.className = `cell cell-${r.kind}`;
      cell.dataset.kind = r.kind;
      cell.style.flexGrow = String(r.days);
      if (r.kind === "gap") cell.textContent = "No data";
      return cell;
    }),
  );
  const unusedCount = dates.filter((d) => !built.has(d)).length;
  const hasGap = runs.some((r) => r.kind === "gap");
  strip.setAttribute(
    "aria-label",
    range
      ? `Timeline from ${formatDate(range[0])} to ${formatDate(range[1])}: ${dates.length} observed dates` +
          (unusedCount ? `, of which ${unusedCount} not used in this build` : "") +
          (hasGap ? ", and a permanent data gap with no observation" : "") +
          ". The same facts are listed below."
      : "No dates in this data",
  );
  q("strip-first").textContent = range ? formatDate(range[0]) : "";
  q("strip-last").textContent = range && range[0] !== range[1] ? formatDate(range[1]) : "";

  q("runs").replaceChildren(
    ...runs.map((r) => {
      const li = document.createElement("li");
      li.dataset.kind = r.kind;
      li.textContent = runText(r);
      return li;
    }),
  );

  return {
    destroy: () => {
      root.innerHTML = "";
    },
  };
}
