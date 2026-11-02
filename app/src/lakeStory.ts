import { lakeStoryBeats, type LakeBeatAction } from "./content";
import { fillTokens } from "./evidenceView";
import { featuredLake, lakeTokens, statusSentence, type LakesFile } from "./lakes";
import { formatDate } from "./timeline";

/** A beat with its tokens filled, ready to show. */
export interface ResolvedBeat {
  id: string;
  beat: number;
  label: string;
  title: string;
  body: string[];
  quote?: { text: string; cite: string };
  actions: { action: LakeBeatAction; label: string; lakeId?: string }[];
}

const ACTION_LABELS: Record<Exclude<LakeBeatAction, "lake">, string> = {
  "lake-watch": "Open Lake Watch",
  dance: "Open The Dance",
  "peshawar-tour": "Start the guided Peshawar tour",
  evidence: "Read How we know",
};

/**
 * The six beats with numbers and names filled from lakes.json. Beat 4 shows the featured lake (featuredLake), found
 * from the data each time. Without lake data, beats that need it say so instead.
 */
export function resolveLakeBeats(file: LakesFile | null): ResolvedBeat[] {
  const featured = featuredLake(file);
  const base = file ? lakeTokens(file) : {};
  const tokens: Record<string, string> = { ...base };
  if (featured) {
    const excluded = featured.excluded.map((e) => `${e.pass}: ${e.reason}`).join("; ");
    Object.assign(tokens, {
      lake_name: featured.name,
      lake_looks: String(featured.status.looks),
      lake_latest: featured.status.latest_date ? formatDate(featured.status.latest_date) : "no date",
      lake_sentence: statusSentence(featured),
      lake_cloud_looks: String(featured.cloud_window_looks),
      lake_coord: featured.coord_source,
      lake_area_label: featured.area_label,
      lake_excluded: featured.excluded.length
        ? `${featured.excluded.length} ${featured.excluded.length === 1 ? "pass was" : "passes were"} left out of the trend (${excluded}).`
        : "",
    });
  }
  return lakeStoryBeats.map((b) => {
    const needsData = b.id === "one-lake" ? !featured : !file;
    const lines = needsData && b.noData ? b.noData : b.body;
    const actions: ResolvedBeat["actions"] = [];
    for (const a of b.actions ?? []) {
      if (a === "lake") {
        if (featured) actions.push({ action: a, label: `Open ${featured.name} in Lake Watch`, lakeId: featured.id });
      } else actions.push({ action: a, label: ACTION_LABELS[a] });
    }
    return {
      id: b.id,
      beat: b.beat,
      label: b.label,
      title: needsData && b.noDataTitle ? b.noDataTitle : fillTokens(b.title, tokens),
      body: lines.map((t) => fillTokens(t, tokens)).filter((t) => t.trim() !== ""),
      quote: b.quote,
      actions,
    };
  });
}

export interface LakeStoryOptions {
  lakes: LakesFile | null;
  onAction(action: LakeBeatAction, lakeId?: string): void;
}

export interface LakeStoryHandle {
  go(index: number, focus?: boolean): void;
  index(): number;
  destroy(): void;
}

const TEMPLATE = `
<div class="ls-wrap">
  <ol class="ls-steps" data-role="ls-steps" aria-label="The six parts of the story"></ol>
  <article class="card ls-card" data-role="ls-card" aria-live="polite">
    <p class="ls-kicker" data-role="ls-kicker"></p>
    <h2 class="ls-title" data-role="ls-title" tabindex="-1"></h2>
    <blockquote class="ls-quote" data-role="ls-quote" hidden></blockquote>
    <p class="ls-cite" data-role="ls-cite" hidden></p>
    <div class="ls-text" data-role="ls-text"></div>
    <div class="ls-actions" data-role="ls-actions"></div>
  </article>
  <div class="ls-nav">
    <button type="button" class="btn" data-role="ls-back">Back</button>
    <p class="ls-count" data-role="ls-count"></p>
    <button type="button" class="btn small-teal" data-role="ls-next">Next</button>
  </div>
  <p class="ls-screening">Indicative screening on provisional NISAR data; official warnings come from PMD and NDMA.</p>
</div>`;

/** The lake story: one card per beat, back and next, numbered steps. Beat 5 hands over to the Peshawar chapter. */
export function createLakeStoryView(root: HTMLElement, opts: LakeStoryOptions): LakeStoryHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => root.querySelector<T>(`[data-role="${role}"]`)!;
  const beats = resolveLakeBeats(opts.lakes);
  let at = 0;

  const steps = q("ls-steps");
  beats.forEach((b, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ls-step";
    btn.dataset.step = String(i);
    btn.textContent = String(b.beat);
    btn.setAttribute("aria-label", `Part ${b.beat} of ${beats.length}: ${b.label}`);
    btn.title = b.label;
    btn.addEventListener("click", () => go(i, true));
    li.append(btn);
    steps.append(li);
  });

  function go(index: number, focus = false): void {
    if (index < 0 || index >= beats.length) return;
    at = index;
    const b = beats[index];
    const card = q("ls-card");
    card.id = b.id;
    card.dataset.beat = b.id;
    q("ls-kicker").textContent = `${b.beat} of ${beats.length}. ${b.label}`;
    q("ls-title").textContent = b.title;
    q("ls-quote").hidden = !b.quote;
    q("ls-quote").textContent = b.quote?.text ?? "";
    q("ls-cite").hidden = !b.quote;
    q("ls-cite").textContent = b.quote ? `Source: ${b.quote.cite}` : "";
    q("ls-text").replaceChildren(
      ...b.body.map((t) => {
        const p = document.createElement("p");
        p.textContent = t;
        return p;
      }),
    );
    q("ls-actions").replaceChildren(
      ...b.actions.map((a) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn small-teal";
        btn.dataset.action = a.action;
        btn.textContent = a.label;
        btn.addEventListener("click", () => opts.onAction(a.action, a.lakeId));
        return btn;
      }),
    );
    q("ls-count").textContent = `${index + 1} of ${beats.length}`;
    q<HTMLButtonElement>("ls-back").disabled = index === 0;
    q<HTMLButtonElement>("ls-next").disabled = index === beats.length - 1;
    for (const s of steps.querySelectorAll<HTMLButtonElement>(".ls-step")) {
      const n = Number(s.dataset.step);
      s.classList.toggle("done", n < index);
      s.classList.toggle("current", n === index);
      if (n === index) s.setAttribute("aria-current", "step");
      else s.removeAttribute("aria-current");
    }
    if (focus) q("ls-title").focus({ preventScroll: true });
  }

  q("ls-back").addEventListener("click", () => go(at - 1, true));
  q("ls-next").addEventListener("click", () => go(at + 1, true));
  go(0);

  return {
    go,
    index: () => at,
    destroy: () => {
      root.innerHTML = "";
    },
  };
}
