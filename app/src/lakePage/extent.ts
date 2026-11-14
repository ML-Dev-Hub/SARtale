import { formatDate } from "../format";
import { isFrozen, type Lake } from "../lakes";
import { el } from "../overview/marks";
import { latestReadingOnTrack } from "../overview/model";
import { shareState } from "../share";

const CAVEAT = "Radar area against the largest mapped outline: they are measured differently, so read this as a guide.";

export type ExtentView =
  | { pct: string; word: "Above" | "Within" | "Within noise" | "noise unknown"; title: string | null; latest: string; largest: string; note: string }
  | { reason: string };

/** What the block says about the lake's radar area against its largest recorded extent, or why there is no share. */
export function extentView(l: Lake, minObservable = 0.5): ExtentView {
  // No value while the lake is frozen (the radar area is not open water), or when the zone is a circle with no outline.
  if (isFrozen(l)) return { reason: l.share_note ?? "Not shown while the lake is frozen: the radar area is not an open-water measurement." };
  if (!l.outline_source) return { reason: l.share_note ?? "Not shown: this lake has no mapped outline, only a circle around its point, so a share of the largest outline would mean nothing." };
  const s = shareState(l);
  if (!s) return { reason: l.share_note ?? "No largest recorded extent for this lake in this build." };
  const r = latestReadingOnTrack(l, minObservable);
  const e = l.largest_extent;
  const track = l.status.track ? `, ${l.status.track}` : "";
  const latest = r ? `Latest: ${r.area.toFixed(3)} km² on ${formatDate(r.date)} (NISAR${track}).` : "Latest: no open-water reading yet.";
  const largest = e ? `Largest recorded: ${e.km2.toFixed(3)} km², ${e.source}${e.year == null && /undated\)?$/i.test(e.source) ? "" : `, ${e.year ?? "undated"}`}.` : "Largest recorded: not available.";
  return { pct: `${s.pct}%`, word: s.word, title: s.title, latest, largest, note: CAVEAT };
}

const SENTENCE: Record<string, string> = {
  Above: "Above the largest recorded extent",
  Within: "Within the largest recorded extent",
  "Within noise": "Within noise: at or above the largest recorded extent, but less than 2× radar noise beyond it",
  "noise unknown": "Above or within not assessed: no noise estimate for this lake yet.",
};

/** Draws the block into root; it always draws something (the share, or the pipeline's reason, or a dash). */
export function renderExtent(root: HTMLElement, l: Lake, minObservable = 0.5): void {
  const v = extentView(l, minObservable);
  const box = el("div", "lp-extent");
  if ("reason" in v) {
    box.append(el("p", "lp-extent-pct lp-extent-none", "—"), el("p", "lp-extent-reason", v.reason));
  } else {
    const word = el("p", "lp-extent-word", SENTENCE[v.word]);
    if (v.title) word.title = v.title;
    if (v.word === "Above") box.dataset.above = "true";
    box.append(el("p", "lp-extent-pct", v.pct), word, el("p", "lp-extent-detail", `${v.latest} ${v.largest}`), el("p", "lp-caption", v.note));
  }
  root.append(box);
}
