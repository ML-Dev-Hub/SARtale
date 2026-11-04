import { lakeHero } from "./content";
import { createEvidenceView } from "./evidenceView";
import { dataUrl, formatDate } from "./format";
import { cloudHeadline, type Lake, type LakesFile } from "./lakes";
import { createLakeStoryView } from "./lakeStory";
import { createLakeWatchView, type LakeChartFactory, type LocatorFactory } from "./lakeWatchView";

export interface AppOptions {
  /** Lake data from data/lakes.json, or null/undefined when the file is absent or unusable. */
  lakes?: LakesFile | null;
  /** Area-by-track chart for Lake Watch. */
  createLakeChart?: LakeChartFactory;
  /** Small map that marks the lakes. */
  createLakeLocator?: LocatorFactory;
  /** Called by "Print lake brief". */
  onLakeBrief?: (lake: Lake) => void;
}

type View = "home" | "lakes" | "story" | "evidence";

const VIEW_NAMES: Record<View, string> = { home: "Start", lakes: "Lake Watch", story: "Story", evidence: "How we know" };
/** Every NISAR file in this build is NASA's provisional GCOV product, so the label is fixed. */
export const MATURITY = "Provisional NISAR data";

const TEMPLATE = `
<div class="shell" data-role="shell">
  <a class="skip" href="#main">Skip to the content</a>
  <header class="top">
    <button type="button" class="logo-btn" data-role="home" aria-label="SARtale: back to the start">
      <span class="logo-panel"><img class="logo" src="brand/logo-256.png" width="56" height="56" alt="SARtale Pakistan logo" /></span>
    </button>
    <h1 class="sr-only">SARtale Lake Watch: glacial lakes of Gilgit-Baltistan and Khyber Pakhtunkhwa in NISAR radar</h1>
    <p class="sr-only" data-role="view-name" aria-live="polite">Start</p>
    <nav class="views" aria-label="Views">
      <button type="button" class="btn view-btn" data-role="view-lakes" aria-pressed="false">Lake Watch</button>
      <button type="button" class="btn view-btn" data-role="view-story" aria-pressed="false">Story</button>
      <button type="button" class="btn view-btn" data-role="view-evidence" aria-pressed="false">How we know</button>
    </nav>
  </header>

  <main class="workspace" id="main" tabindex="-1">
    <section class="hero hero-lakes" data-role="hero" aria-labelledby="hero-title">
      <img class="hero-img" data-role="hero-img" width="601" height="598" fetchpriority="high" alt="" hidden />
      <div class="hero-shade" aria-hidden="true"></div>
      <div class="hero-copy">
        <p class="hero-badge" data-role="hero-maturity"></p>
        <p class="hero-audience" data-role="hero-audience"></p>
        <h2 class="hero-title" id="hero-title" data-role="hero-title"></h2>
        <p class="hero-lede" data-role="hero-lede"></p>
        <p class="hero-screening" data-role="hero-screening"></p>
        <aside class="hero-finding" data-role="hero-finding" aria-label="Headline finding" hidden>
          <p data-role="hero-finding-text"></p>
          <p class="hero-source" data-role="hero-finding-source"></p>
        </aside>
        <div class="hero-actions">
          <button type="button" class="btn cta" data-role="hero-story">Start the story</button>
          <button type="button" class="btn cta-ghost" data-role="hero-lakes">Open Lake Watch</button>
          <button type="button" class="link-btn" data-role="hero-method">How we know</button>
        </div>
      </div>
      <p class="hero-caption" data-role="hero-caption" hidden></p>
    </section>

    <section class="sites-view lakes-view" data-role="lakes-view" aria-label="Lake Watch" hidden>
      <p class="maturity" data-role="lakes-maturity"></p>
      <div class="sites-scroll" data-role="lakes-root"></div>
    </section>
    <section class="sites-view lakestory-view" data-role="lakestory-view" aria-label="Story" hidden>
      <p class="maturity" data-role="lakestory-maturity"></p>
      <div class="sites-scroll" data-role="lakestory-root"></div>
    </section>
    <section class="sites-view evidence-view" data-role="evidence-view" aria-label="How we know" hidden>
      <p class="maturity" data-role="evidence-maturity"></p>
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

  for (const role of ["hero-maturity", "lakes-maturity", "lakestory-maturity", "evidence-maturity"]) {
    q(role).textContent = MATURITY;
    q(role).dataset.kind = "provisional";
  }

  // On a phone the credits start folded. Everywhere else they are open.
  const narrow = window.matchMedia?.("(max-width: 760px)");
  const syncFolds = (): void => {
    q<HTMLDetailsElement>("foot-credits").open = !narrow?.matches;
  };
  narrow?.addEventListener?.("change", syncFolds);
  syncFolds();

  // ---- The opening screen --------------------------------------------------------------------------------------
  q("hero-audience").textContent = lakeHero.audience;
  q("hero-title").textContent = lakeHero.title;
  q("hero-lede").textContent = lakeHero.lede;
  q("hero-screening").textContent = lakeHero.screening;
  if (lakes?.lakes.length) {
    q("hero-finding").hidden = false;
    q("hero-finding-text").textContent = cloudHeadline(lakes);
    q("hero-finding-source").textContent = lakeHero.headlineSource;
  }
  const attabad = lakes?.lakes.find((l) => l.id === "attabad");
  const hh = attabad?.images?.latest_hh;
  if (attabad && hh) {
    const img = q<HTMLImageElement>("hero-img");
    img.src = dataUrl(hh);
    img.alt = "NISAR HH radar picture of Attabad Lake, Hunza, with the lake dark.";
    img.hidden = false;
    const picDate = attabad.images?.date ?? attabad.status.latest_date; // the pictured pass, not just the newest status date
    q("hero-caption").hidden = false;
    q("hero-caption").textContent = `Attabad Lake, Hunza: NISAR HH radar${picDate ? ` on ${formatDate(picDate)}` : ""}. The lake is the long dark band. Radar-geometry picture, not a map. Provisional data.`;
  }

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

  const sections: Record<Exclude<View, "home">, HTMLElement> = {
    lakes: q("lakes-view"),
    story: q("lakestory-view"),
    evidence: q("evidence-view"),
  };
  const viewButtons: Record<Exclude<View, "home">, HTMLButtonElement> = {
    lakes: q("view-lakes"),
    story: q("view-story"),
    evidence: q("view-evidence"),
  };

  function showView(next: View): void {
    q("shell").dataset.view = next;
    q("hero").hidden = next !== "home";
    for (const [name, el] of Object.entries(sections)) el.hidden = name !== next;
    for (const [name, btn] of Object.entries(viewButtons)) btn.setAttribute("aria-pressed", String(name === next));
    q("view-name").textContent = VIEW_NAMES[next];
    document.title = `SARtale: ${VIEW_NAMES[next]} (provisional data)`;
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
  q("hero-story").addEventListener("click", () => {
    lakeStory.go(0);
    showView("story");
  });
  q("hero-lakes").addEventListener("click", () => showView("lakes"));
  q("hero-method").addEventListener("click", () => showView("evidence"));
  for (const [name, btn] of Object.entries(viewButtons)) btn.addEventListener("click", () => showView(name as View));

  showView("home");

  return {
    destroy: () => {
      narrow?.removeEventListener?.("change", syncFolds);
      lakeStory.destroy();
      lakeView.destroy();
      evidenceView.destroy();
      root.innerHTML = "";
    },
  };
}
