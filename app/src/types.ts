export type Pol = "HH" | "HV";

export interface FrameEntry {
  date: string;
  granule: string;
  frames: Record<Pol, string>;
}

export interface Manifest {
  stack: string;
  crid: string;
  /** "Provisional" for real NISAR data; anything else is treated as not real data. */
  maturity: string;
  /** [west, south, east, north] in lon/lat */
  bounds: [number, number, number, number];
  dates: FrameEntry[];
  composite?: string;
  stretch_db: Record<Pol, [number, number]>;
  gap?: { start: string; end: string };
}

/** One acquisition at a site. null means no valid value on that date (a gap, never zero). */
export interface SitePoint {
  date: string;
  hh_db: number | null;
  hv_db: number | null;
  valid_fraction: number | null;
}

/** A site and its HH/HV curve, as written to data/sites.json. */
export interface Site {
  id: string;
  name: string;
  lon: number;
  lat: number;
  role: string;
  series: SitePoint[];
}

/** Image source corners, clockwise from top-left, as [lon, lat]. */
export type Corners = [[number, number], [number, number], [number, number], [number, number]];
