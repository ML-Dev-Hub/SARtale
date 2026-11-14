import { statusSlug } from "../lakeLocator";

/** The status marker shapes (20 × 20): a shape for each kind of status, so the chip never relies on colour alone. */
const SHAPES = {
  triangle: "M10 2 L19 18 L1 18 Z",
  diamond: "M10 1.5 L18.5 10 L10 18.5 L1.5 10 Z",
  down: "M1.5 3 L18.5 3 L10 18 Z",
  ring: "M10 3.5 a6.5 6.5 0 1 0 0.01 0 Z",
  hexagon: "M10 2 L17 6 L17 14 L10 18 L3 14 L3 6 Z",
  circle: "M10 4 a6 6 0 1 0 0.01 0 Z",
  square: "M4.5 4.5 H15.5 V15.5 H4.5 Z",
  dash: "M3 10 H17",
  crossed: "M3.5 3.5 H16.5 V16.5 H3.5 Z M3.5 16.5 L16.5 3.5",
};

const STATUS_SHAPE: Record<string, string> = {
  "Alert: growing": SHAPES.triangle,
  Watch: SHAPES.diamond,
  "Decrease noted": SHAPES.down,
  "Lake may be forming": SHAPES.ring,
  "No change": SHAPES.circle,
  "Frozen (likely)": SHAPES.hexagon,
  "Frozen (seen by Sentinel-2)": SHAPES.hexagon,
  "Break-up likely": SHAPES.hexagon,
  "No lake now": SHAPES.crossed,
  "Not enough NISAR looks yet": SHAPES.square,
  "Not observable": SHAPES.square,
  "Not measurable": SHAPES.square,
  "Not yet validated against Sentinel-2": SHAPES.square,
  "Not seen this pass": SHAPES.dash,
};

const SVG = "http://www.w3.org/2000/svg";

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

export function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string>): SVGElementTagNameMap[K] {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

/** A status marker: decorative, the words beside it carry the status. */
export function statusMark(status: string, size = 12): SVGSVGElement {
  const s = svg("svg", { viewBox: "0 0 20 20", width: String(size), height: String(size), "aria-hidden": "true", class: `ov-mark ov-mark-${statusSlug(status)}` });
  s.append(svg("path", { d: STATUS_SHAPE[status] ?? SHAPES.circle }));
  return s;
}

/** The status chip: a marker shape and the status in words. */
export function statusChip(status: string): HTMLElement {
  const c = el("span", `ov-chip ov-status-${statusSlug(status)}`);
  c.append(statusMark(status), el("span", undefined, status));
  return c;
}

