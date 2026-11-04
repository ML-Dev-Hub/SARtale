import { createEvidenceView } from "./evidenceView";
import type { Lake, LakesFile } from "./lakes";
import { createLakeStoryView } from "./lakeStory";
import { createLakeWatchView, type LakeChartFactory, type LocatorFactory } from "./lakeWatchView";
import type { RequestsClient } from "./lakeRequests";
import { renderStoryPage } from "./storyPage";

export interface AppOptions {
  /** Lake data from data/lakes.json, or null/undefined when the file is absent or unusable. */
  lakes?: LakesFile | null;
  /** Area-by-track chart for Lake Watch. */
  createLakeChart?: LakeChartFactory;
  /** Small map that marks the lakes. */
  createLakeLocator?: LocatorFactory;
  /** Called by "Print lake brief". */
  onLakeBrief?: (lake: Lake) => void;
  /** Client for the lake-request server. Without it the Add a lake form is shown disabled. */
  requests?: RequestsClient;
}

type View = "home" | "lakes" | "story" | "evidence";

const VIEW_NAMES: Record<View, string> = { home: "The story", lakes: "Lake Watch", story: "Story walkthrough", evidence: "How we know" };
/** Hashes that open a view on load, so a view can be linked to or screenshotted directly. */
const HASH_VIEWS: Record<string, View> = { "#lakes": "lakes", "#story": "story", "#evidence": "evidence" };
/** Every NISAR file in this build is NASA's provisional GCOV product, so the label is fixed. */
export const MATURITY = "Provisional NISAR data";

const TEMPLATE = `
<div class="shell" data-role="shell">
  <a class="skip" href="#main">Skip to the content</a>
  <header class="top">
    <button type="button" class="logo-btn" data-role="home" aria-label="SARtale: back to the start">
      <span class="logo-panel"><img class="logo" src="brand/logo-256.png" width="56" height="56" alt="SARtale Pakistan logo" /></span>
    </button>
    <p class="brand">SARtale</p>
    <p class="sr-only" data-role="view-name" aria-live="polite">The story</p>
    <nav class="views" aria-label="Views">
      <button type="button" class="view-btn" data-role="view-home" aria-pressed="false">The story</button>
      <button type="button" class="view-btn" data-role="view-lakes" aria-pressed="false">Lake Watch</button>
      <button type="button" class="view-btn" data-role="view-evidence" aria-pressed="false">How we know</button>
    </nav>
    <p class="maturity" data-role="maturity" data-kind="provisional"></p>
  </header>

  <main class="workspace" id="main" tabindex="-1">
    <div class="home-root" data-role="home-root"></div>

    <section class="sites-view lakes-view" data-role="lakes-view" aria-label="Lake Watch" hidden>
      <div class="sites-scroll" data-role="lakes-root"></div>
    </section>
    <section class="sites-view lakestory-view" data-role="lakestory-view" aria-label="Story" hidden>
      <div class="sites-scroll" data-role="lakestory-root"></div>
    </section>
    <section class="sites-view evidence-view" data-role="evidence-view" aria-label="How we know" hidden>
      <div class="evidence-root" data-role="evidence-root"></div>
    </section>
  </main>

  <footer class="foot">
    <p><strong>${MATURITY}.</strong> Not an official warning service: for warnings, use PMD, NDMA, GBDMA and PDMA.</p>
    <details class="foot-credits" data-role="foot-credits" open>
      <summary>Data credits and team</summary>
      <p>Data: NISAR GCOV from NASA, distributed by ASF. Sentinel-2 L2A from Copernicus, via Earth Search. Glacial lake updates from SUPARCO. Team SARcastic Scientists, Islamabad Local Event, NASA Space Apps Challenge 2026.</p>
    </details>
  </footer>
</div>`;

export interface AppHandle {
  destroy(): void;
}

export function mountApp(root: HTMLElement, opts: AppOptions = {}): AppHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => {
    const el = root.querySelector<T>(`[data-role="${role}"]`);
    if (!el) throw new Error(`missing element ${role}`);
    return el;
  };
  const lakes = opts.lakes ?? null;

  q("maturity").textContent = MATURITY;

  // On a phone the credits start folded. Everywhere else they are open.
  const narrow = window.matchMedia?.("(max-width: 760px)");
  const syncFolds = (): void => {
    q<HTMLDetailsElement>("foot-credits").open = !narrow?.matches;
  };
  narrow?.addEventListener?.("change", syncFolds);
  syncFolds();

  // ---- Views ---------------------------------------------------------------------------------------------------
  const lakeView = createLakeWatchView(q("lakes-root"), {
    lakes,
    createChart: opts.createLakeChart,
    createLocator: opts.createLakeLocator,
    onBrief: opts.onLakeBrief,
  });
  const evidenceView = createEvidenceView(q("evidence-root"), { lakes });
  const lakeStory = createLakeStoryView(q("lakestory-root"), {
    lakes,
    onAction: (action, lakeId) => {
      if (action === "evidence") return showView("evidence");
      showView("lakes");
      if (action === "lake" && lakeId) lakeView.select(lakeId);
    },
  });

  const storyPage = renderStoryPage(q("home-root"), lakes, {
    onOpenLakes: () => showView("lakes"),
    onOpenEvidence: () => showView("evidence"),
    requests: opts.requests,
    onFollowStory: () => {
      lakeStory.go(0);
      showView("story");
    },
  });

  const sections: Record<View, HTMLElement> = {
    home: q("home-root"),
    lakes: q("lakes-view"),
    story: q("lakestory-view"),
    evidence: q("evidence-view"),
  };
  const viewButtons: Record<Exclude<View, "story">, HTMLButtonElement> = {
    home: q("view-home"),
    lakes: q("view-lakes"),
    evidence: q("view-evidence"),
  };

  function showView(next: View, scroll = true): void {
    q("shell").dataset.view = next;
    for (const [name, el] of Object.entries(sections)) el.hidden = name !== next;
    // The walkthrough is part of the story, so the nav keeps "The story" lit there.
    for (const [name, btn] of Object.entries(viewButtons)) btn.setAttribute("aria-pressed", String(name === next || (name === "home" && next === "story")));
    if (scroll) window.scrollTo?.(0, 0);
    q("view-name").textContent = VIEW_NAMES[next];
    document.title = next === "home" ? "SARtale" : `SARtale · ${VIEW_NAMES[next]}`;
  }

  root.addEventListener("click", (e) => {
    // The Lake Watch headline links to the cloud gap, which is the first beat of the story.
    if ((e.target as Element).closest?.('a[href="#cloud-gap"]')) {
      e.preventDefault();
      lakeStory.go(0);
      showView("story");
    }
  });
  q("home").addEventListener("click", () => showView("home"));
  for (const [name, btn] of Object.entries(viewButtons)) btn.addEventListener("click", () => showView(name as View));

  showView(HASH_VIEWS[window.location.hash] ?? "home", false);

  return {
    destroy: () => {
      narrow?.removeEventListener?.("change", syncFolds);
      storyPage.destroy();
      lakeStory.destroy();
      lakeView.destroy();
      evidenceView.destroy();
      root.innerHTML = "";
    },
  };
}
