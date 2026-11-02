import { heroCopy, storyBeats, type StoryStep } from "./content";
import { createEvidenceView } from "./evidenceView";
import { setChangeOverlay, setComposite, setFrame, setStepOverlay, type MapLike } from "./map";
import { createMissedView } from "./missedView";
import type { LakesFile } from "./lakes";
import { createLakeWatchView, type LakeChartFactory, type LocatorFactory } from "./lakeWatchView";
import type { Preloader } from "./preload";
import { createSitesView, type ChartFactory } from "./sitesView";
import { createStoryPanel } from "./storyPanel";
import { buildAxis, mountAxis } from "./timeAxis";
import { changeExclusion, dataUrl, flagFor, formatDate, frameUrl, maturityBanner, orderedDates } from "./timeline";
import type { Manifest, Pol, Site } from "./types";

/** Where to point the map: the whole study area, or a centre and zoom. */
export type Camera = { fit: true } | { home: true } | { center: [number, number]; zoom: number };
/** Pixels of the map hidden under floating panels, so the target is drawn clear of them. */
export interface Padding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/** What the app needs from the two stacked maps (the "after" map underneath, the "before" map clipped on top). */
export interface MapHost {
  after: MapLike;
  before: MapLike;
  /** Optional: put a tappable marker on the map for each site. */
  setSiteMarkers?(sites: Site[], onSelect: (id: string) => void): void;
  /** Optional: move the camera, easing unless the person prefers reduced motion. */
  moveTo?(camera: Camera, padding: Padding): void;
}

export interface AppOptions {
  /** Site curves from data/sites.json, or null/undefined when the file is absent. */
  sites?: Site[] | null;
  /** Lake data from data/lakes.json, or null/undefined when the file is absent or unusable. */
  lakes?: LakesFile | null;
  createChart?: ChartFactory;
  /** Area-by-track chart for Lake Watch. */
  createLakeChart?: LakeChartFactory;
  /** Small map that marks the lakes. */
  createLakeLocator?: LocatorFactory;
  /** Called by "Print lake brief". */
  onLakeBrief?: (lake: import("./lakes").Lake) => void;
  /** Fetches frames in the background so stepping through dates does not stall. Absent in tests. */
  preload?: Preloader;
}

export type HostFactory = (afterEl: HTMLElement, beforeEl: HTMLElement) => MapHost;

type View = "home" | "lakes" | "dance" | "sites" | "missed" | "evidence";

const PLAY_STEP_MS = 800;
/** How long play waits for the next frame before it goes on without it. */
const PLAY_WAIT_MS = 4000;
const STEP_CAPTION =
  "One map for the whole season. Each coloured patch stepped between two passes, and its colour is the date of the first pass after the step. Light tints went brighter, deep shades went darker. This is a statistical flag, not proof of what changed.";
const CHANGE_CAPTION =
  "Highlighted pixels differ unusually from this area's own season. This is a statistical flag, not proof of what changed.";
const CHANGE_LIMIT =
  "A change that lasts most of the season becomes the area's usual state, so the dates before it can be the ones highlighted.";
const STEP_LIMIT =
  "The rule was set with the known sites in view, so this is not a blind test. Its false-alarm budget is about 1%, on control ground and on shuffled dates. Plain ground flags too, with no known cause, and a step names no cause.";

