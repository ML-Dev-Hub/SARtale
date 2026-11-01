import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { ChartFactory } from "./sitesView";

const HH_COLOR = "#3fd0c4";
const HV_COLOR = "#f2a93b";
const GRID = "#243a45";
const TICK = "#93a8b0";
const HEIGHT = 240;

/** The only place uPlot is touched. It needs a real canvas, so tests use a fake ChartFactory instead. */
export const createUplotChart: ChartFactory = (el, data) => {
  const width = () => Math.max(240, el.clientWidth);
  const axis = (label: string): uPlot.Axis => ({
    stroke: TICK,
    grid: { stroke: GRID, width: 1 },
    ticks: { stroke: GRID, width: 1 },
    label,
    labelFont: "600 12px sans-serif",
    font: "12px sans-serif",
  });
  const line = (label: string, stroke: string): uPlot.Series => ({
    label,
    stroke,
    width: 2,
    // Never draw a line across a missing date: null stays a visible break.
    spanGaps: false,
    points: { show: true, size: 7, fill: stroke },
  });
  const plot = new uPlot(
    {
      width: width(),
      height: HEIGHT,
      scales: { x: { time: true } },
      series: [{ label: "Date" }, line("HH (dB)", HH_COLOR), line("HV (dB)", HV_COLOR)],
      axes: [axis("Date"), axis("Backscatter (dB)")],
    },
    [data.x, data.hh, data.hv],
    el,
  );
  const ro = new ResizeObserver(() => plot.setSize({ width: width(), height: HEIGHT }));
  ro.observe(el);
  return {
    destroy: () => {
      ro.disconnect();
      plot.destroy();
    },
  };
};
