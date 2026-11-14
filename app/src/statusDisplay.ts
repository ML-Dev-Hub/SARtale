import type { Lake } from "./lakes";
import { isoDay, shortDate } from "./overview/text";

/** One family per state an officer should tell apart; several pipeline statuses can share one. */
export type Family = "alert" | "watch" | "decrease" | "nochange" | "frozen" | "breakup" | "unmeasured" | "nolake" | "forming";

export interface StatusDisplay {
  family: Family;
  /** The family name shown in the chip. */
  chip: string;
  /** The marker shape (names as in overview/marks.ts). */
  mark: string;
  /** Dashed outline: the state is not a settled reading. */
  dashed: boolean;
  /** The second line: the evidence or the reason. */
  tag: string;
  /** Sort order of the families: attention first, then open water, then the rest. */
  rank: number;
}

const FAMILIES: Family[] = ["alert", "watch", "decrease", "forming", "nochange", "unmeasured", "breakup", "frozen", "nolake"];
const RANK = Object.fromEntries(FAMILIES.map((f, i) => [f, i])) as Record<Family, number>;

const CHIP: Record<Family, string> = {
  alert: "Alert: growing",
  watch: "Watch",
  decrease: "Decrease noted",
  nochange: "No change",
  frozen: "Frozen",
  breakup: "Ice breaking up",
  unmeasured: "Not measured",
  nolake: "No lake now",
  forming: "Lake may be forming",
};

const MARK: Record<Family, string> = {
  alert: "triangle", watch: "diamond", decrease: "down", nochange: "circle", frozen: "hexagon",
  breakup: "hexagon", unmeasured: "square", nolake: "crossed", forming: "ring",
};

const make = (family: Family, tag: string, dashed = false): StatusDisplay =>
  ({ family, chip: CHIP[family], mark: MARK[family], dashed, tag, rank: RANK[family] });

/** "since 9 Nov", or "" when the date is not known. */
const since = (iso: string | null | undefined): string => {
  const d = isoDay(iso ?? null);
  return d ? `since ${shortDate(d)}` : "";
};

export function statusDisplay(lake: Lake, constants?: { min_looks?: number }): StatusDisplay {
  const s = lake.status;
  const levelSince = since(s.level_since ?? lake.freeze?.since);
  const fz = since(lake.freeze?.since);
  switch (s.status) {
    case "Alert: growing": return make("alert", levelSince);
    case "Watch": return make("watch", levelSince);
    case "Decrease noted": return make("decrease", levelSince);
    case "No change": return make("nochange", levelSince);
    case "Frozen (seen by Sentinel-2)": return make("frozen", `Seen in Sentinel-2${fz ? ` ${fz}` : ""}`);
    case "Frozen (likely)": return make("frozen", `By air temperature${fz ? ` ${fz}` : ""}; no clear image`);
    case "Break-up likely": return make("breakup", `Air above 0 °C${fz ? ` ${fz}` : ""}`, true);
    case "Not measurable": return make("unmeasured", "Radar and Sentinel-2 disagree; area for information only", true);
    case "Not yet validated against Sentinel-2": return make("unmeasured", "Waiting for a clear Sentinel-2 scene to check the radar");
    case "Not observable": return make("unmeasured", "Radar cannot see enough of the lake on this track");
    case "Not enough NISAR looks yet":
      return make("unmeasured", `Fewer than ${constants?.min_looks ?? "the minimum number of"} radar looks so far`);
    case "Not seen this pass": return make("unmeasured", "The newest pass did not see the lake");
    case "No lake now": return make("nolake", "No water in recent imagery");
    case "Lake may be forming": return make("forming", s.reason ?? "");
    default: return make("unmeasured", String(s.status));
  }
}

export function familyCounts(lakes: Lake[]): Record<Family, number> {
  const c = Object.fromEntries(FAMILIES.map((f) => [f, 0])) as Record<Family, number>;
  for (const l of lakes) c[statusDisplay(l).family]++;
  return c;
}

/** Of the frozen lakes: how many were seen in Sentinel-2 and how many are frozen by air temperature alone. */
export function frozenBreakdown(lakes: Lake[]): { seen: number; temperature: number } {
  let seen = 0;
  let temperature = 0;
  for (const l of lakes) {
    if (l.status.status === "Frozen (seen by Sentinel-2)") seen++;
    else if (l.status.status === "Frozen (likely)") temperature++;
  }
  return { seen, temperature };
}
