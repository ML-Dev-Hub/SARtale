export type Pol = "HH" | "HV";

export interface FrameEntry {
  date: string;
  granule: string;
  frames: Record<Pol, string>;
  /** A visible caution for this date, shown next to the date stamp. */
  flag?: string;
}

type Rgb = [number, number, number];

/** The before-and-after step layer: one frame, coloured by the date of the step, with its direction. */
export interface StepLayer {
  method: string;
  reference: string;
  /** Ground size of the pixels the step is judged on, in metres. */
  pixel_m: number;
  /** The dates the test uses, in order. */
  dates: string[];
  /** The dates a step can be placed at: the first date after it. */
  split_dates: string[];
  min_segment: number;
  /** A pixel is flagged at or above both, with HH and HV moving the same way. */
  min_step_db: number;
  min_stability: number;
  control_p99_db: number;
  control_p99_stability: number;
  shuffled_p99_db: number;
  shuffled_p99_stability: number;
  scatter_floor_db: number;
  /** Share of scored pixels flagged, 0 to 1. */
  flagged_share: number;
  frame: string;
  /** The colours of the frame, by the date of the step and its direction. */
  classes: { date: string; up: Rgb; down: Rgb }[];
}

/** The statistical change layers. Calibrated builds with enough dates only. */
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
  /** The main change view. Absent from builds made before it existed. */
  step?: StepLayer;
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
/** The step test on a site's own curve. Mean dB after minus mean dB before, so the card can be read off the chart. */
export interface SiteStep {
  /** The first date after the step. */
  date: string;
  /** The last date before it. */
  previous_date: string;
  hh_db: number;
  hv_db: number;
  stability: number;
  /** Whether the curve's step passes the limits the map uses. */
  flagged: boolean;
  /** Share of map pixels in the site's radius flagged, 0 to 1. */
  map_share: number;
}

export interface Site {
  id: string;
  name: string;
  lon: number;
  lat: number;
  role: string;
  stack: string;
  crid: string;
  series: SitePoint[];
  /** null for a build without the step layer. */
  step?: SiteStep | null;
}

/** Image source corners, clockwise from top-left, as [lon, lat]. */
export type Corners = [[number, number], [number, number], [number, number], [number, number]];
