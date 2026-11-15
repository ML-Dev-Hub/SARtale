/**
 * The pipeline writes some limits in technical words (EPSG codes, resampling, method D17, P-codes). plainLimit rewrites the
 * known lines into plain English for the lake page and the brief; any other line passes through unchanged. The original
 * wording is still shown in the sources block (see changedLimits), so nothing is hidden.
 */
const ZONE = /^Track (\w+) comes in another UTM zone \(EPSG:\d+\); its windows are resampled \(nearest neighbou?r\) onto the lake's grid \(EPSG:\d+\)\.?$/;
const MIX = /^Track (\w+) mixes NISAR processing versions P\d+ \(provisional\) and P\d+ \(standard\)\. A calibration change between them can shift areas\.?$/;
const AREAS = /^Areas are water within .*method D17\b/;

export function plainLimit(text: string): string {
  const t = text.trim();
  let m = ZONE.exec(t);
  if (m) return `Track ${m[1]} is recorded on a neighbouring map grid; its pixels are shifted onto this lake's grid before measuring, which can move the outline edge by up to one pixel.`;
  m = MIX.exec(t);
  if (m) return `Track ${m[1]} mixes early (provisional) and later (standard) NISAR processing; the change between them can shift the measured area a little.`;
  if (AREAS.test(t)) return "Area = radar-dark water inside the lake outline (plus 200 m) or a search circle. Wet shore and mud flats also look dark, so a lake that drains onto them barely changes its radar area. Images are pictures, not map overlays.";
  return text;
}

/** The original wording of the lines plainLimit rewrites, without repeats, for the sources block. */
export function changedLimits(lines: string[]): string[] {
  return [...new Set(lines.filter((l) => plainLimit(l) !== l))];
}
