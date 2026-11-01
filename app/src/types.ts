export type Pol = "HH" | "HV";

export interface FrameEntry {
  date: string;
  granule: string;
  frames: Record<Pol, string>;
  /** A visible caution for this date, shown next to the date stamp. */
  flag?: string;
}

/** The statistical change layer. Calibrated builds with enough dates only. */
export interface ChangeLayer {
  method: string;
  reference: string;
  library: string;
  version: string;
  /** Pixels at or above this score are drawn; the rest are transparent. */
  threshold: number;
  /** The score at the top of the shared colour scale. */
  scale_max: number;
  baseline_dates: string[];
  /** Dates left out of the analysis entirely, each with its reason. */
  excluded: { date: string; reason: string }[];
  /** What was subtracted from each scored date, in dB. */
  removed_offsets_db: Record<string, Record<Pol, number>>;
  /** A visible note for a date, for example a pattern nobody can explain yet. */
  date_notes?: Record<string, string>;
  /** Scored date to frame path. */
  frames: Record<string, string>;
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
  /**
   * Every UTC date NISAR imaged this stack (YYYY-MM-DD), including dates not built into this data set.
   * Absent in older manifests: readers then fall back to `dates`.
   */
  acquisitions?: string[];
  composite?: string;
  /** The three dates behind the seasonal composite (red, green, blue). */
  composite_dates?: string[];
  /** dB stretch of calibrated frames. null for browse previews, which are not in dB. */
  stretch_db: Record<Pol, [number, number]> | null;
  gap?: { start: string; end: string };
  /** Ground size of one pixel of the web frames in metres. */
  pixel_m?: number;
  /** Ground size of the pixels behind every measurement (COGs, site curves) in metres. Calibrated builds only. */
  analysis_m?: number;
  change?: ChangeLayer;
}

/** One acquisition at a site. null means no valid value on that date (a gap, never zero). */
export interface SitePoint {
  date: string;
  hh_db: number | null;
  hv_db: number | null;
  valid_fraction: number | null;
  /**
   * Median pixel score of the change layer inside the site's radius. null when the date is excluded or nothing is
   * valid. Absent from builds made before the layer existed.
   */
  change_score?: number | null;
}

/**
 * A site and its HH/HV curve, as written to data/sites.json.
 *
 * Contract: `stack` and `crid` copy the manifest the curves were sampled for. The app shows a site only
 * when both equal the manifest's, so stale or demo curves never appear beside another build. A site
 * with no stamp (or the wrong one) is dropped.
 */
export interface Site {
  id: string;
  name: string;
  lon: number;
  lat: number;
  role: string;
  stack: string;
  crid: string;
  series: SitePoint[];
}

/** Image source corners, clockwise from top-left, as [lon, lat]. */
export type Corners = [[number, number], [number, number], [number, number], [number, number]];
