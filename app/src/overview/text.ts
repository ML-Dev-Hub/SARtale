import { formatDate } from "../format";
import type { Lake } from "../lakes";

/** "9 Nov" from "2026-11-09". */
export const shortDate = (iso: string): string => formatDate(iso).replace(/ \d{4}$/, "");

/** "+0.004" / "−0.004" (a true minus); no sign when it rounds to zero. */
export function signed(v: number): string {
  const shown = Math.abs(v).toFixed(3);
  return Number(shown) === 0 ? shown : `${v > 0 ? "+" : "−"}${shown}`;
}

/**
 * The SUPARCO part of a row's second line; a "possible" match is never shown. SUPARCO publishes no coordinates, so
 * without a probable match we only know that we found none, not that SUPARCO does not list the lake.
 */
export function suparcoShort(l: Lake): string {
  const s = l.suparco;
  if (!s || s.match === "possible") return "no SUPARCO match";
  return s.match === "probable" ? `SUPARCO ${s.id} (probable)` : `SUPARCO ${s.id}`;
}

/**
 * The second line of a lake's row or card: district and SUPARCO match. The district is left out when the name already
 * ends with it ("Proglacial lake C029, Swat" in Swat).
 */
export function placeLine(l: Lake): string {
  const d = l.district;
  const repeated = !!d && l.name.toLowerCase().endsWith(`, ${d.toLowerCase()}`);
  return [repeated ? null : d, suparcoShort(l)].filter(Boolean).join(" · ");
}

export const isoDay = (v: string | null | undefined): string | null => (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v) && Number.isFinite(Date.parse(v.slice(0, 10))) ? v.slice(0, 10) : null);

export const OV_FOOTER = "Screening on NISAR radar, not a warning. Official warnings come from PMD, NDMA, GBDMA and PDMA.";
export const OV_CREDITS = "Lake inventories: HKH-PK-2020 (CC BY 4.0), Hi-MAG (CC BY 4.0), OpenStreetMap (ODbL). Radar: NASA–ISRO NISAR. Optical checks: Copernicus Sentinel-2.";
