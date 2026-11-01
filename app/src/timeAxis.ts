import { acquisitionDates, changeExclusion, flagFor, formatDate, orderedDates } from "./timeline";
import type { Manifest } from "./types";

const DAY_MS = 86_400_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export interface AxisDate {
  /** Index into the built dates, as the date slider counts them. */
  index: number;
  date: string;
  /** Place on the axis, 0 to 1, by real time. */
  pos: number;
  flag?: string;
  /** Why the change analysis leaves this date out, when it does. */
  excluded?: string;
}

export interface AxisModel {
  dates: AxisDate[];
  /** Days NISAR imaged that this build does not use. Drawn small and not selectable. */
  unused: { date: string; pos: number }[];
  months: { label: string; pos: number }[];
  /** The data gap as a share of the axis, or null when the manifest has none inside the range. */
  gap: { from: number; to: number; label: string } | null;
  /** Calendar days from the first to the last built date, counting both ends. */
  days: number;
}

function dayStart(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

const dayMonth = (iso: string): string => formatDate(iso).split(" ").slice(0, 2).join(" ");

/**
 * Where each date sits on a time axis that runs from the start of the first day to the end of the last, so the
 * space between two passes is the real time between them. The gap, when the manifest has one, is a band.
 */
export function buildAxis(m: Manifest): AxisModel {
  const built = orderedDates(m);
  const imaged = acquisitionDates(m);
  const all = [...built, ...imaged].sort();
  const start = dayStart(all[0]);
  const end = dayStart(all[all.length - 1]) + DAY_MS;
  const span = end - start;
  const at = (ms: number): number => Math.min(1, Math.max(0, (ms - start) / span));
  const midday = (iso: string): number => at(dayStart(iso) + DAY_MS / 2);

  const dates: AxisDate[] = built.map((date, index) => ({
    index,
    date,
    pos: midday(date),
    flag: flagFor(m, date),
    excluded: changeExclusion(m, date),
  }));
  const builtSet = new Set(built);
  const unused = imaged.filter((d) => !builtSet.has(d)).map((date) => ({ date, pos: midday(date) }));

  const first = new Date(start);
  const months: AxisModel["months"] = [{ label: MONTHS[first.getUTCMonth()], pos: 0 }];
  let t = Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 1);
  while (t < end) {
    const d = new Date(t);
    months.push({ label: MONTHS[d.getUTCMonth()], pos: at(t) });
    t = Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1);
  }

  let gap: AxisModel["gap"] = null;
  if (m.gap) {
    const from = Date.parse(m.gap.start);
    const to = Date.parse(m.gap.end);
    if (Number.isFinite(from) && Number.isFinite(to) && to > from && to > start && from < end) {
      const f = new Date(from).toISOString().slice(0, 10);
      const e = new Date(to).toISOString().slice(0, 10);
      gap = { from: at(from), to: at(to), label: `No data ${dayMonth(f)} to ${dayMonth(e)}` };
    }
  }
  return { dates, unused, months, gap, days: Math.round(span / DAY_MS) };
}

/** The built date nearest to a place on the axis (0 to 1). */
export function nearestDate(model: AxisModel, pos: number): number {
  let best = 0;
  let bestGap = Infinity;
  for (const d of model.dates) {
    const gap = Math.abs(d.pos - pos);
    if (gap < bestGap) {
      best = d.index;
      bestGap = gap;
    }
  }
  return best;
}

export interface AxisHandle {
  /** Mark the selected date. */
  select(index: number): void;
  /** Tint the dates the step map can place, by the colour the map gives each. null clears it. */
  tint(colours: Record<string, string> | null): void;
  /** Mark dates the change analysis leaves out. */
  showExcluded(on: boolean): void;
  /** Highlight one date, for example while its legend row is hovered. */
  highlight(date: string | null): void;
  destroy(): void;
}