const TEMPLATE = `
<div class="shell" data-role="shell">
  <a class="skip" href="#main">Skip to the content</a>
  <header class="top">
    <button type="button" class="logo-btn" data-role="home" aria-label="SARtale: back to the start">
      <span class="logo-panel"><img class="logo" src="brand/logo-256.png" width="56" height="56" alt="SARtale Pakistan logo" /></span>
    </button>
    <h1 class="sr-only">SARtale: one monsoon season over the Peshawar Valley, in NISAR radar</h1>
    <p class="sr-only" data-role="view-name" aria-live="polite">Start</p>
    <p class="lede" data-role="lede">Step through the season's radar images. Brighter areas sent more of the signal back.</p>
    <nav class="views" aria-label="Views">
      <button type="button" class="btn view-btn" data-role="view-lakes" aria-pressed="false">Lake Watch</button>
      <button type="button" class="btn view-btn" data-role="view-dance" aria-pressed="false">The Dance</button>
      <button type="button" class="btn view-btn" data-role="view-sites" aria-pressed="false">Site Stories</button>
      <button type="button" class="btn view-btn" data-role="view-missed" aria-pressed="false">What NISAR Missed</button>
      <button type="button" class="btn view-btn" data-role="view-evidence" aria-pressed="false">How we know</button>
    </nav>
    <button type="button" class="btn story-btn" data-role="story-start" aria-pressed="false">Start the story</button>
  </header>

  <main class="workspace" id="main" tabindex="-1">
    <section class="hero" data-role="hero" aria-labelledby="hero-title">
      <img class="hero-img" data-role="hero-img" src="brand/hero-radar.webp" width="1280" height="704" fetchpriority="high"
           alt="NISAR radar picture of the Peshawar Valley, with the dark Tarbela Reservoir on the right." />
      <div class="hero-shade" aria-hidden="true"></div>
      <div class="hero-copy">
        <p class="hero-badge" data-role="hero-maturity"></p>
        <h2 class="hero-title" id="hero-title" data-role="hero-title"></h2>
        <p class="hero-lede" data-role="hero-lede"></p>
        <aside class="hero-finding" data-role="hero-finding" aria-label="Headline finding" hidden>
          <p data-role="hero-finding-text"></p>
          <p class="hero-source" data-role="hero-finding-source"></p>
        </aside>
        <div class="hero-actions">
          <button type="button" class="btn cta" data-role="hero-start">Start the story</button>
          <button type="button" class="btn cta-ghost" data-role="hero-explore">Explore the map</button>
          <button type="button" class="link-btn" data-role="hero-method">How we know</button>
        </div>
        <figure class="hero-strip" data-role="hero-strip">
          <div class="axis axis-mini" data-role="hero-axis" role="img" aria-label=""><div class="axis-layer" data-role="hero-axis-layer"></div></div>
          <figcaption data-role="hero-strip-caption"></figcaption>
        </figure>
      </div>
      <p class="hero-caption" data-role="hero-caption"></p>
    </section>

    <div class="stage" data-role="stage" role="region" aria-label="Radar map">
      <div class="viewport">
        <div class="map map-after" data-role="after"></div>
        <div class="map map-before" data-role="before" hidden></div>
        <div class="swipe" data-role="swipe" role="slider" tabindex="0" hidden
             aria-label="Before and after divider" aria-orientation="horizontal"
             aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">
          <span class="grip" aria-hidden="true"></span>
        </div>
        <div class="top-bar">
          <p class="maturity" data-role="maturity"></p>
          <div class="toolbar" role="group" aria-label="Map layers">
            <fieldset class="pol" data-role="pol">
              <legend>Polarization</legend>
              <label class="seg seg-hh"><input type="radio" name="pol" value="HH" checked /><span>HH</span></label>
              <label class="seg seg-hv"><input type="radio" name="pol" value="HV" /><span>HV</span></label>
            </fieldset>
            <button type="button" class="btn toggle" data-role="swipe-toggle" aria-pressed="false">Before and after</button>
            <label class="before-pick" data-role="before-pick" hidden>Before
              <select data-role="before-select"></select>
            </label>
            <button type="button" class="btn toggle composite" data-role="composite-toggle" aria-pressed="false">Seasonal composite</button>
            <button type="button" class="btn toggle change" data-role="change-toggle" aria-pressed="false" hidden>Change</button>
          </div>
        </div>
        <div class="side">
          <p class="hint" data-role="hint" hidden></p>
          <section class="change-panel" data-role="change-panel" aria-label="Change map key" hidden>
            <h2 class="change-title" data-role="change-title">When the radar stepped</h2>
            <ul class="step-legend" data-role="step-legend" aria-label="Colour by date of the step" hidden></ul>
            <p class="change-caption" data-role="change-caption"></p>
            <p class="change-limit" data-role="change-limit"></p>
            <details class="change-about" data-role="change-about" open>
              <summary>How to read the colours, and how the map is drawn</summary>
              <p class="change-legend" data-role="change-legend"><span class="change-ramp" data-role="change-ramp" aria-hidden="true"></span><span data-role="change-legend-text"></span></p>
              <details class="change-more" data-role="change-more">
                <summary>How the map is drawn and tested</summary>
                <p data-role="change-detail"></p>
              </details>
            </details>
            <button type="button" class="btn toggle unusual" data-role="unusual-toggle" aria-pressed="false" hidden>Unusual dates</button>
            <p class="change-note" data-role="change-note" hidden></p>
          </section>
          <details class="limits-box" data-role="limits-box">
            <summary>Limits of these pictures</summary>
            <p class="limits" data-role="limits" hidden></p>
          </details>
        </div>
        <aside class="story" data-role="story" aria-label="Guided story" hidden></aside>
        <p class="stamp stamp-before" data-role="stamp-before" hidden></p>
        <p class="stamp stamp-after" data-role="stamp-after"></p>
        <p class="flag flag-before" data-role="flag-before" role="note" hidden></p>
        <p class="flag flag-after" data-role="flag-after" role="note" hidden></p>
        <p class="loading" data-role="loading" role="status" hidden></p>
        <div class="notice" data-role="notice" role="alert" hidden>
          <span data-role="notice-text"></span>
          <button type="button" class="btn small" data-role="retry">Try again</button>
        </div>
      </div>
    </div>

    <section class="sites-view lakes-view" data-role="lakes-view" aria-label="Lake Watch" hidden>
      <p class="maturity" data-role="lakes-maturity"></p>
      <div class="sites-scroll" data-role="lakes-root"></div>
    </section>
    <section class="sites-view" data-role="sites-view" aria-label="Site Stories" hidden>
      <p class="maturity" data-role="sites-maturity"></p>
      <div class="sites-scroll" data-role="sites-root"></div>
    </section>
    <section class="sites-view missed-view" data-role="missed-view" aria-label="What NISAR Missed" hidden>
      <p class="maturity" data-role="missed-maturity"></p>
      <div class="missed-root" data-role="missed-root"></div>
    </section>
    <section class="sites-view evidence-view" data-role="evidence-view" aria-label="How we know" hidden>
      <p class="maturity" data-role="evidence-maturity"></p>
      <div class="evidence-root" data-role="evidence-root"></div>
    </section>

    <section class="dock" data-role="dock" aria-label="Date controls">
      <button type="button" class="btn play" data-role="play">Play</button>
      <div class="timeline">
        <div class="date-row">
          <label class="slider-label" for="date-slider">Date <output class="date-out" data-role="date-out" for="date-slider"></output></label>
          <span class="chip chip-flag" data-role="date-flag" hidden>Flagged date</span>
          <span class="chip chip-out" data-role="date-excluded" hidden>Not in the Change map</span>
          <span class="load-state" data-role="load-state" role="status" hidden></span>
        </div>
        <div class="axis" data-role="axis">
          <div class="axis-layer" data-role="ticks" aria-hidden="true"></div>
          <input id="date-slider" data-role="slider" type="range" min="0" step="1" value="0" />
        </div>
        <ul class="axis-key" data-role="axis-key" aria-label="Key to the date line"></ul>
      </div>
    </section>
  </main>

  <footer class="foot">
    <p><strong data-role="foot-status"></strong> Not an official warning service: for warnings, use PMD, NDMA and PDMA.</p>
    <details class="foot-credits" data-role="foot-credits" open>
      <summary>Data credits and team</summary>
      <p>Data: NISAR GCOV from NASA, distributed by ASF. OPERA DSWx-S1 from NASA. River and reservoir figures from the Flood Forecasting Division (FFD), Pakistan Meteorological Department. Team SARcastic Scientists, Islamabad Local Event, NASA Space Apps Challenge 2026.</p>
    </details>
  </footer>
</div>`;

