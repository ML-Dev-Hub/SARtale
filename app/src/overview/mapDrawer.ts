import { BASE_BOUNDS, locatorStyle, statusSlug } from "../lakeLocator";
import type { Lake } from "../lakes";
import { statusDisplay } from "../statusDisplay";
import { familyMark } from "./marks";
import type { MapDrawerFactory, MappedLakesFile } from "./model";

const GREY = "#8ea3b0";

/**
 * Runs a callback once, when both the map style and the data are ready, whichever comes last. (Map.loaded() is no help:
 * it stays false while tiles load, long after the one "load" event has fired.)
 */
export function createReadyGate<T>(): { styleReady(): void; dataReady(d: T): void; onReady(fn: (d: T) => void): void } {
  let style = false;
  let data: { v: T } | null = null;
  let fn: ((d: T) => void) | null = null;
  let done = false;
  const check = (): void => {
    if (done || !style || !data || !fn) return;
    done = true;
    fn(data.v);
  };
  return {
    styleReady() { style = true; check(); },
    dataReady(d) { data = { v: d }; check(); },
    onReady(f) { fn = f; check(); },
  };
}

/** One watched lake's pin: its status shape (never colour alone), a button named for the lake. */
export function pinElement(l: Lake, onPick: (id: string) => void): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "ov-pin";
  b.dataset.id = l.id;
  b.dataset.status = statusSlug(l.status.status);
  const d = statusDisplay(l);
  b.dataset.family = d.family;
  b.setAttribute("aria-label", `${l.name}, ${d.chip}`);
  b.title = `${l.name}: ${d.chip}`;
  b.append(familyMark(d, 24));
  b.addEventListener("click", () => onPick(l.id));
  return b;
}

/**
 * The overview's map: the watched lakes as status pins and, once the file arrives, the mapped lakes as one layer of small
 * grey dots. MapLibre is imported on first use, so it stays out of the opening download; without WebGL the map says so
 * and the table and card still work. The base is the bundled MODIS picture, no outside tiles.
 */
export const createMapDrawer: MapDrawerFactory = (el, { lakes, loadMapped, onPick }) => {
  const gate = createReadyGate<MappedLakesFile>();
  const pins = new Map<string, HTMLButtonElement>();
  let map: import("maplibre-gl").Map | undefined;
  let ro: ResizeObserver | undefined;
  let gone = false;
  let sel: string | null = null;
  let mappedOn = true;
  let userMoved = false;
  let fitting = false;

  const applySel = (): void => {
    for (const [k, b] of pins) {
      b.toggleAttribute("data-selected", k === sel);
      b.setAttribute("aria-pressed", String(k === sel));
    }
    if (map?.getLayer("mapped-sel")) map.setFilter("mapped-sel", ["==", ["get", "id"], sel ?? ""]);
  };
  const applyVisible = (): void => {
    for (const id of ["mapped", "mapped-sel"]) if (map?.getLayer(id)) map.setLayoutProperty(id, "visibility", mappedOn ? "visible" : "none");
  };

  void (async () => {
    try {
      const [maplibregl, worker] = await Promise.all([
        import("maplibre-gl"),
        import("maplibre-gl/dist/maplibre-gl-worker.mjs?url"),
        import("maplibre-gl/dist/maplibre-gl.css"),
      ]);
      if (gone) return;
      maplibregl.setWorkerUrl(worker.default);
      const m = new maplibregl.Map({ container: el, style: locatorStyle() as never, attributionControl: false, dragRotate: false, maxPitch: 0 });
      m.touchZoomRotate.disableRotation();
      m.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
      map = m;
      const onStart = (e: unknown): void => {
        if (!fitting && typeof e === "object" && e !== null && !!(e as { originalEvent?: unknown }).originalEvent) userMoved = true;
      };
      m.on("movestart", onStart);
      m.on("zoomstart", onStart);
      const fit = (): void => {
        if (!el.clientWidth || !el.clientHeight) return;
        fitting = true;
        try {
          m.resize();
          if (userMoved) return;
          const { west, east, south, north } = BASE_BOUNDS;
          // A few percent of the smaller side, so pins on the edge are not clipped.
          const pad = Math.max(10, Math.round(Math.min(el.clientWidth, el.clientHeight) * 0.06));
          m.fitBounds([[west, south], [east, north]], { padding: pad, animate: false });
        } finally {
          fitting = false;
        }
      };
      for (const l of lakes) {
        const b = pinElement(l, onPick);
        pins.set(l.id, b);
        new maplibregl.Marker({ element: b }).setLngLat([l.lon, l.lat]).addTo(m);
      }
      applySel();
      // The style is ready at MapLibre's "style.load" (or "load", if that came first); the listener is attached before that can fire.
      m.once("style.load", () => gate.styleReady());
      m.once("load", () => gate.styleReady());
      ro = new ResizeObserver(fit);
      ro.observe(el);
      fit();

      const addMapped = (f: MappedLakesFile): void => {
        m.addSource("mapped", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: f.lakes.map((x) => ({ type: "Feature" as const, properties: { id: x.id }, geometry: { type: "Point" as const, coordinates: [x.lon, x.lat] } })),
          },
        });
        m.addLayer({ id: "mapped", type: "circle", source: "mapped", paint: { "circle-color": GREY, "circle-radius": 3, "circle-opacity": 0.95, "circle-stroke-color": "#050d16", "circle-stroke-width": 1 } });
        m.addLayer({
          id: "mapped-sel", type: "circle", source: "mapped", filter: ["==", ["get", "id"], ""],
          paint: { "circle-color": GREY, "circle-radius": 6, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
        });
        m.on("click", "mapped", (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (typeof id === "string") onPick(id);
        });
        m.on("mouseenter", "mapped", () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", "mapped", () => (m.getCanvas().style.cursor = ""));
        applySel();
        applyVisible();
      };
      gate.onReady((f) => {
        if (!gone) addMapped(f);
      });
      const f = await loadMapped();
      if (f) gate.dataReady(f);
    } catch (err) {
      if (!gone) el.textContent = `Map unavailable (${err instanceof Error ? err.message : String(err)}). The table still works.`;
    }
  })();

  return {
    highlight(id) {
      sel = id;
      applySel();
    },
    setMappedVisible(on) {
      mappedOn = on;
      applyVisible();
    },
    destroy() {
      gone = true;
      ro?.disconnect();
      map?.remove();
    },
  };
};
