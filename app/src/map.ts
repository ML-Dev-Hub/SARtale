import { dataUrl, frameUrl } from "./timeline";
import type { Corners, Manifest, Pol } from "./types";

/** The only thing the app needs from a map. The MapLibre adapter implements it; tests use a fake. */
export interface MapLike {
  /** Show an image at the given corners. Rejects if the image cannot be loaded. */
  setImage(url: string, corners: Corners): Promise<void>;
  /** Show an image above the radar, or clear it with null. Optional: a map without it simply shows no overlay. */
  setOverlay?(url: string | null, corners: Corners): Promise<void>;
}

/** Manifest bounds [w, s, e, n] to image source corners: top-left, top-right, bottom-right, bottom-left. */
export function cornersFromBounds(bounds: Manifest["bounds"]): Corners {
  const [w, s, e, n] = bounds;
  return [[w, n], [e, n], [e, s], [w, s]];
}

async function show(map: MapLike, m: Manifest, urlFor: () => string, what: string): Promise<void> {
  let url = "";
  try {
    url = urlFor();
    await map.setImage(url, cornersFromBounds(m.bounds));
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    throw new Error(`Could not load the radar overlay for ${what}${url ? ` (${url})` : ""}: ${reason}`);
  }
}

export function setFrame(map: MapLike, m: Manifest, date: string, pol: Pol): Promise<void> {
  return show(map, m, () => frameUrl(m, date, pol), `${date} ${pol}`);
}

/** Show the change frame of a date. A date with no frame, or null, clears the overlay. */
export async function setChangeOverlay(map: MapLike, m: Manifest, date: string | null): Promise<void> {
  const path = date ? m.change?.frames[date] : undefined;
  const corners = cornersFromBounds(m.bounds);
  if (!path) return map.setOverlay?.(null, corners);
  const url = dataUrl(path);
  try {
    await map.setOverlay?.(url, corners);
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    throw new Error(`Could not load the change overlay for ${date} (${url}): ${reason}`);
  }
}

export function setComposite(map: MapLike, m: Manifest): Promise<void> {
  if (!m.composite) return Promise.reject(new Error("This data set has no seasonal composite overlay"));
  return show(map, m, () => dataUrl(m.composite!), "the seasonal composite");
}