export interface AxisOptions {
  /** Called when the person points at the axis. The index is of a built date. */
  onPick(index: number, final: boolean): void;
  disabled?: () => boolean;
}

/** Draw the axis into `layer` and wire pointer input (touch and mouse) on `track`. Keyboard stays with the range input. */
export function mountAxis(track: HTMLElement, layer: HTMLElement, model: AxisModel, opts: AxisOptions): AxisHandle {
  layer.replaceChildren();
  const pct = (v: number): string => `${(v * 100).toFixed(3)}%`;
  const make = (cls: string, pos?: number): HTMLElement => {
    const el = document.createElement("i");
    el.className = cls;
    if (pos !== undefined) el.style.left = pct(pos);
    return el;
  };

  for (const mo of model.months) {
    const tick = make("axis-month", mo.pos);
    tick.dataset.label = mo.label;
    layer.append(tick);
  }
  if (model.gap) {
    const band = make("axis-gap", model.gap.from);
    band.style.width = pct(model.gap.to - model.gap.from);
    band.dataset.label = "No data";
    band.title = model.gap.label;
    layer.append(band);
  }
  for (const u of model.unused) {
    const el = make("axis-dot unused", u.pos);
    el.title = `${formatDate(u.date)}: observed, not used in this build`;
    layer.append(el);
  }
  const dots = new Map<number, HTMLElement>();
  for (const d of model.dates) {
    const el = make("axis-dot", d.pos);
    el.dataset.date = d.date;
    el.title = [formatDate(d.date), d.flag].filter(Boolean).join(". ");
    if (d.flag) el.classList.add("flagged");
    if (d.excluded) el.dataset.excluded = "true";
    dots.set(d.index, el);
    layer.append(el);
  }

  let dragging = false;
  const posOf = (e: PointerEvent): number => {
    const r = layer.getBoundingClientRect();
    return r.width > 0 ? (e.clientX - r.left) / r.width : 0;
  };
  const pick = (e: PointerEvent, final: boolean): void => {
    if (opts.disabled?.()) return;
    opts.onPick(nearestDate(model, posOf(e)), final);
  };
  const down = (e: PointerEvent): void => {
    if (e.button !== undefined && e.button > 0) return;
    if (opts.disabled?.()) return;
    dragging = true;
    track.setPointerCapture?.(e.pointerId);
    track.classList.add("dragging");
    pick(e, false);
  };
  const move = (e: PointerEvent): void => {
    if (dragging) pick(e, false);
  };
  const up = (e: PointerEvent): void => {
    if (!dragging) return;
    dragging = false;
    track.classList.remove("dragging");
    pick(e, true);
  };
  const cancel = (): void => {
    dragging = false;
    track.classList.remove("dragging");
  };
  track.addEventListener("pointerdown", down);
  track.addEventListener("pointermove", move);
  track.addEventListener("pointerup", up);
  track.addEventListener("pointercancel", cancel);

  let selected = -1;
  return {
    select(index) {
      if (selected >= 0) dots.get(selected)?.classList.remove("current");
      selected = index;
      dots.get(index)?.classList.add("current");
    },
    tint(colours) {
      for (const d of model.dates) {
        const el = dots.get(d.index)!;
        const c = colours?.[d.date];
        if (c) {
          el.style.setProperty("--step", c);
          el.classList.add("step");
        } else {
          el.style.removeProperty("--step");
          el.classList.remove("step");
        }
      }
    },
    showExcluded(on) {
      for (const d of model.dates) dots.get(d.index)!.classList.toggle("excluded", on && !!d.excluded);
    },
    highlight(date) {
      for (const d of model.dates) dots.get(d.index)!.classList.toggle("lit", d.date === date);
    },
    destroy() {
      track.removeEventListener("pointerdown", down);
      track.removeEventListener("pointermove", move);
      track.removeEventListener("pointerup", up);
      track.removeEventListener("pointercancel", cancel);
      layer.replaceChildren();
    },
  };
}
