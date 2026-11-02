import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { LakeChartData, LakeChartFactory } from "./lakeWatchView";
import type { ChartFactory, ChartHooks } from "./sitesView";

const HH_COLOR = "#3fd0c4";
const HV_COLOR = "#f2a93b";
const GRID = "#243a45";
const TICK = "#93a8b0";
const HEIGHT = 260;
const FONT = '"Bricolage Grotesque Variable", "Segoe UI", system-ui, sans-serif';

/** Dates are UTC-midnight seconds, so the axis must read them in UTC or viewers west of UTC see the day before. */
export const utcTzDate = (ts: number): Date => uPlot.tzDate(new Date(ts * 1e3), "Etc/UTC");

const axis = (label: string): uPlot.Axis => ({
  stroke: TICK,
  grid: { stroke: GRID, width: 1 },
  ticks: { stroke: GRID, width: 1 },
  label,
  labelFont: `600 12px ${FONT}`,
  font: `12px ${FONT}`,
});

const line = (label: string, stroke: string): uPlot.Series => ({
  label,
  stroke,
  width: 2,
  // Never draw a line across a missing date: null stays a visible break.
  spanGaps: false,
  points: { show: true, size: 7, fill: stroke },
});

/** The uPlot options, without touching a canvas. Exported so tests can check them. */
export function chartOptions(width: number, hooks?: ChartHooks): uPlot.Options {
  return {
    width,
    height: HEIGHT,
    tzDate: utcTzDate,
    scales: { x: { time: true } },
    series: [{ label: "Date" }, line("HH (dB)", HH_COLOR), line("HV (dB)", HV_COLOR)],
    axes: [axis("Date"), axis("Backscatter (dB)")],
    // A tap or click on the chart picks the nearest date. No drag-zoom, so a swipe on a phone still scrolls the page.
    cursor: { drag: { x: false, y: false, setScale: false }, points: { size: 11 } },
    legend: { show: false },
    hooks: {
      ready: [
        (u) => {
          u.over.style.cursor = hooks?.onPick ? "pointer" : "default";
          u.over.addEventListener("click", () => {
            const i = u.cursor.idx;
            if (i != null && hooks?.onPick) hooks.onPick(i);
          });
        },
      ],
    },
  };
}

/** The only place a uPlot is constructed. It needs a real canvas, so tests use a fake ChartFactory instead. */
export const createUplotChart: ChartFactory = (el, data, hooks) => {
  const width = () => Math.max(240, el.clientWidth);
  const plot = new uPlot(chartOptions(width(), hooks), [data.x, data.hh, data.hv], el);
  const ro = new ResizeObserver(() => plot.setSize({ width: width(), height: HEIGHT }));
  ro.observe(el);
  return {
    destroy: () => {
      ro.disconnect();
      plot.destroy();
    },
  };
};

const TRACK_COLORS = ["#3fd0c4", "#f2a93b", "#9db8ff", "#e58bd0", "#b6d96b", "#ff8a7a"];

/** The uPlot options for the lake area chart: one line per track, then a markers-only series for excluded passes. */
export function lakeChartOptions(width: number, data: LakeChartData): uPlot.Options {
  let k = 0;
  const series: uPlot.Series[] = [{ label: "Date" }];
  for (const s of data.series) {
    if (s.excluded) {
      // Hollow markers, no line: the pass is shown but is not part of any track's trend.
      series.push({ label: s.label, stroke: "#ff8a7a", width: 0, paths: () => null, points: { show: true, size: 10, width: 2, stroke: "#ff8a7a", fill: "#0b151b" } });
    } else {
      const c = TRACK_COLORS[k++ % TRACK_COLORS.length];
      // Nulls here are dates that belong to other tracks, so the line steps over them within this track only.
      series.push({ label: s.label, stroke: c, width: 2, spanGaps: true, points: { show: true, size: 7, fill: c } });
    }
  }
  return {
    width,
    height: HEIGHT,
    tzDate: utcTzDate,
    scales: { x: { time: true } },
    series,
    axes: [axis("Date"), axis("Water area (km²)")],
    cursor: { drag: { x: false, y: false, setScale: false }, points: { size: 11 } },
    legend: { show: true },
  };
}

export const createUplotLakeChart: LakeChartFactory = (el, data) => {
  const width = () => Math.max(240, el.clientWidth);
  const plot = new uPlot(lakeChartOptions(width(), data), [data.x, ...data.series.map((s) => s.values)] as uPlot.AlignedData, el);
  const ro = new ResizeObserver(() => plot.setSize({ width: width(), height: HEIGHT }));
  ro.observe(el);
  return {
    destroy: () => {
      ro.disconnect();
      plot.destroy();
    },
  };
};
