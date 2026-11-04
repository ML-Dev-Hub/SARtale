import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { LakeChartData, LakeChartFactory } from "./lakeWatchView";

const GRID = "#1b2c3b";
const TICK = "#a9bdca";
const HEIGHT = 260;
const FONT = '"Inter Variable", "Inter", system-ui, sans-serif';

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

const TRACK_COLORS = ["#7dd8f2", "#ffc46b", "#9db8ff", "#e58bd0", "#b6d96b", "#ff8a7a"];

/** The uPlot options for the lake area chart: one line per track, then a markers-only series for excluded passes. */
export function lakeChartOptions(width: number, data: LakeChartData): uPlot.Options {
  let k = 0;
  const series: uPlot.Series[] = [{ label: "Date" }];
  for (const s of data.series) {
    if (s.excluded) {
      // Hollow markers, no line: the pass is shown but is not part of any track's trend.
      series.push({ label: s.label, stroke: "#ff8a7a", width: 0, paths: () => null, points: { show: true, size: 10, width: 2, stroke: "#ff8a7a", fill: "#0b1825" } });
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
