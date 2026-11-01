import * as maplibregl from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
// The worker is a separate self-contained file. Bundle it ourselves so nothing is fetched from outside the page.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { Camera, HostFactory, MapHost, Padding } from "./app";
import { loadImage } from "./images";
import type { MapLike } from "./map";
import type { Corners, Manifest, Site } from "./types";

maplibregl.setWorkerUrl(workerUrl);

const BACKGROUND = "#0b151b";
const reducedMotion = (): boolean => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
const OVERLAY_FILES = ["rivers", "roads", "places"] as const;

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
  private userMoved = false;
  private markers: { el: HTMLElement; lon: number; lat: number }[] = [];
  private seq = 0;
  private overlaySeq = 0;

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
    if (!decorative) {
      // A scale bar in metres, and zoom buttons for keyboard and mouse users. Touch users pinch.
      this.map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-left");
      this.map.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "bottom-left");
    }
    // Fit to the frame bounds so the image fills the stage, and keep it fitted while the layout settles.
    // Once the person pans or zooms, their view is left alone.
    this.map.on("movestart", (e) => {
      if ((e as { originalEvent?: unknown }).originalEvent) this.userMoved = true;
    });
    new ResizeObserver(() => {
      if (container.clientWidth === 0 || container.clientHeight === 0) return;
      this.map.resize();
      if (!this.userMoved && !this.decorative) this.fit();
    }).observe(container);
    this.ready = new Promise((resolve) => this.map.once("load", () => resolve()));
    void this.ready.then(() => this.addOverlays());
  }

  /**
   * Fit the study area to the stage. On a wide stage the picture is made to fill it side to side, so there are no
   * empty bands left and right, as long as that crops no more than a third off the top and bottom. Otherwise the
   * whole area is shown. Either way the person can pan to the rest.
   */
  fit(): void {
    const [w, s, e, n] = this.bounds;
    const el = this.map.getContainer();
    // A tall, narrow stage (a phone held upright) cannot show the whole area at a readable size, so it shows the middle
    // two thirds, which holds every site and place label. Pinching shows the rest.
    const narrow = el.clientHeight > 0 && el.clientWidth / el.clientHeight < 1;
    const dw = e - w;
    const box: [[number, number], [number, number]] = narrow ? [[w + 0.11 * dw, s], [w + 0.79 * dw, n]] : [[w, s], [e, n]];
    const cam = this.map.cameraForBounds(box, { padding: 8 });
    if (!cam || !el.clientHeight) return void this.map.fitBounds(box, { padding: 8, animate: false });
    const sw = maplibregl.MercatorCoordinate.fromLngLat(box[0]);
    const ne = maplibregl.MercatorCoordinate.fromLngLat(box[1]);
    const areaAspect = Math.abs(ne.x - sw.x) / Math.abs(sw.y - ne.y);
    const stageAspect = el.clientWidth / el.clientHeight;
    const crop = 1 - areaAspect / stageAspect;
    const zoom = stageAspect > areaAspect && crop <= 0.34 ? (cam.zoom ?? 0) + Math.log2(stageAspect / areaAspect) : cam.zoom;
    this.map.jumpTo({ center: cam.center, zoom, padding: { top: 0, right: 0, bottom: 0, left: 0 } });
  }

  /** Move the camera. `padding` keeps the target clear of floating panels. A person who moves the map is left alone. */
  moveTo(camera: Camera, padding: Padding): void {
    if ("home" in camera) {
      // Back to the default view of the whole stage, with no panel padding.
      this.userMoved = false;
      this.fit();
      return;
    }
    this.userMoved = true;
    const animate = !reducedMotion();
    // Panels can ask for more room than a phone has. Keep at least 30% of each side free, or MapLibre cannot fit the area.
    const el = this.map.getContainer();
    const raw = { top: padding.top + 8, right: padding.right + 8, bottom: padding.bottom + 8, left: padding.left + 8 };
    const squeeze = (a: number, b: number, size: number): [number, number] => {
      const room = size * 0.7;
      return a + b > room && a + b > 0 ? [(a / (a + b)) * room, (b / (a + b)) * room] : [a, b];
    };
    const [top, bottom] = squeeze(raw.top, raw.bottom, el.clientHeight);
    const [left, right] = squeeze(raw.left, raw.right, el.clientWidth);
    const pad = { top, right, bottom, left };
    if ("fit" in camera) {
      const [w, s, e, n] = this.bounds;
      this.map.fitBounds([[w, s], [e, n]], { padding: pad, animate, duration: 1400 });
    } else {
      this.map.easeTo({ center: camera.center, zoom: camera.zoom, padding: pad, animate, duration: 1400 });
    }
  }

  /** Resolves once the image source has taken its new picture, or after a short wait so a stall never blocks the app. */
  private whenSourceLoaded(id: string): Promise<void> {
    return new Promise((resolve) => {
      const finish = (): void => {
        this.map.off("sourcedata", onData);
        clearTimeout(timer);
        resolve();
      };
      const onData = (e: { sourceId?: string; isSourceLoaded?: boolean }): void => {
        if (e.sourceId === id && e.isSourceLoaded) finish();
      };
      const timer = setTimeout(finish, 1500);
      this.map.on("sourcedata", onData);
    });
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
        this.map.getLayer("change") ? "change" : this.firstOverlayLayer(),
      );
      this.hasImage = true;
    } else {
      const loaded = this.whenSourceLoaded("radar");
      (this.map.getSource("radar") as maplibregl.ImageSource).updateImage({ url, coordinates: corners });
      await loaded;
    }
  }

  /** The change layer sits above the radar and under any overlay lines. */
  async setOverlay(url: string | null, corners: Corners): Promise<void> {
    const mine = ++this.overlaySeq;
    if (url) await loadImage(url);
    await this.ready;
    if (mine !== this.overlaySeq) return; // a newer request came in while this one loaded
    if (!url) {
      if (this.map.getLayer("change")) this.map.setLayoutProperty("change", "visibility", "none");
      return;
    }
    if (this.map.getSource("change")) {
      (this.map.getSource("change") as maplibregl.ImageSource).updateImage({ url, coordinates: corners });
      this.map.setLayoutProperty("change", "visibility", "visible");
    } else {
      this.map.addSource("change", { type: "image", url, coordinates: corners });
      this.map.addLayer(
        { id: "change", type: "raster", source: "change", paint: { "raster-fade-duration": 0, "raster-opacity": 1 } },
        this.firstOverlayLayer(),
      );
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
        // A place may name "top" (label below its point) or "bottom" (label above it), so close neighbours do not overlap.
        const side = f.properties?.anchor === "top" || f.properties?.anchor === "bottom" ? (f.properties.anchor as "top" | "bottom") : undefined;
        new maplibregl.Marker({ element: el, anchor: side ?? "center", offset: [0, side === "top" ? 6 : side === "bottom" ? -6 : 0] })
          .setLngLat(f.geometry.coordinates as [number, number])
          .addTo(this.map);
      }
    }
  }

  /** One tappable marker per site. Each is a real button so it works by keyboard and touch. */
  setSiteMarkers(sites: Site[], onSelect: (id: string) => void): void {
    for (const site of sites) {
      const el = document.createElement("button");
      el.type = "button";
      el.className = "site-marker";
      el.setAttribute("aria-label", `Open site story: ${site.name}`);
      el.addEventListener("click", () => onSelect(site.id));
      new maplibregl.Marker({ element: el }).setLngLat([site.lon, site.lat]).addTo(this.map);
      this.markers.push({ el, lon: site.lon, lat: site.lat });
    }
    // A marker outside the picture cannot be seen, so it should not take keyboard focus either.
    const sync = (): void => {
      const b = this.map.getBounds();
      for (const m of this.markers) m.el.tabIndex = b.contains([m.lon, m.lat]) ? 0 : -1;
    };
    this.map.on("moveend", sync);
    this.map.on("resize", sync);
    sync();
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
        to.jumpTo({ center: from.getCenter(), zoom: from.getZoom(), padding: from.getPadding() });
        syncing = false;
      });
    };
    follow(after.map, before.map);
    follow(before.map, after.map);
    // The before map starts hidden; when it appears it takes over the camera of the visible map.
    new ResizeObserver(() => {
      if (beforeEl.clientWidth > 0) before.map.jumpTo({ center: after.map.getCenter(), zoom: after.map.getZoom(), padding: after.map.getPadding() });
    }).observe(beforeEl);
    return {
      after,
      before,
      setSiteMarkers: (sites, onSelect) => after.setSiteMarkers(sites, onSelect),
      moveTo: (camera, padding) => after.moveTo(camera, padding),
    };
  };
}
