export type Pol = "HH" | "HV";

export interface FrameEntry {
  date: string;
  granule: string;
  frames: Record<Pol, string>;
  /** A visible caution for this date, shown next to the date stamp. */
  flag?: string;
}

export interface Manifest {
  stack: string;
  crid: string;
  /**
   * "Provisional" for calibrated NISAR data, "Provisional preview" for NASA's display-scaled browse images.
   * Anything else is treated as not real data.
   */
  maturity: string;
  /** [west, south, east, north] in lon/lat */
  bounds: [number, number, number, number];
  dates: FrameEntry[];
  composite?: string;
  /** The three dates behind the seasonal composite (red, green, blue). */
  composite_dates?: string[];
  /** dB stretch of calibrated frames. null for browse previews, which are not in dB. */
  stretch_db: Record<Pol, [number, number]> | null;
  gap?: { start: string; end: string };
  /** Ground size of one preview pixel in metres, measured from the georeferencing. */
  pixel_m?: number;
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
