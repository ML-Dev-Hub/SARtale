import { createEvidenceView } from "./evidenceView";
import type { Lake, LakesFile } from "./lakes";
import { createLakeStoryView } from "./lakeStory";
import { createLakeWatchView, type LakeChartFactory, type LocatorFactory } from "./lakeWatchView";
import type { LakeRequest } from "./lakeRequests";
import { DEFAULT_STATE, overviewQuery, parseOverviewHash, type OverviewState } from "./overview/model";
import { createOverview } from "./overview/overviewView";
import { renderStoryPage } from "./storyPage";

export interface AppOptions {
  /** Lake data from data/lakes.json, or null/undefined when the file is absent or unusable. */
  lakes?: LakesFile | null;
  /** Area-by-track chart for Lake Watch. */
  createLakeChart?: LakeChartFactory;
  /** Small map that marks the lakes (the overview's map drawer takes it over in a later step). */
  createLakeLocator?: LocatorFactory;
  /** Called by "Print lake brief". */
  onLakeBrief?: (lake: Lake) => void;
  /** Lake requests from data/requests.json. */
  requests?: LakeRequest[];
}

type View = "home" | "lakes" | "story" | "evidence" | "share";

const VIEW_NAMES: Record<View, string> = { home: "The story", lakes: "Lake Watch", story: "Story walkthrough", evidence: "How we know", share: "Share" };
/** Hashes that open a view on load, so a view can be linked to or screenshotted directly. */
const HASH_VIEWS: Record<string, View> = { "#lakes": "lakes", "#story": "story", "#evidence": "evidence", "#share": "share" };
const VIEW_HASH: Record<View, string> = { home: "", lakes: "#lakes", story: "#story", evidence: "#evidence", share: "#share" };

/**
 * The view (and lake) a URL hash names: "" or "#" is the start page, "#lakes/attabad" a lake. Any other hash is an
 * in-page anchor (the skip link, a story section) and returns null, so it never changes the view.
 */
export function routeFromHash(hash: string): { view: View; lake?: string; pass?: string; compare?: [string, string]; query?: string } | null {
  if (hash === "" || hash === "#") return { view: "home" };
  if (HASH_VIEWS[hash]) return { view: HASH_VIEWS[hash] };
  const q = /^#lakes\?(.+)$/.exec(hash);
  if (q) return { view: "lakes", query: q[1] };
  const pass = /^#lakes\/([a-z0-9_-]+)\/pass\/([0-9A-Za-z_-]+)$/.exec(hash);
  if (pass) return { view: "lakes", lake: pass[1], pass: pass[2] };
  const cmp = /^#lakes\/([a-z0-9_-]+)\/compare\/([0-9A-Za-z_-]+)\/([0-9A-Za-z_-]+)$/.exec(hash);
  if (cmp) return { view: "lakes", lake: cmp[1], compare: [cmp[2], cmp[3]] };
  const m = /^#lakes\/([a-z0-9_-]+)$/.exec(hash);
  return m ? { view: "lakes", lake: m[1] } : null;
}
/**
 * Passes up to 21 Oct 2026 are NASA's provisional GCOV release (P05023), later ones the standard product (P05036).
 * The label stays while any provisional pass is used, which is every build that keeps the season from June.
 */
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
      <div class="sites-scroll" data-role="overview-root"></div>
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
    <p><strong>${MATURITY}.</strong> Not an official warning service. For warnings, use PMD, NDMA, GBDMA and PDMA.</p>
    <details class="foot-credits" data-role="foot-credits" open>
      <summary>Data credits and team</summary>
      <p>Data: NISAR GCOV from NASA, distributed by ASF. Sentinel-2 L2A from Copernicus, via Earth Search. Glacial lake updates from SUPARCO. Team SARcastic Scientists, Islamabad Local Event, NASA Space Apps Challenge 2026.</p>
    </details>
  </footer>
