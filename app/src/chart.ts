import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { LakeChartData, LakeChartFactory } from "./lakeWatchView";

const GRID = "#1b2c3b";
const TICK = "#a9bdca";
const HEIGHT = 260;
const FONT = '"Inter Variable", "Inter", system-ui, sans-serif';

/** Dates are UTC-midnight seconds, so the axis must read them in UTC or viewers west of UTC see the day before. */
export const utcTzDate = (ts: number): Date => uPlot.tzDate(new Date(ts * 1e3), "Etc/UTC");

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
/** "18 Jun" from UTC-midnight seconds: day then month, the order readers here use. */
export const dayMonth = (ts: number): string => {
  const d = new Date(ts * 1e3);
  return `${d.getUTCDate()} ${MONTH_ABBR[d.getUTCMonth()]}`;
};

const axis = (label: string): uPlot.Axis => ({
  stroke: TICK,
  grid: { stroke: GRID, width: 1 },
  ticks: { stroke: GRID, width: 1 },
  label,
  labelFont: `600 14px ${FONT}`,
  font: `14px ${FONT}`,
});

export const FROZEN_GREY = "#8d9aa5";
const BAND_EDGE = "#6f8798";
const BAND_FILL = "rgba(125, 216, 242, 0.12)";
const RAIL = "#a9bdca";
const VERSION = "#d3dfe7";
export const LEVEL_RING = "#ffd23f";
/** Ring colour by the level a pass set: Watch amber, Alert and Decrease noted their status colours. */
export const LEVEL_COLORS: Partial<Record<string, string>> = { Watch: "#ffc46b", "Alert: growing": "#ffd23f", "Decrease noted": "#c4d3ff" };
const TRACK_COLORS =["#7dd8f2", "#ffc46b", "#9db8ff", "#e58bd0", "#b6d96b", "#ff8a7a"];

/** The uPlot options for the lake area chart: one line per track, then a markers-only series for excluded passes. */
export function lakeChartOptions(width: number, data: LakeChartData): uPlot.Options {
  let k = 0;
  const series: uPlot.Series[] = [{ label: "Date" }];
  for (const s of data.series) {
    if (s.band) {
      // The status track's baseline ± 2 × noise: thin dashed edges, shaded between them (bands below).
      series.push({ label: s.label, stroke: BAND_EDGE, width: 1, dash: [4, 4], spanGaps: true, points: { show: false } });
    } else if (s.bridge) {
      // Dashed in the track colour (the track is the first line, so it has the first colour): spans a pass with no usable reading.
      series.push({ label: s.label, stroke: TRACK_COLORS[0], width: 2, dash: [5, 5], spanGaps: true, points: { show: false } });
    } else if (s.level) {
      const ring = (s.levelName && LEVEL_COLORS[s.levelName]) || LEVEL_RING;
      // The passes that set a level: large ringed markers in the level colour, no line.
      series.push({ label: s.label, stroke: ring, width: 0, paths: () => null, points: { show: true, size: 15, width: 3, stroke: ring, fill: "transparent" } });
    } else if (s.rail) {
      // Passes with no usable reading: hollow rings on their own rail along the bottom, not at any area value.
      series.push({ label: s.label, scale: "rail", stroke: RAIL, width: 0, paths: () => null, points: { show: true, size: 10, width: 2, stroke: RAIL, fill: "transparent" } });
    } else if (s.version) {
      // The vertical dashed line is drawn by the draw hook below; the series itself draws nothing.
      series.push({ label: s.label, stroke: VERSION, width: 0, paths: () => null, points: { show: false } });
    } else if (s.frozen) {
      // Grey markers, no line: taken while the lake was probably frozen, so not an open-water reading.
      series.push({ label: s.label, stroke: FROZEN_GREY, width: 0, paths: () => null, points: { show: true, size: 8, width: 2, stroke: FROZEN_GREY, fill: "#53606b" } });
    } else if (s.excluded) {
      // Hollow markers, no line: the pass is shown but is not part of any track's trend.
      series.push({ label: s.label, stroke: "#ff8a7a", width: 0, paths: () => null, points: { show: true, size: 10, width: 2, stroke: "#ff8a7a", fill: "#0b1825" } });
    } else {
      const c = TRACK_COLORS[k++ % TRACK_COLORS.length];
      // Nulls here are dates that belong to other tracks, so the line steps over them within this track only.
      series.push({ label: s.label, stroke: c, width: 2, spanGaps: !data.series.some((b) => b.bridge), points: { show: true, size: 7, fill: c } });
    }
  }
  // Shade between the band's upper and lower edges (uPlot series indices count the x series as 0).
  const hi = data.series.findIndex((s) => s.band === "hi");
  const lo = data.series.findIndex((s) => s.band === "lo");
  const bands: uPlot.Band[] = hi >= 0 && lo >= 0 ? [{ series: [hi + 1, lo + 1], fill: BAND_FILL }] : [];
  const hasRail = data.series.some((s) => s.rail);
  const marks = data.series.flatMap((s, i) => (s.version ? [{ label: s.label, at: s.values.map((v, j) => (v === null ? null : data.x[j])).filter((t): t is number => t !== null), i }] : []));
  const scales: uPlot.Scales = { x: { time: true } };
  // The rail is its own scale, so its zero values do not pull the area axis down; the area axis leaves room under the data.
  if (hasRail) {
    scales.rail = { range: [-1, 14] };
    scales.y = { range: (_u, lo, hi) => [Math.max(0, lo - (hi - lo || 1) * 0.35), hi + (hi - lo || 1) * 0.1] };
  }
  const hooks: uPlot.Hooks.Arrays = {};
  if (marks.length) {
    hooks.draw = [
      (u) => {
        const { ctx } = u;
        const { top, height, left, width: w } = u.bbox;
        ctx.save();
        ctx.strokeStyle = VERSION;
        ctx.fillStyle = VERSION;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([2, 4]);
        ctx.font = `14px ${FONT}`;
        for (const m of marks) {
          for (const t of m.at) {
            const x = Math.round(u.valToPos(t, "x", true));
            ctx.beginPath();
            ctx.moveTo(x, top);
            ctx.lineTo(x, top + height);
            ctx.stroke();
          }
          const x = u.valToPos(m.at[m.at.length - 1], "x", true);
          ctx.setLineDash([]);
          ctx.textAlign = x > left + w * 0.6 ? "right" : "left";
          ctx.fillText(m.label, x + (ctx.textAlign === "right" ? -6 : 6), top + 14);
        }
        ctx.restore();
      },
    ];
  }
  return {
    width,
    height: HEIGHT,
    tzDate: utcTzDate,
    scales,
    series,
    bands,
    hooks,
    axes: [{ ...axis("Date"), values: (_u, splits) => splits.map((t) => dayMonth(t)) }, axis("Radar water area (km²)")],
    cursor: { drag: { x: false, y: false, setScale: false }, points: { size: 11 } },
    // The history block has its own legend (shape and words); the plain tooltip-style legend stays for the older chart.
    legend: { show: !hasRail && !marks.length },
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
