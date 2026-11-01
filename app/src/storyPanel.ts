import type { StoryStep } from "./content";
import { buildAxis, mountAxis } from "./timeAxis";
import { formatDate } from "./timeline";
import type { Manifest, Site } from "./types";

export interface StoryPanelOptions {
  steps: StoryStep[];
  manifest: Manifest;
  sites: Site[] | null;
  /** The step is now showing: move the map to it. `from` is the step the person came from, or -1. */
  onGo(step: StoryStep, index: number, from: number): void;
  /** The person chose to leave the story for free exploring. */
  onExit(): void;
  onOpenSite(id: string): void;
  onPlay(): void;
}

export interface StoryPanelHandle {
  go(index: number): void;
  index(): number;
  count(): number;
  destroy(): void;
}

const TEMPLATE = `
<div class="story-top">
  <ol class="beats" data-role="story-beats" aria-label="The six parts of the story"></ol>
  <button type="button" class="story-leave" data-role="story-exit">Explore freely</button>
</div>
<div class="story-body" data-role="story-content" aria-live="polite">
  <p class="story-kicker" data-role="story-kicker"></p>
  <h2 class="story-title" data-role="story-title" tabindex="-1"></h2>
  <div class="story-text" data-role="story-text"></div>
  <figure class="story-strip" data-role="story-strip" hidden>
    <div class="axis axis-mini" data-role="story-axis"><div class="axis-layer" data-role="story-axis-layer"></div></div>
    <figcaption data-role="story-strip-caption"></figcaption>
  </figure>
  <p class="story-source" data-role="story-source" hidden></p>
  <div class="story-actions" data-role="story-actions"></div>
</div>
<div class="story-nav">
  <button type="button" class="btn story-back" data-role="story-back">Back</button>
  <p class="story-count" data-role="story-count"></p>
  <button type="button" class="btn story-next" data-role="story-next">Next</button>
</div>`;

/** The guided story: one card with six parts, back and next, and a way out. It tells the app where to point the map. */
export function createStoryPanel(root: HTMLElement, opts: StoryPanelOptions): StoryPanelHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => {
    const el = root.querySelector<T>(`[data-role="${role}"]`);
    if (!el) throw new Error(`missing element ${role}`);
    return el;
  };
  const { steps } = opts;
  let at = -1;
  let axis: ReturnType<typeof mountAxis> | undefined;

  // One dot per beat, a button that jumps to the beat's first step.
  const beatNumbers = [...new Set(steps.map((s) => s.beat))];
  const beatsEl = q("story-beats");
  for (const n of beatNumbers) {
    const first = steps.findIndex((s) => s.beat === n);
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "beat-dot";
    b.dataset.beat = String(n);
    b.setAttribute("aria-label", `Part ${n} of ${beatNumbers.length}: ${steps[first].label}`);
    b.title = steps[first].label;
    b.addEventListener("click", () => go(first));
    li.append(b);
    beatsEl.append(li);
  }

  const button = (label: string, cls: string, onClick: () => void): HTMLButtonElement => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = cls;
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  };

  function render(step: StoryStep, index: number): void {
    const inBeat = steps.filter((s) => s.beat === step.beat);
    const part = inBeat.length > 1 ? `, ${step.stop} (${inBeat.indexOf(step) + 1} of ${inBeat.length})` : "";
    q("story-kicker").textContent = `${step.label}${part}`;
    q("story-title").textContent = step.title;
    q("story-text").replaceChildren(
      ...step.body.map((t) => {
        const p = document.createElement("p");
        p.textContent = t;
        return p;
      }),
    );

    const strip = q("story-strip");
    strip.hidden = !step.strip;
    if (step.strip) {
      const model = buildAxis(opts.manifest);
      const track = q("story-axis");
      axis?.destroy();
      axis = mountAxis(track, q("story-axis-layer"), model, { onPick() {}, disabled: () => true, marks: step.marks });
      const gap = model.gap ? ` ${model.gap.label}.` : "";
      const peak = step.marks?.length ? ` ${step.marks.map((m) => m.label).join(", ")}.` : "";
      q("story-strip-caption").textContent = `The nine passes by date.${gap}${peak}`;
      track.setAttribute("role", "img");
      track.setAttribute(
        "aria-label",
        `Timeline from ${formatDate(model.dates[0].date)} to ${formatDate(model.dates[model.dates.length - 1].date)} with ${model.dates.length} passes.${gap}${peak}`,
      );
    }

    const src = q("story-source");
    src.hidden = !step.source;
    src.textContent = step.source ? `Source: ${step.source}` : "";

    const actions = q("story-actions");
    actions.replaceChildren();
    if (step.action === "play") actions.append(button("Play the season", "btn small-teal", opts.onPlay));
    const site = step.site ? opts.sites?.find((s) => s.id === step.site) : undefined;
    if (site) actions.append(button(`Open the ${site.name} card`, "btn small-ghost", () => opts.onOpenSite(site.id)));

    q("story-count").textContent = `${index + 1} of ${steps.length}`;
    q<HTMLButtonElement>("story-back").disabled = index === 0;
    const next = q<HTMLButtonElement>("story-next");
    next.textContent = index === steps.length - 1 ? "Explore the map" : "Next";
    for (const b of beatsEl.querySelectorAll<HTMLButtonElement>(".beat-dot")) {
      const n = Number(b.dataset.beat);
      b.classList.toggle("done", n < step.beat);
      b.classList.toggle("current", n === step.beat);
      if (n === step.beat) b.setAttribute("aria-current", "step");
      else b.removeAttribute("aria-current");
    }
  }

  function go(index: number): void {
    if (index < 0 || index >= steps.length) return;
    const from = at;
    at = index;
    render(steps[index], index);
    opts.onGo(steps[index], index, from);
  }

  q("story-back").addEventListener("click", () => go(at - 1));
  q("story-next").addEventListener("click", () => (at >= steps.length - 1 ? opts.onExit() : go(at + 1)));
  q("story-exit").addEventListener("click", () => opts.onExit());
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      opts.onExit();
    }
  });

  return {
    go,
    index: () => at,
    count: () => steps.length,
    destroy: () => {
      axis?.destroy();
      root.innerHTML = "";
    },
  };
}