</div>`;

export interface AppHandle {
  /** Show the lake requests once data/requests.json has loaded (the app starts without waiting for it). */
  setRequests(requests: LakeRequest[]): void;
  destroy(): void;
}

/** The element id a URL fragment names, or null when the fragment is not valid percent-encoding (e.g. "#%"). */
export function fragmentId(hash: string): string | null {
  try {
    return decodeURIComponent(hash.slice(1));
  } catch {
    return null;
  }
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
    onBrief: opts.onLakeBrief,
    onSelect: (id) => setHash(`#lakes/${id}`, true),
  });
  // `#lakes` and `#lakes?<filters>` show the overview; `#lakes/<id>` shows the lake. Without lake data the lake view
  // says so, and there is no overview.
  const overview = lakes && lakes.lakes.length
    ? createOverview(q("overview-root"), {
      file: lakes,
      state: DEFAULT_STATE,
      onState: (s: OverviewState) => {
        const query = overviewQuery(s);
        setHash(query ? `#lakes?${query}` : "#lakes", true);
        overview?.update(s);
      },
      onOpenLake: (id) => {
        setHash(`#lakes/${id}`);
        showLakes({ lake: id });
        window.scrollTo?.(0, 0);
      },
    })
    : null;

  /** Shows the overview, or one lake when the route names a lake in the data. */
  function showLakes(r: { lake?: string; query?: string }): void {
    const lake = r.lake && lakes?.lakes.some((l) => l.id === r.lake) ? r.lake : undefined;
    const onOverview = overview !== null && !lake;
    q("lakes-view").dataset.mode = onOverview ? "overview" : "lake";
    q("overview-root").hidden = !onOverview;
    q("lakes-root").hidden = onOverview;
    if (onOverview) overview!.update(parseOverviewHash(r.query ?? ""));
    else if (lake) lakeView.select(lake);
  }
  const evidenceView = createEvidenceView(q("evidence-root"), { lakes });
  const lakeStory = createLakeStoryView(q("lakestory-root"), {
    lakes,
    onAction: (action, lakeId) => {
      if (action === "evidence") return showView("evidence");
      showView("lakes");
      if (action === "lake" && lakeId) {
        setHash(`#lakes/${lakeId}`, true);
        showLakes({ lake: lakeId });
      }
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

  const sections: Record<Exclude<View, "share">, HTMLElement> = {
    home: q("home-root"),
    lakes: q("lakes-view"),
    story: q("lakestory-view"),
    evidence: q("evidence-view"),
  };
  const viewButtons: Record<Exclude<View, "story" | "share">, HTMLButtonElement> = {
    home: q("view-home"),
    lakes: q("view-lakes"),
    evidence: q("view-evidence"),
  };

  /** Puts a view in the address bar: a new history entry for a view change, a replaced one for a lake pick. */
  function setHash(hash: string, replace = false): void {
    const current = window.location.hash === "#" ? "" : window.location.hash;
    if (current === hash) return;
    const url = hash || window.location.pathname + window.location.search;
    if (replace) window.history?.replaceState?.(null, "", url);
    else window.history?.pushState?.(null, "", url);
  }

  function showView(next: View, scroll = true, push = true): void {
    if (push) {
      const here = routeFromHash(window.location.hash);
      // An in-page anchor (#main, a story section) is replaced, so Back never lands on a hash that names no view.
      if (here?.view !== next) setHash(VIEW_HASH[next], here === null);
    }
    q("shell").dataset.view = next;
    // No share page yet (a later task): #share shows the start page meanwhile.
    const shown = next === "share" ? "home" : next;
    for (const [name, el] of Object.entries(sections)) el.hidden = name !== shown;
    if (next === "lakes") showLakes(routeFromHash(window.location.hash) ?? {});
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
  for (const [name, btn] of Object.entries(viewButtons)) {
    btn.addEventListener("click", () => {
      // Lake Watch in the nav always leads to the overview, also from a lake's own page.
      if (name === "lakes" && routeFromHash(window.location.hash)?.view === "lakes") setHash("#lakes");
      showView(name as View);
    });
  }

  // Back, Forward and a typed or linked hash all change the hash (our pushState entries always differ in it), so
  // hashchange alone covers them; popstate as well would run every move twice.
  const followHash = (): void => {
    const r = routeFromHash(window.location.hash);
    if (!r) return;
    showView(r.view, false, false);
  };
  window.addEventListener("hashchange", followHash);
  const first = routeFromHash(window.location.hash) ?? { view: "home" as View };
  showView(first.view, false, false);
  // A link to a story section, such as #videos, arrives before the page is drawn, so scroll to it now.
  const id = routeFromHash(window.location.hash) ? null : fragmentId(window.location.hash);
  const anchor = id ? document.getElementById(id) : null;
  anchor?.scrollIntoView?.();

  return {
    setRequests: (list) => storyPage.setRequests(list),
    destroy: () => {
      narrow?.removeEventListener?.("change", syncFolds);
      window.removeEventListener("hashchange", followHash);
      storyPage.destroy();
      lakeStory.destroy();
      lakeView.destroy();
      overview?.destroy();
      evidenceView.destroy();
      root.innerHTML = "";
    },
  };
}
