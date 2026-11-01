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

/** Reserved for the Site Stories view (a later task). */
export interface Site {
  id: string;
  name: string;
  lon: number;
  lat: number;
}

/** Image source corners, clockwise from top-left, as [lon, lat]. */
export type Corners = [[number, number], [number, number], [number, number], [number, number]];
