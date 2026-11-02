import type { Lake } from "./lakes";
import type { LocatorFactory } from "./lakeWatchView";

const BACKGROUND = "#0b151b"; // same base style as maplibreAdapter.ts: a plain background, no outside tiles

/**
 * True when a MapLibre movestart/zoomstart event came from the person: drag, scroll, pinch and the +/- buttons all
 * carry the DOM event as `originalEvent`. Programmatic moves (our fitBounds, and Map.resize(), which fires movestart
 * when the hidden view first gets a size) carry none, so they must not stop the locator from framing the lakes.
 */
export function isUserMove(e: unknown): boolean {
  return typeof e === "object" && e !== null && !!(e as { originalEvent?: unknown }).originalEvent;
}

/**
 * A small map with one button per lake. MapLibre is loaded after first paint (dynamic import), the way lazyHost.ts
 * loads the main map, so Lake Watch adds nothing to the opening download. If it cannot start (no WebGL) the lake list
 * still works and a short line says the locator is unavailable.
 */
export const createLakeLocator: LocatorFactory = (el, lakes, onPick) => {
  const buttons = new Map<string, HTMLButtonElement>();
  let map: { remove(): void } | undefined;
  let ro: ResizeObserver | undefined;
  let gone = false;
  let userMoved = false;
  let fitting = false;
  let pending: string | undefined;

  void (async () => {
    try {
      const [maplibregl, worker] = await Promise.all([
        import("maplibre-gl"),
        import("maplibre-gl/dist/maplibre-gl-worker.mjs?url"),
        import("maplibre-gl/dist/maplibre-gl.css"),
      ]);
      if (gone) return;
      maplibregl.setWorkerUrl(worker.default);
      const m = new maplibregl.Map({
        container: el,
        style: { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": BACKGROUND } }] },
        attributionControl: false,
        dragRotate: false,
        maxPitch: 0,
      });
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
      map = m;
      // Only moves the person made (drag, scroll, pinch, +/- buttons) stop the automatic framing; see isUserMove.
      const onStart = (e: unknown): void => {
        if (!fitting && isUserMove(e)) userMoved = true;
      };
      m.on("movestart", onStart);
      m.on("zoomstart", onStart);
      // Runs on every size change, including the first time the view becomes visible with a non-zero size
      // (the map may have been created while Lake Watch was hidden, e.g. when the start screen opened first).
      const fit = (): void => {
        if (!el.clientWidth || !el.clientHeight) return;
        fitting = true;
        try {
          m.resize();
          if (userMoved) return; // once the person has zoomed or panned, leave their view alone
          const w = Math.min(...lakes.map((l) => l.bounds?.[0] ?? l.lon));
          const e = Math.max(...lakes.map((l) => l.bounds?.[2] ?? l.lon));
          const s = Math.min(...lakes.map((l) => l.bounds?.[1] ?? l.lat));
          const n = Math.max(...lakes.map((l) => l.bounds?.[3] ?? l.lat));
          m.fitBounds([[w, s], [e, n]], { padding: 30, animate: false, maxZoom: 9 });
        } finally {
          fitting = false;
        }
      };
      m.on("load", () => {
        // Where a lake has bounds they draw its frame; the marker always comes from lon/lat.
        const features = lakes
          .filter((l: Lake) => l.bounds)
          .map((l) => {
            const [w, s, e, n] = l.bounds as [number, number, number, number];
            return { type: "Feature" as const, properties: {}, geometry: { type: "LineString" as const, coordinates: [[w, s], [e, s], [e, n], [w, n], [w, s]] } };
          });
        m.addSource("frames", { type: "geojson", data: { type: "FeatureCollection", features } });
        m.addLayer({ id: "frames", type: "line", source: "frames", paint: { "line-color": "#4fd1c5", "line-width": 1 } });
      });
      // Town (for reference): orientation only, not data. Plain text markers, because the blank base style has no fonts for map text.
      const towns = [["Gilgit", 74.31, 35.92], ["Karimabad / Hunza", 74.66, 36.32], ["Chitral", 71.79, 35.85], ["Skardu", 75.63, 35.3]] as const;
      for (const [name, lon, lat] of towns) {
        const t = document.createElement("span");
        t.className = "lw-town";
        t.textContent = name;
        t.setAttribute("aria-hidden", "true");
        new maplibregl.Marker({ element: t, anchor: "top" }).setLngLat([lon, lat]).addTo(m);
      }
      for (const l of lakes) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "site-marker lw-marker";
        b.dataset.role = "lw-marker";
        b.dataset.control = String(l.role === "control");
        b.setAttribute("aria-label", l.name);
        b.title = l.name;
        b.addEventListener("click", () => onPick(l.id));
        buttons.set(l.id, b);
        new maplibregl.Marker({ element: b }).setLngLat([l.lon, l.lat]).addTo(m);
      }
      if (pending) for (const [k, b] of buttons) b.toggleAttribute("data-selected", k === pending);
      ro = new ResizeObserver(fit);
      ro.observe(el);
      fit();
    } catch (err) {
      if (!gone) el.textContent = `Map unavailable (${err instanceof Error ? err.message : String(err)}). The list still works.`;
    }
  })();

  return {
    highlight(id) {
      pending = id; // applied when the markers arrive, if they have not yet
      for (const [k, b] of buttons) b.toggleAttribute("data-selected", k === id);
    },
    destroy() {
      gone = true;
      ro?.disconnect();
      map?.remove();
    },
  };
};
