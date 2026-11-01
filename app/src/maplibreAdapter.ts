import * as maplibregl from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
// The worker is a separate self-contained file. Bundle it ourselves so nothing is fetched from outside the page.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { HostFactory, MapHost } from "./app";
import type { MapLike } from "./map";
import type { Corners, Manifest } from "./types";

maplibregl.setWorkerUrl(workerUrl);

const BACKGROUND = "#0b151b";
const OVERLAY_FILES = ["rivers", "roads", "places"] as const;

/** Loads an image and rejects if it is missing or not an image. Also warms the browser cache. */
function loadImage(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve();
    img.onerror = () => reject(new Error(`image not found or unreadable`));
    img.src = url;
  });
}

/** Optional GeoJSON overlays. A missing file (or a dev server answering with index.html) is skipped quietly. */
async function fetchOverlay(name: string): Promise<FeatureCollection | null> {
  try {
    const res = await fetch(`data/overlays/${name}.geojson`);
    if (!res.ok) return null;
    const json = (await res.json()) as FeatureCollection;
    return json?.type === "FeatureCollection" ? json : null;
  } catch {
    return null;
  }
}

class RadarMap implements MapLike {
  readonly map: maplibregl.Map;
  private readonly ready: Promise<void>;
  private hasImage = false;
  private seq = 0;

  constructor(container: HTMLElement, private readonly bounds: Manifest["bounds"], private readonly decorative: boolean) {
    this.map = new maplibregl.Map({
      container,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "background", type: "background", paint: { "background-color": BACKGROUND } }],
      },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    });
    this.map.touchZoomRotate.disableRotation();
    // Fit to the data the first time the container has a real size; keep the canvas in step after that.
    let fitted = false;
    new ResizeObserver(() => {
      if (container.clientWidth === 0 || container.clientHeight === 0) return;
      this.map.resize();
      if (!fitted && !this.decorative) {
        fitted = true;
        this.fit();
      }
    }).observe(container);
    this.ready = new Promise((resolve) => this.map.once("load", () => resolve()));
    void this.ready.then(() => this.addOverlays());
  }

  fit(): void {
    const [w, s, e, n] = this.bounds;
    this.map.fitBounds([[w, s], [e, n]], { padding: 24, animate: false });
  }

  async setImage(url: string, corners: Corners): Promise<void> {
    const mine = ++this.seq;
    await loadImage(url);
    await this.ready;
    if (mine !== this.seq) return; // a newer frame was requested while this one loaded
    if (!this.hasImage) {
      this.map.addSource("radar", { type: "image", url, coordinates: corners });
      this.map.addLayer(
        { id: "radar", type: "raster", source: "radar", paint: { "raster-fade-duration": 0, "raster-opacity": 1 } },
        this.firstOverlayLayer(),
      );
      this.hasImage = true;
    } else {
      (this.map.getSource("radar") as maplibregl.ImageSource).updateImage({ url, coordinates: corners });
    }
  }

  /** Radar sits under any overlay lines that are already on the map. */
  private firstOverlayLayer(): string | undefined {
    return OVERLAY_FILES.map((n) => `overlay-${n}-line`).find((id) => this.map.getLayer(id));
  }

  private async addOverlays(): Promise<void> {
    const [rivers, roads, places] = await Promise.all(OVERLAY_FILES.map(fetchOverlay));
    if (rivers) this.addLines("rivers", rivers, "#4fd1c5", 1.6);
    if (roads) this.addLines("roads", roads, "#f2a93b", 1.2);
    if (places) {
      for (const f of places.features) {
        if (f.geometry.type !== "Point") continue;
        const el = document.createElement("span");
        el.className = "place";
        el.textContent = String(f.properties?.name ?? "");
        if (this.decorative) el.setAttribute("aria-hidden", "true");
        new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates as [number, number]).addTo(this.map);
      }
    }
  }

  private addLines(name: string, data: FeatureCollection, color: string, width: number): void {
    this.map.addSource(`overlay-${name}`, { type: "geojson", data });
    this.map.addLayer({
      id: `overlay-${name}-line`,
      type: "line",
      source: `overlay-${name}`,
      paint: { "line-color": color, "line-width": width, "line-opacity": 0.85 },
    });
  }
}

/** Two maps stacked and kept in step; the before map is clipped by the app. */
export function hostFactoryFor(m: Manifest): HostFactory {
  return (afterEl, beforeEl): MapHost => {
    const after = new RadarMap(afterEl, m.bounds, false);
    const before = new RadarMap(beforeEl, m.bounds, true);
    let syncing = false;
    const follow = (from: maplibregl.Map, to: maplibregl.Map) => {
      from.on("move", () => {
        if (syncing) return;
        syncing = true;
        to.jumpTo({ center: from.getCenter(), zoom: from.getZoom() });
        syncing = false;
      });
    };
    follow(after.map, before.map);
    follow(before.map, after.map);
    // The before map starts hidden; when it appears it takes over the camera of the visible map.
    new ResizeObserver(() => {
      if (beforeEl.clientWidth > 0) before.map.jumpTo({ center: after.map.getCenter(), zoom: after.map.getZoom() });
    }).observe(beforeEl);
    return { after, before };
  };
}