export interface AppHandle {
  /** Resolves when the map has finished the most recent update. */
  settled(): Promise<void>;
  destroy(): void;
}

/** The limits line for calibrated data: what it is, the two pixel sizes and the grey scale every date shares. */
function calibratedLimits(m: Manifest, label: string): string {
  const stretch = (["HH", "HV"] as const)
    .filter((pol) => m.stretch_db?.[pol])
    .map((pol) => `${pol} ${m.stretch_db![pol][0].toFixed(1)} to ${m.stretch_db![pol][1].toFixed(1)} dB`)
    .join(", ");
  return (
    `Limits: ${label}, RTC gamma-0 backscatter, not validated. ` +
    (m.analysis_m ? `Measurements use ${m.analysis_m} m pixels. ` : "") +
    (m.pixel_m ? `These pictures are drawn at about ${m.pixel_m} m. ` : "") +
    (stretch ? `Black to white is ${stretch}, the same on every date. ` : "") +
    "A change in brightness is a change in backscatter, not proof of what changed on the ground."
  );
}

export function mountApp(root: HTMLElement, m: Manifest, createHost: HostFactory, opts: AppOptions = {}): AppHandle {
  root.innerHTML = TEMPLATE;
  const q = <T extends HTMLElement>(role: string): T => {
    const el = root.querySelector<T>(`[data-role="${role}"]`);
    if (!el) throw new Error(`missing element ${role}`);
    return el;
  };

  const dates = orderedDates(m);
  const last = dates.length - 1;
  const stageEl = q("stage");
  const afterEl = q("after");
  const beforeEl = q("before");
  const swipeEl = q("swipe");
  const maturityEl = q("maturity");
  const stampBefore = q("stamp-before");
  const stampAfter = q("stamp-after");
  const noticeEl = q("notice");
  const noticeText = q("notice-text");
  const retryBtn = q<HTMLButtonElement>("retry");
  const loadingEl = q("loading");
  const playBtn = q<HTMLButtonElement>("play");
  const slider = q<HTMLInputElement>("slider");
  const dateOut = q("date-out");
  const dateFlag = q("date-flag");
  const dateExcluded = q("date-excluded");
  const loadState = q("load-state");
  const axisEl = q("axis");
  const polSet = q<HTMLFieldSetElement>("pol");
  const swipeToggle = q<HTMLButtonElement>("swipe-toggle");
  const beforePick = q("before-pick");
  const beforeSelect = q<HTMLSelectElement>("before-select");
  const compositeToggle = q<HTMLButtonElement>("composite-toggle");
  const changeToggle = q<HTMLButtonElement>("change-toggle");
  const changePanel = q("change-panel");
  const changeNote = q("change-note");
  const changeCaption = q("change-caption");
  const changeLimit = q("change-limit");
  const changeDetail = q("change-detail");
  const changeRamp = q("change-ramp");
  const legendText = q("change-legend-text");
  const stepLegend = q("step-legend");
  const unusualToggle = q<HTMLButtonElement>("unusual-toggle");
  const hint = q("hint");
  const limitsEl = q("limits");
  const flagBefore = q("flag-before");
  const flagAfter = q("flag-after");
  const dockEl = q("dock");
  const heroEl = q("hero");
  const storyEl = q("story");
  const storyStart = q<HTMLButtonElement>("story-start");
  const lakesViewEl = q("lakes-view");
  const lakesMaturity = q("lakes-maturity");
  const sitesViewEl = q("sites-view");
  const sitesMaturity = q("sites-maturity");
  const missedViewEl = q("missed-view");
  const missedMaturity = q("missed-maturity");
  const evidenceViewEl = q("evidence-view");
  const evidenceMaturity = q("evidence-maturity");
  const viewName = q("view-name");
  const ledeEl = q("lede");
  const viewButtons: Record<Exclude<View, "home">, HTMLButtonElement> = {
    lakes: q("view-lakes"),
    dance: q("view-dance"),
    sites: q("view-sites"),
    missed: q("view-missed"),
    evidence: q("view-evidence"),
  };

  // Maturity label: always visible. Set before the map is created, so it is on the page even if the map cannot start
  // (for example when WebGL is unavailable).
  const banner = maturityBanner(m);
  for (const el of [maturityEl, lakesMaturity, sitesMaturity, missedMaturity, evidenceMaturity]) {
    el.textContent = banner.text;
    el.dataset.kind = banner.kind;
  }
  q("foot-status").textContent = banner.kind === "provisional" ? `${banner.text}.` : banner.text;

  const host = createHost(afterEl, beforeEl);

  // On a phone the longer notes start folded, so the map keeps its room. Everywhere else they are open.
  const narrow = window.matchMedia?.("(max-width: 760px)");
  const syncFolds = (): void => {
    q<HTMLDetailsElement>("foot-credits").open = !narrow?.matches;
    q<HTMLDetailsElement>("change-about").open = !narrow?.matches;
  };
  narrow?.addEventListener?.("change", syncFolds);
  syncFolds();

  const state = { i: 0, beforeI: 0, pol: "HH" as Pol, composite: false, swipe: false, change: false, unusual: !m.change?.step, fraction: 0.5, playing: false };
  const story = { active: false, resume: -1 };
  let view: View = "home";
  let seq = 0;
  let pending: Promise<void> = Promise.resolve();
  let timer: ReturnType<typeof setTimeout> | undefined;

  const maturityTag = { synthetic: "synthetic demo", preview: "real NISAR preview", provisional: "provisional data" }[banner.kind];
  const isPreview = banner.kind === "preview";
  // Limits of the images, shown on The Dance. Not shown for synthetic data.
  limitsEl.hidden = banner.kind === "synthetic";
  q("limits-box").hidden = banner.kind === "synthetic";
  if (banner.kind === "provisional") limitsEl.textContent = calibratedLimits(m, banner.text);
  if (isPreview) {
    ledeEl.textContent = "Step through the season's radar images. The images are scaled for display, so their brightness is not a measurement.";
    const size = m.pixel_m ? `about ${m.pixel_m} m` : "coarse";
    limitsEl.textContent =
      `Limits: each preview pixel covers ${size} and its brightness is scaled for display, so brightness cannot be compared as a measurement. ` +
      "Placement uses the published footprint and is good to roughly 2 km.";
  }

  // ---- The opening screen --------------------------------------------------------------------------------------
  const provisional = banner.kind === "provisional";
  const siteIds = new Set((opts.sites ?? []).map((s) => s.id));
  q("hero-maturity").textContent = banner.text;
  q("hero-maturity").dataset.kind = banner.kind;
  heroEl.dataset.kind = banner.kind;
  q("hero-title").textContent = provisional ? heroCopy.title : "The Peshawar Valley through one monsoon season";
  q("hero-lede").textContent = provisional
    ? heroCopy.lede
    : isPreview
      ? "Step through NASA's NISAR browse images of the valley. They are low-resolution previews scaled for display, not calibrated measurements."
      : "A synthetic demonstration of the app. It is not NISAR data.";
  // The picture is the real calibrated composite, so it appears only for calibrated data. The finding needs the
  // build it was written from: its sites and its step map.
  const showFinding = provisional && !!m.change?.step && siteIds.has("tarbela-shore");
  q<HTMLImageElement>("hero-img").hidden = !provisional;
  q("hero-finding").hidden = !showFinding;
  if (showFinding) {
    q("hero-finding-text").textContent = heroCopy.finding;
    q("hero-finding-source").textContent = heroCopy.findingSource;
  }
  const [cr, cg, cb] = (m.composite_dates ?? []).map(formatDate);
  q("hero-caption").hidden = !provisional;
  q("hero-caption").textContent =
    cr && cg && cb
      ? `NISAR HH on ${cr}, ${cg} and ${cb}, drawn as red, green and blue. Provisional data.`
      : "NISAR HH seasonal composite. Provisional data.";
  const axisModel = buildAxis(m);
  const heroAxis = mountAxis(q("hero-axis"), q("hero-axis-layer"), axisModel, { onPick() {}, disabled: () => true });
  {
    const gapText = axisModel.gap ? ` The hatched band is the gap in NISAR's record, ${axisModel.gap.label.replace("No data ", "")}.` : "";
    const caption = `${dates.length} passes, ${formatDate(dates[0])} to ${formatDate(dates[last])}.${gapText}`;
    q("hero-strip-caption").textContent = caption;
    q("hero-axis").setAttribute("aria-label", caption);
  }
  // The story is calibrated data's guided tour; it uses the step map and the sites of that build.
  const storyEnabled = provisional && storyBeats.length > 0;
  for (const id of ["hero-start", "story-start"]) q(id).hidden = !storyEnabled;

  // ---- Views ---------------------------------------------------------------------------------------------------
  const sitesView = createSitesView(q("sites-root"), {
    sites: opts.sites ?? null,
    manifest: m,
    createChart: opts.createChart,
    onShowDate: (date, site) => showOnMap(date, site),
  });
  const lakeView = createLakeWatchView(q("lakes-root"), {
    lakes: opts.lakes ?? null,
    createChart: opts.createLakeChart,
    createLocator: opts.createLakeLocator,
    onBrief: opts.onLakeBrief,
  });
  const missedView = createMissedView(q("missed-root"), { manifest: m });
  const evidenceView = createEvidenceView(q("evidence-root"), { manifest: m, sites: opts.sites ?? null });

  function showView(next: View): void {
    view = next;
    q("shell").dataset.view = next;
    const danceOn = next === "dance";
    const home = next === "home";
    if (!danceOn) stopPlaying();
    // The map stays mounted behind the opening screen so its first frame is loading while the person reads.
    stageEl.hidden = !(danceOn || home);
    stageEl.toggleAttribute("inert", home);
    dockEl.hidden = !danceOn;
    ledeEl.hidden = !danceOn;
    heroEl.hidden = !home;
    lakesViewEl.hidden = next !== "lakes";
    sitesViewEl.hidden = next !== "sites";
    missedViewEl.hidden = next !== "missed";
    evidenceViewEl.hidden = next !== "evidence";
    for (const [name, btn] of Object.entries(viewButtons)) btn.setAttribute("aria-pressed", String(name === next));
    const name = { home: "Start", lakes: "Lake Watch", dance: "The Dance", sites: "Site Stories", missed: "What NISAR Missed", evidence: "How we know" }[next];
    viewName.textContent = name;
    document.title = `SARtale: ${name} (${maturityTag})`;
    updateStoryChrome();
  }
  q("home").addEventListener("click", () => showView("home"));
  viewButtons.lakes.addEventListener("click", () => showView("lakes"));
  viewButtons.dance.addEventListener("click", () => showView("dance"));
  viewButtons.sites.addEventListener("click", () => showView("sites"));
  viewButtons.missed.addEventListener("click", () => showView("missed"));
  viewButtons.evidence.addEventListener("click", () => showView("evidence"));
  q("hero-explore").addEventListener("click", () => showView("dance"));
  q("hero-method").addEventListener("click", () => showView("evidence"));

  // ---- The date line -------------------------------------------------------------------------------------------
  slider.max = String(last);
  const axis = mountAxis(axisEl, q("ticks"), axisModel, {
    onPick: (i) => {
      if (i === state.i) return;
      stopPlaying();
      state.i = i;
      void refresh();
    },
    disabled: () => state.composite || dates.length < 2,
  });
  beforeSelect.innerHTML = dates.map((d, i) => `<option value="${i}">${formatDate(d)}</option>`).join("");
  {
    const key = q("axis-key");
    const item = (cls: string, text: string): HTMLLIElement => {
      const li = document.createElement("li");
      const sw = document.createElement("span");
      sw.className = `key-mark ${cls}`;
      sw.setAttribute("aria-hidden", "true");
      li.append(sw, document.createTextNode(text));
      return li;
    };
    key.append(item("km-pass", "NISAR pass"));
    if (dates.some((d) => flagFor(m, d))) key.append(item("km-flag", "Flagged date"));
    if (axisModel.gap) key.append(item("km-gap", axisModel.gap.label));
    if (m.change) key.append(item("km-out", "Left out of the Change map"));
  }
  compositeToggle.hidden = !m.composite;
  changeToggle.hidden = !m.change;
  unusualToggle.hidden = !m.change?.step;

  const stepClasses = m.change?.step?.classes ?? [];
  const dayMonth = (iso: string): string => formatDate(iso).split(" ").slice(0, 2).join(" ");
  if (m.change?.step) {
    const head = document.createElement("li");
    head.className = "legend-head";
    head.setAttribute("aria-hidden", "true");
    head.append(...["Step date", "Brighter", "Darker"].map((t) => Object.assign(document.createElement("span"), { textContent: t })));
    stepLegend.append(head);
    for (const c of stepClasses) {
      const li = document.createElement("li");
      li.dataset.date = c.date;
      const label = document.createElement("span");
      label.className = "legend-date";
      label.textContent = dayMonth(c.date);
      const swatch = (rgb: number[], what: string): HTMLSpanElement => {
        const s = document.createElement("span");
        s.className = "swatch";
        s.style.background = `rgb(${rgb.join(" ")})`;
        s.title = `${what} after, around ${dayMonth(c.date)}`;
        const t = document.createElement("span");
        t.className = "sr-only";
        t.textContent = `${what} after`;
        s.append(t);
        return s;
      };
      li.append(label, swatch(c.up, "Brighter"), swatch(c.down, "Darker"));
      // Pointing at a legend row lights its date on the date line, which is the link between a colour and a date.
      li.addEventListener("pointerenter", () => axis.highlight(c.date));
      li.addEventListener("pointerleave", () => axis.highlight(null));
      stepLegend.append(li);
    }
  }
  const stepColours: Record<string, string> = Object.fromEntries(stepClasses.map((c) => [c.date, `rgb(${c.down.join(" ")})`]));

  /** The words of the change panel for the view that is on. */
  function changeWords(): void {
    const c = m.change;
    if (!c) return;
    const step = state.unusual ? undefined : c.step;
    q("change-title").textContent = step ? "When the radar stepped" : "Unusual dates";
    changeCaption.textContent = step ? STEP_CAPTION : CHANGE_CAPTION;
    stepLegend.hidden = !step;
    changeRamp.hidden = !!step;
    legendText.textContent = step
      ? "No colour means no step passed the test. The date slider changes the radar underneath, not these colours."
      : `Yellow is a score of ${c.threshold}, red is ${c.scale_max} or more, on one scale for every date. ` +
        `The score counts how many of its usual swings a pixel sits from its usual value, in HH or HV. Below ${c.threshold} shows nothing.`;
    changeLimit.textContent = step ? STEP_LIMIT : CHANGE_LIMIT;
    const drawn = step ? step.pixel_m * 3 : 0;
    changeDetail.textContent = step
      ? `HH and HV must move the same way by at least ${step.min_step_db} dB on average, and the dates on each side of the step must agree (stability of at least ${step.min_stability.toFixed(1)}). ` +
        `One step is shown per place, so a second step there is not drawn. ` +
        `The map is drawn at ${drawn} m and analysed at ${step.pixel_m} m: a ${drawn} m cell is drawn only if at least 2 of its 9 pixels are flagged, ` +
        `so small patches look wider than measured, and about 31% of flagged pixels fall in cells that are not drawn. ` +
        `The controls were used in setting the limit, and an independent reviewer found that five fresh cities also stayed quiet (0% flagged within 450 m). ` +
        `The step test and its numbers are on the How we know page.`
      : CHANGE_LIMIT;
    q("change-more").hidden = !step;
    for (const li of stepLegend.querySelectorAll<HTMLElement>("li[data-date]")) {
      li.classList.toggle("current", li.dataset.date === dates[state.i]);
    }
  }
  if (dates.length < 2) {
    slider.disabled = true;
    playBtn.disabled = true;
    swipeToggle.disabled = true;
  }

  function showNotice(message: string | null): void {
    noticeEl.hidden = message === null;
    noticeText.textContent = message ?? "";
  }

  function compositeHint(): string {
    const off = "Switch the composite off to use the date controls.";
    const [r, g, b] = (m.composite_dates ?? []).map(formatDate);
    const which = r && g && b ? `red is ${r}, green is ${g}, blue is ${b} (HH)` : "red for early dates, green for the middle, blue for late (HH)";
    if (isPreview) {
      return `Composite colours: ${which}. Colour differences may come from display scaling, so they are not a measurement and not proven physical change. ${off}`;
    }
    return `Composite colours: ${which}. Colour shows a difference in backscatter, not proven physical change. ${off}`;
  }

  /** The cautions of any flagged date behind the composite, each with its date. */
  function compositeFlags(): string | undefined {
    const notes = (m.composite_dates ?? []).flatMap((d) => {
      const flag = flagFor(m, d);
      return flag ? [`${formatDate(d)}: ${flag}`] : [];
    });
    return notes.length ? notes.join(" ") : undefined;
  }

  /** What the change panel says about the current date beyond the fixed caption, or undefined. */
  function changeDateNote(): string | undefined {
    const date = dates[state.i];
    const reason = changeExclusion(m, date);
    if (reason) return `Excluded from change analysis. ${reason}`;
    return m.change?.date_notes?.[date];
  }

  function updateLabels(): void {
    dateOut.textContent = formatDate(dates[state.i]);
    slider.setAttribute("aria-valuetext", formatDate(dates[state.i]));
    slider.value = String(state.i);
    axis.select(state.i);
    for (const r of polSet.querySelectorAll<HTMLInputElement>('input[name="pol"]')) r.checked = r.value === state.pol;
    const polText = state.composite ? "HH seasonal composite" : state.pol;
    stampAfter.textContent = state.composite ? polText : `${formatDate(dates[state.i])}, ${state.pol}`;
    stampBefore.textContent = `${formatDate(dates[state.beforeI])}, ${state.pol}`;
    stampBefore.hidden = !(state.swipe && !state.composite);
    const flagA = state.composite ? compositeFlags() : flagFor(m, dates[state.i]);
    flagAfter.textContent = flagA ?? "";
    flagAfter.hidden = !flagA;
    const flagB = state.swipe && !state.composite ? flagFor(m, dates[state.beforeI]) : undefined;
    flagBefore.textContent = flagB ?? "";
    flagBefore.hidden = !flagB;
    const caution = [flagA ? (state.composite ? flagA : `${formatDate(dates[state.i])}: ${flagA}`) : "", flagB ? `${formatDate(dates[state.beforeI])}: ${flagB}` : ""].filter(Boolean).join(" ");
    const cautionEl = root.querySelector<HTMLElement>('[data-role="story-caution"]');
    if (cautionEl) {
      cautionEl.textContent = caution;
      cautionEl.hidden = !caution;
    }
    dateFlag.hidden = state.composite || !flagFor(m, dates[state.i]);
    const changeOn = state.change && !state.composite;
    dateExcluded.hidden = !(changeOn && changeExclusion(m, dates[state.i]));
    playBtn.textContent = state.playing ? "Pause" : "Play";
    playBtn.setAttribute("aria-pressed", String(state.playing));
    swipeToggle.setAttribute("aria-pressed", String(state.swipe));
    compositeToggle.setAttribute("aria-pressed", String(state.composite));
    changeToggle.setAttribute("aria-pressed", String(state.change));
    changeToggle.disabled = state.composite;
    changePanel.hidden = !changeOn;
    const note = changeDateNote();
    changeNote.textContent = note ?? "";
    changeNote.hidden = !note;
    unusualToggle.setAttribute("aria-pressed", String(state.unusual));
    changeWords();
    axis.tint(changeOn && !state.unusual && m.change?.step ? stepColours : null);
    axis.showExcluded(!!changeOn);
    beforeEl.hidden = !(state.swipe && !state.composite);
    swipeEl.hidden = beforeEl.hidden;
    beforePick.hidden = !state.swipe || state.composite;
    beforeSelect.value = String(state.beforeI);
    const locked = state.composite;
    slider.disabled = locked || dates.length < 2;
    playBtn.disabled = locked || dates.length < 2;
    swipeToggle.disabled = locked || dates.length < 2;
    polSet.disabled = locked;
    axisEl.classList.toggle("locked", locked);
    hint.hidden = !locked;
    hint.textContent = locked ? compositeHint() : "";
    stageEl.style.setProperty("--swipe", `${state.fraction * 100}%`);
    beforeEl.style.clipPath = `inset(0 ${100 - state.fraction * 100}% 0 0)`;
    swipeEl.setAttribute("aria-valuenow", String(Math.round(state.fraction * 100)));
  }

  // ---- Frames: loading state and background preloading ---------------------------------------------------------
  const preload = opts.preload;
  const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData === true;
  /** The frame URL for a date, or undefined where the manifest has none (never throws). */
  function urlOf(i: number, pol: Pol = state.pol): string | undefined {
    try {
      return frameUrl(m, dates[i], pol);
    } catch {
      return undefined;
    }
  }
  /** Ask for every frame of a polarization, nearest the current date first. */
  function warm(pol: Pol): void {
    if (!preload || saveData) return;
    const order = dates.map((_, i) => i).sort((a, b) => Math.abs(a - state.i) - Math.abs(b - state.i));
    preload.request(order.flatMap((i) => urlOf(i, pol) ?? []));
    if (m.change?.step && state.change) preload.request([dataUrl(m.change.step.frame)]);
  }
  const stopWatching = preload?.onChange(() => {
    const p = preload.progress();
    const left = p.total - p.done - p.failed;
    loadState.hidden = left <= 0;
    loadState.textContent = left > 0 ? `Preparing frames: ${p.done} of ${p.total}` : "";
  });
  let loadingTimer: ReturnType<typeof setTimeout> | undefined;
  function showLoading(text: string): void {
    clearTimeout(loadingTimer);
    // Quick loads stay silent; a slow one says what it is waiting for.
    loadingTimer = setTimeout(() => {
      loadingEl.textContent = text;
      loadingEl.hidden = false;
    }, 160);
  }
  function hideLoading(): void {
    clearTimeout(loadingTimer);
    loadingEl.hidden = true;
  }

  /** Draw whatever the state says. Newer calls supersede older ones; only the newest reports errors. */
  function refresh(): Promise<void> {
    const mine = ++seq;
    updateLabels();
    const jobs: Promise<void>[] = [
      state.composite ? setComposite(host.after, m) : setFrame(host.after, m, dates[state.i], state.pol),
    ];
    if (state.swipe && !state.composite) jobs.push(setFrame(host.before, m, dates[state.beforeI], state.pol));
    if (m.change) {
      const on = state.change && !state.composite;
      jobs.push(on && !state.unusual ? setStepOverlay(host.after, m) : setChangeOverlay(host.after, m, on ? dates[state.i] : null));
    }
    showLoading(state.composite ? "Loading the seasonal composite" : `Loading ${formatDate(dates[state.i])}, ${state.pol}`);
    pending = Promise.all(jobs).then(
      () => {
        if (mine === seq) showNotice(null);
      },
      (err: unknown) => {
        if (mine !== seq) return;
        stopPlaying();
        stampAfter.textContent += " (not loaded)";
        showNotice(err instanceof Error ? err.message : String(err));
      },
    );
    void pending.finally(() => {
      if (mine === seq) hideLoading();
    });
    return pending;
  }

  function stopPlaying(): void {
    state.playing = false;
    if (timer) clearTimeout(timer);
    timer = undefined;
    updateLabels();
  }

  async function tick(): Promise<void> {
    if (!state.playing) return;
    if (state.i >= last) return stopPlaying();
    const next = state.i + 1;
    const url = urlOf(next);
    if (preload && url) {
      // Wait for the next frame to be on hand, so the step is clean instead of a blank flash. Never wait for long.
      showLoading(`Loading ${formatDate(dates[next])}, ${state.pol}`);
      await Promise.race([preload.whenReady(url).catch(() => {}), new Promise((r) => setTimeout(r, PLAY_WAIT_MS))]);
      hideLoading();
      if (!state.playing) return;
    }
    state.i = next;
    await refresh();
    if (!state.playing) return;
    // Ask for the frame after this one now, while this one is on screen.
    const ahead = urlOf(state.i + 1);
    if (preload && ahead) preload.prioritize(ahead);
    timer = setTimeout(() => void tick(), PLAY_STEP_MS);
  }

  function startPlaying(): void {
    if (state.i >= last) state.i = 0;
    state.playing = true;
    updateLabels();
    void tick();
  }

  slider.addEventListener("input", () => {
    state.i = Number(slider.value);
    void refresh();
  });
  playBtn.addEventListener("click", () => (state.playing ? stopPlaying() : startPlaying()));
  polSet.addEventListener("change", (e) => {
    const t = e.target as HTMLInputElement;
    if (t.name === "pol") {
      state.pol = t.value as Pol;
      warm(state.pol);
      void refresh();
    }
  });
  swipeToggle.addEventListener("click", () => {
    state.swipe = !state.swipe;
    void refresh();
  });
  beforeSelect.addEventListener("change", () => {
    state.beforeI = Number(beforeSelect.value);
    void refresh();
  });
  compositeToggle.addEventListener("click", () => {
    state.composite = !state.composite;
    if (state.composite) {
      stopPlaying();
      if (preload && m.composite) preload.prioritize(dataUrl(m.composite));
    }
    void refresh();
  });
  changeToggle.addEventListener("click", () => {
    state.change = !state.change;
    if (state.change && preload && m.change?.step && !state.unusual) preload.prioritize(dataUrl(m.change.step.frame));
    void refresh();
  });
  unusualToggle.addEventListener("click", () => {
    state.unusual = !state.unusual;
    void refresh();
  });
  retryBtn.addEventListener("click", () => void refresh());

  // Swipe divider: drag with pointer or move with the keyboard.
  function setFraction(f: number): void {
    state.fraction = Math.min(1, Math.max(0, f));
    updateLabels();
  }
  swipeEl.addEventListener("pointerdown", (e) => {
    swipeEl.setPointerCapture(e.pointerId);
    swipeEl.classList.add("dragging");
  });
  swipeEl.addEventListener("pointermove", (e) => {
    if (!swipeEl.hasPointerCapture(e.pointerId)) return;
    const r = stageEl.getBoundingClientRect();
    if (r.width > 0) setFraction((e.clientX - r.left) / r.width);
  });
  const endDrag = (): void => swipeEl.classList.remove("dragging");
  swipeEl.addEventListener("pointerup", endDrag);
  swipeEl.addEventListener("pointercancel", endDrag);
  swipeEl.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 0.2 : 0.05;
    const next: Record<string, number> = {
      ArrowLeft: state.fraction - step,
      ArrowDown: state.fraction - step,
      ArrowRight: state.fraction + step,
      ArrowUp: state.fraction + step,
      Home: 0,
      End: 1,
    };
    if (e.key in next) {
      e.preventDefault();
      setFraction(next[e.key]);
    }
  });

  // ---- The guided story ----------------------------------------------------------------------------------------
  /** The index of a date in the built dates, or the nearest earlier one, or 0. */
  function dateIndex(date: string | undefined): number {
    if (!date) return 0;
    const exact = dates.indexOf(date);
    if (exact >= 0) return exact;
    return Math.max(0, dates.filter((d) => d <= date).length - 1);
  }

  /** How much of the map the floating panels hide, so a camera move leaves its target in the clear. */
  function cameraPadding(): Padding {
    const pad = { top: 0, right: 0, bottom: 0, left: 0 };
    const stage = stageEl.getBoundingClientRect();
    const topBar = root.querySelector<HTMLElement>(".top-bar");
    if (topBar) pad.top = topBar.offsetHeight;
    if (story.active && !storyEl.hidden && stage.width > 0) {
      const r = storyEl.getBoundingClientRect();
      if (r.width > stage.width * 0.8) pad.bottom = r.height + 8;
      else pad.left = r.width + 20;
    }
    return pad;
  }

  function applyStep(step: StoryStep): void {
    stopPlaying();
    state.composite = false;
    state.i = dateIndex(step.map.date);
    state.pol = step.map.pol;
    state.swipe = !!step.map.swipeBefore;
    if (step.map.swipeBefore) state.beforeI = dateIndex(step.map.swipeBefore);
    state.fraction = 0.5;
    state.change = !!step.map.change && !!m.change?.step;
    state.unusual = !m.change?.step;
    warm(state.pol);
    void refresh();
    host.moveTo?.(step.camera, cameraPadding());
  }

  const storyPanel = createStoryPanel(storyEl, {
    steps: storyBeats,
    manifest: m,
    sites: opts.sites ?? null,
    onGo: (step, index) => {
      story.resume = index;
      applyStep(step);
    },
    onExit: () => exitStory(),
    onOpenSite: (id) => {
      showView("sites");
      sitesView.select(id);
    },
    onPlay: () => {
      state.composite = false;
      startPlaying();
    },
  });

  function updateStoryChrome(): void {
    const total = storyBeats.length;
    storyEl.hidden = !(story.active && view === "dance");
    stageEl.dataset.story = story.active ? "on" : "off";
    storyStart.setAttribute("aria-pressed", String(story.active));
    storyStart.textContent = story.active ? "In the story" : story.resume >= 0 ? "Resume the story" : "Start the story";
    storyStart.title = !story.active && story.resume >= 0 ? `Resume at step ${story.resume + 1} of ${total}` : "";
  }

  function startStory(from = Math.max(0, story.resume)): void {
    if (!storyEnabled) return;
    story.active = true;
    showView("dance");
    storyPanel.go(from);
    q("story-title").focus({ preventScroll: true });
  }

  /** Leave the story to explore freely. The place is kept, so the person can come back to it. */
  function exitStory(): void {
    const finished = storyPanel.index() >= storyPanel.count() - 1;
    const hadFocus = storyEl.contains(document.activeElement);
    const wasFit = "fit" in storyBeats[Math.max(0, storyPanel.index())].camera;
    story.active = false;
    story.resume = finished ? -1 : storyPanel.index();
    if (view !== "dance") showView("dance");
    else updateStoryChrome();
    // The card no longer hides part of the map, so the map takes the whole stage back.
    if (wasFit) host.moveTo?.({ home: true }, { top: 0, right: 0, bottom: 0, left: 0 });
    // Focus goes to the button that brings the story back, so keyboard users are not left on a hidden card.
    if (hadFocus) storyStart.focus();
  }

  storyStart.addEventListener("click", () => {
    if (story.active) showView("dance");
    else startStory();
  });
  q("hero-start").addEventListener("click", () => startStory(0));

  /** Show a date on the map, centred on a site (from a card's chart or table). Leaves the story if it was on. */
  function showOnMap(date: string, site: Site): void {
    if (story.active) {
      story.active = false;
      story.resume = storyPanel.index();
    }
    stopPlaying();
    state.composite = false;
    state.swipe = false;
    state.i = dateIndex(date);
    showView("dance");
    void refresh();
    host.moveTo?.({ center: [site.lon, site.lat], zoom: 10.5 }, cameraPadding());
  }

  void refresh().then(() => warm(state.pol));
  showView("home");

  if (opts.sites?.length) {
    host.setSiteMarkers?.(opts.sites, (id) => {
      showView("sites");
      sitesView.select(id);
    });
  }

  return {
    settled: () => pending,
    destroy: () => {
      stopPlaying();
      narrow?.removeEventListener?.("change", syncFolds);
      stopWatching?.();
      axis.destroy();
      heroAxis.destroy();
      storyPanel.destroy();
      lakeView.destroy();
      sitesView.destroy();
      missedView.destroy();
      evidenceView.destroy();
      root.innerHTML = "";
    },
  };
}
