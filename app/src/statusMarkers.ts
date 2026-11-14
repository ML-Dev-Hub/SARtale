/** Shape, fill and line pattern encode status independently of colour. */
export type MarkerFamily = "alert" | "watch" | "decrease" | "nochange" | "frozen" | "breakup" | "unmeasured" | "nolake" | "forming";

export const MARKER_COLORS: Record<MarkerFamily, string> = {
  alert: "#ffd23f",
  watch: "#ffc46b",
  decrease: "#c4d3ff",
  nochange: "#7dd8f2",
  frozen: "#e2eef7",
  breakup: "#e2eef7",
  unmeasured: "#a9bdca",
  nolake: "#8ea3b0",
  forming: "#7dd8f2",
};

export const MARKER_LABELS: Record<MarkerFamily, string> = {
  alert: "Alert: growing",
  watch: "Watch",
  decrease: "Decrease noted",
  nochange: "No change",
  frozen: "Frozen",
  breakup: "Ice breaking up",
  unmeasured: "Not measured",
  nolake: "No lake now",
  forming: "Lake may be forming",
};

/** Decorative SVG: use MARKER_LABELS for the surrounding accessible label. */
export function markerSvg(family: MarkerFamily, opts?: { size?: number; selected?: boolean }): string {
  const requestedSize = opts?.size ?? 24;
  const size = Number.isFinite(requestedSize) && requestedSize > 0 ? requestedSize : 24;
  const color = MARKER_COLORS[family];
  const dark = "#050d16";
  // The under-stroke adds a total 2.5 px of dark outline to each shape.
  // Dash patterns are repeated on both passes so the gaps remain open.
  const solid = (geometry: string): string =>
    '<g fill="' + color + '" stroke="' + dark + '" stroke-width="2.5" stroke-linejoin="round">' + geometry + '</g>' +
    '<g fill="' + color + '" stroke="none">' + geometry + '</g>';
  const outline = (geometry: string, width = 2): string =>
    '<g fill="none" stroke="' + dark + '" stroke-width="' + (width + 2.5) + '" stroke-linejoin="round" stroke-linecap="round">' + geometry + '</g>' +
    '<g fill="none" stroke="' + color + '" stroke-width="' + width + '" stroke-linejoin="round" stroke-linecap="round">' + geometry + '</g>';
  const hexagon = '5,8 12,4 19,8 19,16 12,20 5,16';
  let shape: string;
  switch (family) {
    case "alert":
      // Plain, slightly larger upward triangle; no text or exclamation glyph.
      shape = solid('<polygon points="12,4 20,18.5 4,18.5"/>');
      break;
    case "watch":
      shape = solid('<polygon points="12,4.5 19.5,12 12,19.5 4.5,12"/>');
      break;
    case "decrease":
      shape = solid('<polygon points="5,6 19,6 12,19"/>');
      break;
    case "nochange":
      shape = solid('<circle cx="12" cy="12" r="6.5"/>') +
        '<circle cx="12" cy="12" r="2" fill="' + dark + '" stroke="none"/>';
      break;
    case "frozen":
      shape = outline('<polygon points="' + hexagon + '"/>') +
        outline('<line x1="12" y1="8" x2="12" y2="16"/><line x1="8.5" y1="10" x2="15.5" y2="14"/><line x1="8.5" y1="14" x2="15.5" y2="10"/>', 1.5);
      break;
    case "breakup":
      shape = outline('<polygon points="' + hexagon + '" stroke-dasharray="3 5" stroke-linecap="butt"/>') +
        // Two remaining radial arms, separated visually from the full crystal.
        outline('<path d="M12 8 L12 12 L15.5 14"/>', 1.5);
      break;
    case "unmeasured":
      shape = outline('<circle cx="12" cy="12" r="6.5" stroke-dasharray="3.4 3.4" stroke-linecap="butt"/>');
      break;
    case "nolake":
      shape = outline('<circle cx="12" cy="12" r="6.5"/><line x1="7.4" y1="16.6" x2="16.6" y2="7.4"/>');
      break;
    case "forming":
      shape = outline('<polygon points="12,4.5 19.5,12 12,19.5 4.5,12" stroke-dasharray="5.3 5.3" stroke-dashoffset="2.65" stroke-linecap="butt"/>');
      break;
  }
  // The ring's dark backing keeps white selection visible against snow.
  const selection = opts?.selected
    ? '<circle cx="12" cy="12" r="10" fill="none" stroke="' + dark + '" stroke-width="4"/><circle cx="12" cy="12" r="10" fill="none" stroke="#ffffff" stroke-width="2"/>'
    : '';
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="' + size + '" height="' + size + '" aria-hidden="true" focusable="false">' + selection + shape + '</svg>';
}
