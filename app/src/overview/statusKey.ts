import type { Lake } from "../lakes";
import { familyCounts, FAMILY_SENTENCE, type Family } from "../statusDisplay";
import { MARKER_LABELS, markerSvg } from "../statusMarkers";
import { el } from "./marks";

const ORDER: Family[] = ["alert", "watch", "decrease", "forming", "nochange", "unmeasured", "breakup", "frozen", "nolake"];

/** The families the key lists: those present in the file, and Alert always. */
export function keyFamilies(lakes: Lake[]): Family[] {
  const c = familyCounts(lakes);
  return ORDER.filter((f) => f === "alert" || c[f] > 0);
}

/** A foldable status key: marker, chip name and one plain sentence for each status. */
export function statusKey(lakes: Lake[], open: boolean): HTMLDetailsElement {
  const cls = "ov-key";
  const d = el("details", cls);
  d.dataset.role = "ov-key";
  d.open = open;
  d.append(el("summary", `${cls}-summary`, "What the statuses mean"));
  const ul = el("ul", `${cls}-list`);
  for (const f of keyFamilies(lakes)) {
    const li = el("li", `${cls}-item`);
    li.dataset.family = f;
    const mk = el("span", "ov-legend-mark");
    mk.innerHTML = markerSvg(f, { size: 18 });
    li.append(mk, el("strong", `${cls}-name`, MARKER_LABELS[f]), el("span", `${cls}-text`, FAMILY_SENTENCE[f]));
    ul.append(li);
  }
  d.append(ul);
  return d;
}
