import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
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
