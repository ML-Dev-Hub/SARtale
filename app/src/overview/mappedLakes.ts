import { issueUrl } from "../lakeRequests";
import type { MappedLake, MappedLakesFile } from "./model";

export const SOURCE_LABELS = { hkhpk2020: "HKH-PK-2020", himag: "Hi-MAG", osm: "OpenStreetMap" } as const;

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";

function toMappedLake(x: unknown): MappedLake | null {
  if (!x || typeof x !== "object") return null;
  const o = x as Record<string, unknown>;
  const sup = o.suparco ?? null;
  const supOk = sup === null || (typeof sup === "object" && isNum((sup as { id?: unknown }).id) && (sup as { match?: unknown }).match === "probable");
  const ok =
    isStr(o.id) && isNum(o.lon) && isNum(o.lat) && isNum(o.km2) && (o.year === null || isNum(o.year)) &&
    (o.source === "hkhpk2020" || o.source === "himag" || o.source === "osm") && supOk;
  if (!ok) return null;
  return {
    id: o.id as string, lon: o.lon as number, lat: o.lat as number, km2: o.km2 as number, year: o.year as number | null,
    source: o.source as MappedLake["source"],
    suparco: sup === null ? null : { id: (sup as { id: number }).id, match: "probable" },
  };
}

/**
 * Reads mapped_lakes.json. A malformed lake is dropped on its own; a missing file, a slow response, bad JSON or a file
 * without its version, notices and lake list is null (the overview then says the mapped lakes could not be loaded).
 */
export async function loadMappedLakes(
  url = "data/mapped_lakes.json",
  fetchFn: typeof fetch = (...a) => fetch(...a),
  timeoutMs = 20_000,
): Promise<MappedLakesFile | null> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetchFn(url, { cache: "no-cache", signal: ctl.signal });
    if (!res.ok) return null;
    const j = (await res.json()) as Record<string, unknown> | null;
    if (!j || typeof j !== "object" || !isNum(j.version) || !Array.isArray(j.lakes) || !Array.isArray(j.sources)) return null;
    const n = j.notice as Record<string, unknown> | undefined;
    if (!n || !isStr(n.odbl) || !isStr(n.cc_by)) return null;
    return {
      version: j.version,
      built: isStr(j.built) ? j.built : "",
      notice: { odbl: n.odbl, cc_by: n.cc_by },
      sources: j.sources as MappedLakesFile["sources"],
      lakes: j.lakes.map(toMappedLake).filter((l): l is MappedLake => l !== null),
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** The lake-request form, pre-filled with this mapped lake's point and where its outline comes from. */
export function watchThisLakeUrl(m: MappedLake): string {
  return issueUrl({
    name: `Mapped lake ${m.id}`,
    lat: String(m.lat),
    lon: String(m.lon),
    source: `${SOURCE_LABELS[m.source]} outline, ${m.year ?? "undated"}`,
  });
}
