import { setComposite, setFrame, type MapLike } from "./map";
import { createMissedView } from "./missedView";
import { createSitesView, type ChartFactory } from "./sitesView";
import { flagFor, formatDate, maturityBanner, orderedDates } from "./timeline";
import type { Manifest, Pol, Site } from "./types";

/** What the app needs from the two stacked maps (the "after" map underneath, the "before" map clipped on top). */
export interface MapHost {
  after: MapLike;
  before: MapLike;
  /** Optional: put a tappable marker on the map for each site. */
  setSiteMarkers?(sites: Site[], onSelect: (id: string) => void): void;
}

export interface AppOptions {
  /** Site curves from data/sites.json, or null/undefined when the file is absent. */
  sites?: Site[] | null;
  createChart?: ChartFactory;
}

export type HostFactory = (afterEl: HTMLElement, beforeEl: HTMLElement) => MapHost;

const PLAY_STEP_MS = 800;

const TEMPLATE = `
<div class="shell">
  <header class="top">
    <span class="logo-panel"><img class="logo" src="brand/logo-256.png" width="56" height="56" alt="SARtale Pakistan logo" /></span>
    <h1 class="brand">SARtale</h1>
    <p class="view" data-role="view-name" aria-live="polite">The Dance</p>
    <nav class="views" aria-label="Views">
      <button type="button" class="btn view-btn" data-role="view-dance" aria-pressed="true">The Dance</button>
      <button type="button" class="btn view-btn" data-role="view-sites" aria-pressed="false">Site Stories</button>
      <button type="button" class="btn view-btn" data-role="view-missed" aria-pressed="false">What NISAR Missed</button>
    </nav>
    <p class="lede" data-role="lede">Step through the season's radar images. Brighter areas sent more of the signal back.</p>
  </header>
  <main class="stage" data-role="stage" aria-label="Radar map">
    <p class="maturity" data-role="maturity"></p>
    <div class="viewport">
      <div class="map map-after" data-role="after"></div>
      <div class="map map-before" data-role="before" hidden></div>
      <div class="swipe" data-role="swipe" role="slider" tabindex="0" hidden
           aria-label="Before and after divider" aria-orientation="horizontal"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">
        <span class="grip" aria-hidden="true"></span>
      </div>
      <p class="stamp stamp-before" data-role="stamp-before" hidden></p>
      <p class="stamp stamp-after" data-role="stamp-after"></p>
      <p class="flag flag-before" data-role="flag-before" role="note" hidden></p>
      <p class="flag flag-after" data-role="flag-after" role="note" hidden></p>
      <div class="notice" data-role="notice" role="alert" hidden>
        <span data-role="notice-text"></span>
        <button type="button" class="btn small" data-role="retry">Try again</button>
      </div>
    </div>
  </main>
  <section class="sites-view" data-role="sites-view" aria-label="Site Stories" hidden>
    <p class="maturity" data-role="sites-maturity"></p>
    <div class="sites-scroll" data-role="sites-root"></div>
  </section>
  <section class="sites-view missed-view" data-role="missed-view" aria-label="What NISAR Missed" hidden>
    <p class="maturity" data-role="missed-maturity"></p>
    <div class="missed-root" data-role="missed-root"></div>
  </section>
  <section class="dock" data-role="dock" aria-label="Controls">
    <div class="row timeline">
      <button type="button" class="btn play" data-role="play">Play</button>
      <div class="slider-block">
        <label class="slider-label" for="date-slider">
          Date <output class="date-out" data-role="date-out" for="date-slider"></output>
        </label>
        <div class="track">
          <div class="ticks" data-role="ticks" aria-hidden="true"></div>
          <input id="date-slider" data-role="slider" type="range" min="0" step="1" value="0" />
        </div>
        <div class="ends" aria-hidden="true"><span data-role="first"></span><span data-role="last"></span></div>
      </div>
    </div>
    <div class="row options">
      <fieldset class="pol" data-role="pol">
        <legend>Polarization</legend>
        <label class="seg seg-hh"><input type="radio" name="pol" value="HH" checked /><span>HH</span></label>
        <label class="seg seg-hv"><input type="radio" name="pol" value="HV" /><span>HV</span></label>
      </fieldset>
      <div class="compare">
        <button type="button" class="btn toggle" data-role="swipe-toggle" aria-pressed="false">Before and after</button>
        <label class="before-pick" data-role="before-pick" hidden>Before
          <select data-role="before-select"></select>
        </label>
      </div>
      <button type="button" class="btn toggle composite" data-role="composite-toggle" aria-pressed="false">Seasonal composite</button>
    </div>
    <p class="hint" data-role="hint" hidden></p>
    <p class="limits" data-role="limits" hidden></p>
  </section>
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
  const playBtn = q<HTMLButtonElement>("play");
  const slider = q<HTMLInputElement>("slider");
  const dateOut = q("date-out");
  const ticks = q("ticks");
  const polSet = q<HTMLFieldSetElement>("pol");
  const swipeToggle = q<HTMLButtonElement>("swipe-toggle");
  const beforePick = q("before-pick");
  const beforeSelect = q<HTMLSelectElement>("before-select");
  const compositeToggle = q<HTMLButtonElement>("composite-toggle");
  const hint = q("hint");
  const limitsEl = q("limits");
  const flagBefore = q("flag-before");
  const flagAfter = q("flag-after");
  const dockEl = q("dock");
  const sitesViewEl = q("sites-view");
  const sitesMaturity = q("sites-maturity");
  const missedViewEl = q("missed-view");
  const missedMaturity = q("missed-maturity");
  const viewName = q("view-name");
  const ledeEl = q("lede");
  const viewDance = q<HTMLButtonElement>("view-dance");
  const viewSites = q<HTMLButtonElement>("view-sites");
  const viewMissed = q<HTMLButtonElement>("view-missed");

  // Maturity label: always visible. Set before the map is created, so it is on the page even if the map cannot start
  // (for example when WebGL is unavailable).
  const banner = maturityBanner(m);
  maturityEl.textContent = banner.text;
  maturityEl.dataset.kind = banner.kind;
  sitesMaturity.textContent = banner.text;
  sitesMaturity.dataset.kind = banner.kind;
  missedMaturity.textContent = banner.text;
  missedMaturity.dataset.kind = banner.kind;

  const host = createHost(afterEl, beforeEl);

  const state = { i: 0, beforeI: 0, pol: "HH" as Pol, composite: false, swipe: false, fraction: 0.5, playing: false };
  let seq = 0;
  let pending: Promise<void> = Promise.resolve();
  let timer: ReturnType<typeof setTimeout> | undefined;

  const maturityTag = { synthetic: "synthetic demo", preview: "real NISAR preview", provisional: "provisional data" }[banner.kind];
  const isPreview = banner.kind === "preview";
  // Limits of the images, shown on The Dance. Not shown for synthetic data.
  limitsEl.hidden = banner.kind === "synthetic";
  if (banner.kind === "provisional") limitsEl.textContent = calibratedLimits(m, banner.text);
  if (isPreview) {
    ledeEl.textContent = "Step through the season's radar images. The images are scaled for display, so their brightness is not a measurement.";
    const size = m.pixel_m ? `about ${m.pixel_m} m` : "coarse";
    limitsEl.textContent =
      `Limits: each preview pixel covers ${size} and its brightness is scaled for display, so brightness cannot be compared as a measurement. ` +
      "Placement uses the published footprint and is good to roughly 2 km.";
  }

  // Views: The Dance (map), Site Stories (curves and cards), What NISAR Missed (timeline and data gap).
  const sitesView = createSitesView(q("sites-root"), { sites: opts.sites ?? null, manifest: m, createChart: opts.createChart });
  const missedView = createMissedView(q("missed-root"), { manifest: m });
  function showView(view: "dance" | "sites" | "missed"): void {
    const danceOn = view === "dance";
    if (!danceOn) stopPlaying();
    stageEl.hidden = !danceOn;
    dockEl.hidden = !danceOn;
    ledeEl.hidden = !danceOn;
    sitesViewEl.hidden = view !== "sites";
    missedViewEl.hidden = view !== "missed";
    viewDance.setAttribute("aria-pressed", String(danceOn));
    viewSites.setAttribute("aria-pressed", String(view === "sites"));
    viewMissed.setAttribute("aria-pressed", String(view === "missed"));
    const name = { dance: "The Dance", sites: "Site Stories", missed: "What NISAR Missed" }[view];
    viewName.textContent = name;
    document.title = `SARtale: ${name} (${maturityTag})`;
  }
  viewDance.addEventListener("click", () => showView("dance"));
  viewSites.addEventListener("click", () => showView("sites"));
  viewMissed.addEventListener("click", () => showView("missed"));

  // Slider, ticks, end labels, before picker.
  slider.max = String(last);
  ticks.innerHTML = dates
    .map((_, i) => `<i style="left:${last === 0 ? 0 : (i / last) * 100}%"></i>`)
    .join("");
  q("first").textContent = formatDate(dates[0]);
  q("last").textContent = formatDate(dates[last]);
  beforeSelect.innerHTML = dates.map((d, i) => `<option value="${i}">${formatDate(d)}</option>`).join("");
  compositeToggle.hidden = !m.composite;
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

  function updateLabels(): void {
    dateOut.textContent = formatDate(dates[state.i]);
    slider.setAttribute("aria-valuetext", formatDate(dates[state.i]));
    slider.value = String(state.i);
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
    playBtn.textContent = state.playing ? "Pause" : "Play";
    playBtn.setAttribute("aria-pressed", String(state.playing));
    swipeToggle.setAttribute("aria-pressed", String(state.swipe));
    compositeToggle.setAttribute("aria-pressed", String(state.composite));
    beforeEl.hidden = !(state.swipe && !state.composite);
    swipeEl.hidden = beforeEl.hidden;
    beforePick.hidden = !state.swipe || state.composite;
    const locked = state.composite;
    slider.disabled = locked || dates.length < 2;
    playBtn.disabled = locked || dates.length < 2;
    swipeToggle.disabled = locked || dates.length < 2;
    polSet.disabled = locked;
    hint.hidden = !locked;
    hint.textContent = locked ? compositeHint() : "";
    stageEl.style.setProperty("--swipe", `${state.fraction * 100}%`);
    beforeEl.style.clipPath = `inset(0 ${100 - state.fraction * 100}% 0 0)`;
    swipeEl.setAttribute("aria-valuenow", String(Math.round(state.fraction * 100)));
  }

  /** Draw whatever the state says. Newer calls supersede older ones; only the newest reports errors. */
  function refresh(): Promise<void> {
    const mine = ++seq;
    updateLabels();
    const jobs: Promise<void>[] = [
      state.composite ? setComposite(host.after, m) : setFrame(host.after, m, dates[state.i], state.pol),
    ];
    if (state.swipe && !state.composite) jobs.push(setFrame(host.before, m, dates[state.beforeI], state.pol));
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
    state.i += 1;
    await refresh();
    if (!state.playing) return;
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
    if (state.composite) stopPlaying();
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

  void refresh();
  showView("dance");

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
      sitesView.destroy();
      missedView.destroy();
      root.innerHTML = "";
    },
  };
}
