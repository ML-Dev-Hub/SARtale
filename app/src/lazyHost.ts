import type { HostFactory, MapHost } from "./app";
import type { MapLike } from "./map";
import type { Manifest } from "./types";

/**
 * A map host that loads the map library after the page has first painted. The opening screen and the controls need no
 * map code, so the heavy chunk (about 1 MB) downloads in the background instead of delaying the first view. Calls made
 * before it arrives wait for it, in order. If the library cannot start (for example without WebGL), the calls that
 * need it fail with its message, and the app shows that message beside the controls.
 */
export function lazyHostFactory(m: Manifest, load: () => Promise<{ hostFactoryFor(m: Manifest): HostFactory }> = () => import("./maplibreAdapter")): HostFactory {
  return (afterEl, beforeEl): MapHost => {
    const real: Promise<MapHost> = load().then((mod) => mod.hostFactoryFor(m)(afterEl, beforeEl));
    // A failure is reported by the calls that wait on it; this keeps the browser from also logging it as unhandled.
    real.catch(() => {});
    const proxy = (side: "after" | "before"): MapLike => ({
      setImage: async (url, corners) => (await real)[side].setImage(url, corners),
      setOverlay: async (url, corners) => (await real)[side].setOverlay?.(url, corners),
    });
    return {
      after: proxy("after"),
      before: proxy("before"),
      setSiteMarkers: (sites, onSelect) => void real.then((h) => h.setSiteMarkers?.(sites, onSelect), () => {}),
      moveTo: (camera, padding) => void real.then((h) => h.moveTo?.(camera, padding), () => {}),
    };
  };
}
