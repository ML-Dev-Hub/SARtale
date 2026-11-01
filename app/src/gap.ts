import { acquisitionDates, orderedDates } from "./timeline";
import type { Manifest } from "./types";

/**
 * "observed": NISAR imaged the day and this build uses it. "observed-unused": NISAR imaged the day but this
 * build does not include it. "no-observation": NISAR recorded nothing that day.
 */
export type CoverageState = "observed" | "observed-unused" | "no-observation";

export interface Segment {
  /** UTC calendar date, YYYY-MM-DD. */
  date: string;
  state: CoverageState;
  /** True when the whole day lies inside the permanent data gap in the manifest. Ordinary days between passes are false. */
  inGap: boolean;
}

export const UNUSED_LABEL = "Observed, not used in this build";

export function stateLabel(state: Segment["state"]): string {
  return state === "observed" ? "Observed" : state === "observed-unused" ? UNUSED_LABEL : "No observation";
}

const DAY_MS = 86_400_000;
const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Milliseconds at UTC midnight for a YYYY-MM-DD string, or null if it is not a real calendar date. */
function dayStart(iso: string): number | null {
  const m = ISO_DAY.exec(iso);
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return new Date(t).toISOString().slice(0, 10) === iso ? t : null;
}

/** The gap in the manifest as [start, end] milliseconds, or null when absent or unreadable. */
function gapRange(m: Manifest): [number, number] | null {
  if (!m.gap) return null;
  const start = Date.parse(m.gap.start);
  const end = Date.parse(m.gap.end);
  return Number.isFinite(start) && Number.isFinite(end) && end > start ? [start, end] : null;
}

/**
 * One segment per UTC calendar day from `from` to `to` inclusive.
 * A day is "observed" when the manifest builds it, and "observed-unused" when the manifest's `acquisitions`
 * list it but the build does not (a manifest without `acquisitions` falls back to its `dates`). Unless the whole
 * day lies inside the permanent gap: then it is "no-observation" with inGap true, even if the manifest lists it.
 * A day the gap only touches (the days of the gap's start and end) is not inGap, so a pass on it stays observed.
 * An empty, reversed or invalid range returns [].
 */
export function coverageSegments(m: Manifest, from: string, to: string): Segment[] {
  const a = dayStart(from);
  const b = dayStart(to);
  if (a === null || b === null || b < a) return [];
  const built = new Set(orderedDates(m));
  const imaged = new Set(acquisitionDates(m));
  const gap = gapRange(m);
  const out: Segment[] = [];
  for (let t = a; t <= b; t += DAY_MS) {
    const date = new Date(t).toISOString().slice(0, 10);
    const inGap = gap !== null && t >= gap[0] && t + DAY_MS <= gap[1];
    const state: CoverageState = inGap || !imaged.has(date) ? "no-observation" : built.has(date) ? "observed" : "observed-unused";
    out.push({ date, state, inGap });
  }
  return out;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-07-27T22:03:25Z" to "27 Jul 2026, 22:03:25 UTC". Unreadable input is returned as it came. */
export function formatUtcMoment(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const d = new Date(t);
  const p = (n: number): string => String(n).padStart(2, "0");
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
}

/** The verified data-gap fact, from the manifest only. null when the manifest holds no gap. */
export function gapSummary(m: Manifest): string | null {
  if (!gapRange(m) || !m.gap) return null;
  return `NISAR has no data from ${formatUtcMoment(m.gap.start)} to ${formatUtcMoment(m.gap.end)}.`;
}
