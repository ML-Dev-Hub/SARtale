import type { Lake } from "./lakes";

export interface ShareState {
  /** The share as a whole percent. */
  pct: number;
  above: boolean;
  /** Below 100% the reading is inside the outline; at 100% or more "Above" needs 2× radar noise beyond it. */
  word: "Above" | "Within" | "Within noise" | "noise unknown";
  /** Explains the two words that sit at 100% or more without being "Above". */
  title: string | null;
}

/** The lake's radar area as a share of its largest recorded extent, with the word for it; null when it has no share. */
export function shareState(l: Lake): ShareState | null {
  const v = l.share_of_largest;
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  const above = l.above_largest === true;
  const word = above ? "Above" : v < 1 ? "Within" : l.above_largest === false ? "Within noise" : "noise unknown";
  const title = v >= 1 && !above
    ? l.above_largest === false
      ? "Above 100% but less than 2× radar noise beyond the largest mapped outline"
      : "Above 100%, but the radar noise is not known, so it cannot say whether the lake is above its largest mapped outline"
    : null;
  return { pct: Math.round(v * 100), above, word, title };
}
