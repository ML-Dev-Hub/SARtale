"""Write the committed inventory tables from the 11 Nov 2026 lake-inventory investigation.

    python processing/inventory/make_tables.py --lakefind <dir> [--out processing/inventory] [--fill-register]

<dir> holds the investigation's outputs (lake_candidates.csv and .geojson, suparco_match.csv) and its raw downloads
under dl/ (HKH-PK-2020, Hi-MAG, the OpenStreetMap Overpass result, geoBoundaries, the SUPARCO posts and map). The
HMAGLOFDB zip is read from --hmaglofdb. The scripts that made those outputs are in scripts/ next to this file (copied
as they ran; they take the investigation folder as their first argument). Raw downloads belong in
processing/inventory/dl/, which git ignores.

Writes, under --out: lake_candidates.csv and suparco_match.csv (copied), sources.json (URL, SHA-256 and licence of
every download), districts.geojson (geoBoundaries ADM2 near the study area, simplified to 0.001°, each with its
province in `adm1`, plus Pakistan's ADM0 outline), new_lakes.json (the 43 register rows, with `batch`) and
watched_inventory.json (outline areas and SUPARCO matches per watched lake); processing/outlines/<id>.geojson for the
43 lakes; and app/public/data/mapped_lakes.json (every candidate except those on a watched lake, without outlines).
--fill-register adds district, province and district_source to the lakes_in.json rows that lack them.

Needs geopandas and shapely (not part of the rebuild environment); the pipeline reads only the written files.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from shapely.geometry import box, mapping  # noqa: E402

HERE = Path(__file__).resolve().parent
PROCESSING = HERE.parent
REPO = PROCESSING.parent
sys.path.insert(0, str(PROCESSING))
from sartale import districts  # noqa: E402

UTM = 32643  # metres, for areas, centroids and distances
DISTRICT_BOX = (69.8, 33.4, 77.6, 38.6)  # the request box (34.4-37.6 N, 70.8-76.6 E) and 1° around it
MAPPED_EXCLUDE_M = 300  # a candidate this close to a watched lake's point is that lake
FETCHED = "11 Nov 2026"

# (batch, candidate, register id, name). Names are the lakes' usual names; an unnamed lake is named by its candidate
# number, never by a SUPARCO number (SUPARCO publishes none of its lakes' locations: the IDs are our reconstruction).
PICKS = [
    (1, "C001", "karambar_lake", "Karambar Lake (Karambar Pass)"), (1, "C002", "khukush", "Khukush Lake"),
    (1, "C003", "shandur", "Shandur Lake"), (1, "C004", "bashkar_gol", "Bashkar Gol Lake"),
    (1, "C005", "atro_sar", "Atro Sar"), (1, "C006", "lake_c006", None), (1, "C007", "lake_c007", None),
    (1, "C008", "zhagi_chhat", "Zhagi Chhat"), (1, "C009", "andrab", "Andrab Lake"),
    (1, "C010", "lake_c010", None), (1, "C011", "lake_c011", None),
    (2, "C012", "lake_c012", None), (2, "C013", "lake_c013", None), (2, "C014", "rama", "Rama Lake"),
    (2, "C015", "lake_c015", None), (2, "C017", "lake_c017", None), (2, "C018", "lake_c018", None),
    (2, "C019", "lake_c019", None), (2, "C020", "lake_c020", None), (2, "C022", "katora", "Katora Lake"),
    (2, "C023", "godar_dhand", "Godar Dhand"),
    (3, "C024", "kondol", "Kondol Lake"), (3, "C025", "shetangud_dhand", "Shetangud Dhand"),
    (3, "C026", "lake_c026", None), (3, "C027", "lake_c027", None), (3, "C028", "lake_c028", None),
    (3, "C029", "lake_c029", None), (3, "C030", "lake_c030", None), (3, "C031", "lake_c031", None),
    (3, "C032", "suroor_ojorik", "Suroor Ojorik Lake"), (3, "C033", "lake_c033", None),
    (3, "C034", "lake_c034", None),
    (4, "C035", "lake_c035", None), (4, "C036", "lake_c036", None), (4, "C037", "lake_c037", None),
    (4, "C039", "lake_c039", None), (4, "C040", "lake_c040", None), (4, "C041", "lake_c041", None),
    (4, "C042", "lake_c042", None), (4, "C044", "borith", "Borith Lake"), (4, "C046", "lake_c046", None),
    (4, "C047", "lake_c047", None), (4, "C049", "lake_c049", None),
]
# Register sites that are inventory candidates too. The other four sites (attabad, shisper, karambar, rogheli) are
# not: Attabad is a landslide-dammed lake, and the others have no lake now or no lake of 0.05 km² or more.
SITES = {"passu": "C045", "shazore": "C043", "khurdopin": "C048"}

SUPARCO_METHOD = (
    "SUPARCO publishes no coordinates, names or outlines for its list of potentially dangerous glacial lakes (PDGL), "
    "only ID numbers, areas and a numbered dot map. SARtale georeferenced SUPARCO's 1 Jul 2026 GLOF status map "
    "(district boundaries fitted to geoBoundaries ADM2, then 7 large lakes whose areas match SUPARCO's within 10%; "
    "RMS 0.6 km), read the dot labels by eye and matched each ID to an inventory lake. 'probable': exactly one label "
    "is read at the dot, an inventory lake within 1.5 km has 0.6-1.5 times SUPARCO's area, and the district agrees "
    "where SUPARCO gives one. 'possible': the label is ambiguous or the area agrees only loosely. A dot whose label "
    "could be several IDs never gives one ID. These are reconstructions, not SUPARCO-supplied locations; no SUPARCO "
    "image or geometry is copied.")

ZENODO_HKHPK = "https://doi.org/10.5281/zenodo.15476013"
ZENODO_HIMAG = "https://doi.org/10.5281/zenodo.4275164"
OVERPASS_QUERY = ('[out:json][timeout:600];'
                  '(way["natural"="water"]["water"!="river"](34.4,70.8,37.6,76.6);'
                  'relation["natural"="water"]["water"!="river"](34.4,70.8,37.6,76.6););out geom;')
SUPARCO_LICENCE = ("None stated ('All rights reserved by SUPARCO'). Not redistributed: only SARtale's reconstructed "
                   "ID matches are committed, with their method")
GB_API = "https://www.geoboundaries.org/api/current/gbOpen/PAK/{level}/"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sources(lakefind: Path, hmaglofdb: Path) -> list[dict]:
    dl = lakefind / "dl"
    out = [
        {"id": "hkhpk2020", "name": "HKH-PK-2020 glacial lake inventory (Siddique et al. 2023)",
         "url": "https://zenodo.org/api/records/15476013/files/HKH-PK.zip/content", "doi": ZENODO_HKHPK,
         "file": "hkhpk/hkhpk.zip", "licence": "CC BY 4.0", "attribution": "Siddique et al. 2023, Zenodo 15476013",
         "fetched": "2026-11-11",
         "note": "8,808 outlines mapped on PlanetScope imagery of Sep 2020. The .prj says UTM 43N (EPSG:32643), not "
                 "EPSG:4326 as the record's description says."},
        {"id": "himag", "name": "Hi-MAG glacial lake database 2008-2017 (Chen et al. 2021, ESSD 13:741)",
         "url": "https://zenodo.org/api/records/4275164/files/Hi-MAG%20database.zip/content", "doi": ZENODO_HIMAG,
         "file": "himag/himag.zip", "licence": "CC BY 4.0",
         "attribution": "Chen et al. 2021, Earth Syst. Sci. Data 13:741, Zenodo 4275164", "fetched": "2026-11-11",
         "note": "Annual Landsat 30 m outlines with lake type and elevation."},
        {"id": "osm", "name": "OpenStreetMap water polygons (natural=water) over the request box",
         "url": "https://overpass-api.de/api/interpreter", "file": "osm/osm_water.json", "licence": "ODbL 1.0",
         "attribution": "© OpenStreetMap contributors", "fetched": "2026-11-11",
         "osm_base": json.loads((dl / "osm" / "osm_water.json").read_text(encoding="utf-8"))["osm3s"][
             "timestamp_osm_base"],
         "query": OVERPASS_QUERY,
         "note": "The Overpass result is a dated snapshot of OpenStreetMap (osm_base above); fetching again gives "
                 "newer data. The query text was not saved with the result: this one is rebuilt from the "
                 "investigation's notes (bounding box 34.4,70.8,37.6,76.6; natural=water except rivers) and matches "
                 "the result (2,419 ways and 35 relations, all natural=water, none water=river)."},
    ]
    for level in ("ADM0", "ADM1", "ADM2"):
        meta = json.loads((dl / "gb" / f"meta_{level}.json").read_text(encoding="utf-8"))
        out.append({"id": f"geoboundaries_{level.lower()}", "name": f"geoBoundaries gbOpen PAK {level} "
                    f"({meta['boundaryCanonical']}, {meta['boundaryYearRepresented']})",
                    "url": GB_API.format(level=level), "download_url": meta["gjDownloadURL"],
                    "file": f"gb/{level}.geojson", "licence": meta["boundaryLicense"],
                    "attribution": f"geoBoundaries (Runfola et al. 2020); source: {meta['boundarySource']}",
                    "fetched": "2026-11-11", "build": meta["buildDate"]})
    out.append({"id": "hmaglofdb", "name": "HMAGLOFDB v1.3.0, High Mountain Asia GLOF database (Shrestha et al. "
                "2023, ESSD 15:3941)", "url": "https://api.github.com/repos/fidelsteiner/HMAGLOFDB/zipball/"
                "1d975defe128dc66f5d342f42bc54b9a731cfc29", "doi": "https://doi.org/10.5281/zenodo.18257243",
                "file": str(hmaglofdb), "licence": "CC0 1.0", "attribution": "Shrestha et al. 2023",
                "fetched": "2026-11-10"})
    posts = [("suparco_2026_05_20", "glacial-lakes-status-20th-may-2026", "2026-05-22"),
             ("suparco_2026_06_05", "glacial-lakes-status-5th-june-2026", "2026-06-08"),
             ("suparco_2026_07_02", "glof-status-update", "2026-07-02"),
             ("suparco_2026_08_20", "glof-monitoring-status-05-august-2026", "2026-08-20")]
    for sid, slug, published in posts:
        out.append({"id": sid, "name": f"SUPARCO space4climate GLOF post, published {published}",
                    "url": f"https://space4climate.gov.pk/{slug}/", "file": f"suparco/{slug}.html",
                    "licence": SUPARCO_LICENCE, "fetched": "2026-11-11"})
    out.append({"id": "suparco_map_2026_07_01", "name": "SUPARCO GLOF monitoring status map, 1 Jul 2026 (JPEG)",
                "url": "https://space4climate.gov.pk/wp-content/uploads/2026/07/"
                       "GLOF-Monitoring-Status3-1st-July-2026.jpg",
                "file": "suparco/GLOF-Monitoring-Status3-1st-July-2026.jpg", "licence": SUPARCO_LICENCE,
                "fetched": "2026-11-11"})
    for s in out:
        p = Path(s["file"]) if Path(s["file"]).is_absolute() else dl / s["file"]
        s["sha256"] = sha256(p)
        s["file"] = p.name if Path(s["file"]).is_absolute() else s["file"]
    return out


def _clean(geom, tolerance=None, digits=5):
    if tolerance:
        geom = geom.simplify(tolerance)
    return shapely.set_precision(geom, 10 ** -digits)


def districts_geojson(lakefind: Path) -> dict:
    gb = lakefind / "dl" / "gb"
    a0, a1, a2 = (gpd.read_file(gb / f"{lv}.geojson") for lv in ("ADM0", "ADM1", "ADM2"))
    area = box(*DISTRICT_BOX)
    a2 = a2[a2.intersects(area)].copy()
    rp = a2.copy()
    rp["geometry"] = a2.representative_point()
    j = gpd.sjoin(rp, a1[["shapeISO", "shapeName", "geometry"]].rename(
        columns={"shapeISO": "iso1", "shapeName": "adm1_name"}), predicate="within")
    a2 = a2.join(j[["iso1", "adm1_name"]])
    if a2.iso1.isna().any():
        raise SystemExit(f"districts: no province for {list(a2[a2.iso1.isna()].shapeName)}")
    simple = shapely.coverage_simplify(a2.geometry.values, 0.001)  # shared edges stay shared: no gaps
    feats = []
    for (_, r), g in zip(a2.iterrows(), simple):
        feats.append({"type": "Feature", "properties": {
            "level": "ADM2", "name": r.shapeName, "adm1": r.iso1.split("-")[1], "adm1_name": r.adm1_name,
            "shape_id": r.shapeID}, "geometry": mapping(_clean(shapely.make_valid(g)))})
    pak = a0.union_all().intersection(area)
    feats.append({"type": "Feature", "properties": {"level": "ADM0", "name": "Pakistan"},
                  "geometry": mapping(_clean(pak, 0.001))})
    feats.sort(key=lambda f: (f["properties"]["level"], f["properties"]["name"]))
    return {"type": "FeatureCollection",
            "source": ("geoBoundaries gbOpen PAK ADM2 and ADM1 (public domain) and ADM0 (from OpenStreetMap, ODbL 1.0, "
                       "© OpenStreetMap contributors), release 9469f09, built 12 Dec 2023; districts whose "
                       f"geometry meets {DISTRICT_BOX} (lon/lat box), simplified to 0.001° keeping shared edges; "
                       "adm1 = the province holding the district's representative point"),
            "features": feats}


def suparco_rows(path: Path) -> dict[int, dict]:
    """The first suparco_match.csv row of each ID (SUPARCO's areas are per ID)."""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.setdefault(int(r["suparco_id"]), r)
    return out


def _note_parts(note: str) -> tuple[str | None, tuple[str, str, str] | None]:
    labels = re.search(r"dot labels unclear: ([\d/]+)", note or "")
    dot = re.search(r"map dot ([\d.]+),([\d.]+), ([\d.]+) km from outline", note or "")
    return (labels.group(1) if labels else None), (dot.groups() if dot else None)


def suparco_matches(c, supa: dict[int, dict]) -> tuple[dict | None, list[dict]]:
    """(suparco, suparco_candidates) of a candidate row: one probable ID is the lake's; anything else is a candidate."""
    if pd.isna(c.suparco_id) or not str(c.suparco_id).strip():
        return None, []
    ids = [int(x) for x in str(c.suparco_id).split("/")]
    labels, dot = _note_parts(c.suparco_note)
    out = []
    for sid in ids:
        s = supa[sid]
        where = (f"has a dot at {dot[0]} E, {dot[1]} N, {dot[2]} km from this lake's outline" if dot
                 else "has a dot near this lake")
        label = (f"whose label could be any of {labels.replace('/', ', ')}" if labels else f"labelled {sid}")
        area = (f"SUPARCO's table gives ID {sid} {s['suparco_area_aug']} km² in Jul-Aug 2026 and "
                f"{s['suparco_max2025']} km² as the 2025 maximum" if s["suparco_area_aug"]
                else f"SUPARCO's table gives no area for ID {sid}")
        match = "possible" if len(ids) > 1 else c.suparco_conf
        out.append({"id": sid, "match": match, "source": (
            f"Reconstructed by SARtale, not published by SUPARCO: SUPARCO's 1 Jul 2026 GLOF status map {where}, "
            f"{label}; {area}. {match.capitalize()} match by map position and area (see suparco_method).")})
    if len(out) == 1 and out[0]["match"] == "probable":
        return out[0], []
    return None, out


def outline_areas(c) -> list[dict]:
    out = []
    if pd.notna(c.area_2020_hkhpk):
        out.append({"source": "HKH-PK-2020 (PlanetScope outline, Sep 2020)", "year": 2020,
                    "km2": round(float(c.area_2020_hkhpk), 4), "licence": "CC BY 4.0"})
    if pd.notna(c.himag_max_2008_2017):
        out.append({"source": "Hi-MAG (Landsat 30 m outline)", "year": int(c.himag_max_year),
                    "km2": round(float(c.himag_max_2008_2017), 4), "licence": "CC BY 4.0"})
    if pd.notna(c.area_osm):
        out.append({"source": "OpenStreetMap outline (undated)", "year": None, "km2": round(float(c.area_osm), 4),
                    "licence": "ODbL 1.0"})
    return out


def _txt(v) -> str:
    return "" if pd.isna(v) else str(v).strip()


def coord_source(c, rid: str, supa: dict[int, dict]) -> str:
    """regbatch.py's template, for every outline source, point kind and match kind."""
    src = c.outline_source
    if src.startswith("HKH-PK"):
        outline = (f"HKH-PK-2020 outline (Zenodo 15476013, CC BY 4.0; PlanetScope, Sep 2020; "
                   f"{c.area_2020_hkhpk:.3f} km²)")
    elif src.startswith("OpenStreetMap"):
        outline = f"OpenStreetMap outline {c.osm_id} (ODbL; undated; {c.area_osm:.3f} km²)"
    else:
        outline = f"Hi-MAG outline {c.himag_id} (Zenodo 4275164, CC BY 4.0; Landsat, 2017; {c.area_2017_himag:.3f} km²)"
    head = (f"Centroid of the {outline}" if c.point_kind == "centroid"
            else f"A point inside the {outline}, whose centroid falls outside the lake")
    same = []
    if _txt(c.himag_id) and not src.startswith("Hi-MAG"):
        same.append(f"Hi-MAG {c.himag_id} (Zenodo 4275164, CC BY 4.0), {c.area_2017_himag:.3f} km² in 2017"
                    if pd.notna(c.area_2017_himag) else f"Hi-MAG {c.himag_id} (Zenodo 4275164, CC BY 4.0)")
    if _txt(c.osm_id) and not src.startswith("OpenStreetMap"):
        same.append(f"OSM {c.osm_id} (ODbL)")
    parts = [head]
    if same:
        parts.append("the same lake as " + " and ".join(same))
    parts.append(f"open water in Sentinel-2 on {c.s2_date} ({c.s2_water_buf100_km2:.2f} km²)")
    if _txt(c.suparco_id):
        ids = str(c.suparco_id).split("/")
        if len(ids) == 1:
            parts.append(f"SUPARCO PDGL ID {ids[0]} ({c.suparco_conf} match by map position and area; SUPARCO gives "
                         f"{supa[int(ids[0])]['suparco_area_aug']} km² in Jul-Aug 2026 and "
                         f"{supa[int(ids[0])]['suparco_max2025']} km² as the 2025 maximum)")
        else:
            areas = ", ".join(f"{supa[int(i)]['suparco_area_aug']} km² for ID {i}" for i in ids)
            parts.append(f"SUPARCO PDGL ID {' or '.join(ids)} (possible match by map position and area; the map "
                         f"labels at this dot are unclear, so which ID is not settled; SUPARCO gives {areas} in "
                         "Jul-Aug 2026)")
    if rid == "borith":
        parts.append("an HMAGLOFDB event (Ghulkin, 2007) has its lake point within 1 km, but SARtale's location "
                     "check (10 Nov 2026) found that Borith Lake is not that event's source")
    elif _txt(c.glof_events):
        dam = _txt(c.dam_type).replace("HMAGLOFDB: ", "").lower()
        parts.append(f"HMAGLOFDB v1.3.0 (CC0) records an outburst in {_txt(c.glof_last)} whose lake point is within "
                     f"1 km (dam type there: {dam})")
    return "; ".join(parts)


def outline_feature(geom, c, name: str) -> dict:
    src = c.outline_source
    lic = "CC BY 4.0" if "CC BY" in src else ("ODbL 1.0" if "OpenStreetMap" in src else "")
    if not lic:
        raise SystemExit(f"{c.cand_id}: no licence for outline source {src!r}")
    return {"type": "Feature", "properties": {"name": name, "source": f"{src}; candidate {c.cand_id}, fetched "
                                              f"{FETCHED}", "licence": lic},
            "geometry": mapping(_clean(geom.simplify(0.00002), digits=6))}


def mapped_lakes(cands: pd.DataFrame, geoms: gpd.GeoDataFrame, points: list[tuple[float, float]], built: str,
                 supa_probable: set[int]) -> dict:
    g = geoms.to_crs(UTM)
    pts = gpd.GeoSeries(gpd.points_from_xy([p[0] for p in points], [p[1] for p in points]), crs=4326).to_crs(UTM)
    near = {cid for cid, geom in zip(g.index, g.geometry) if pts.distance(geom).min() <= MAPPED_EXCLUDE_M}
    lakes = []
    for c in cands.sort_values("rank").itertuples():
        if c.cand_id in near:
            continue
        src = c.outline_source
        if src.startswith("HKH-PK"):
            source, km2, year = "hkhpk2020", c.area_2020_hkhpk, 2020
        elif src.startswith("Hi-MAG"):
            source, km2, year = "himag", c.area_2017_himag, 2017
        else:
            source, km2, year = "osm", c.area_osm, None
        sid = _txt(c.suparco_id)
        suparco = ({"id": int(sid), "match": "probable"}
                   if c.suparco_conf == "probable" and sid.isdigit() and int(sid) in supa_probable else None)
        lakes.append({"id": f"m{len(lakes) + 1:04d}", "lon": round(float(c.lon), 5), "lat": round(float(c.lat), 5),
                      "km2": round(float(km2), 3), "year": year, "source": source, "suparco": suparco})
    return {
        "version": 1, "built": built,
        "notice": {
            "odbl": "Lakes with source osm: © OpenStreetMap contributors, available under the Open Database "
                    "Licence (ODbL) 1.0, https://www.openstreetmap.org/copyright.",
            "cc_by": "Lakes with source hkhpk2020: HKH-PK-2020, Siddique et al. 2023 (Zenodo 15476013); source himag: "
                     "Hi-MAG, Chen et al. 2021, ESSD 13:741 (Zenodo 4275164). Both CC BY 4.0.",
            "suparco": "SUPARCO IDs are SARtale's probable matches, reconstructed from SUPARCO's 1 Jul 2026 GLOF "
                       "status map and area table; SUPARCO publishes no coordinates for its list."},
        "sources": [
            {"id": "hkhpk2020", "name": "HKH-PK-2020 glacial lake inventory", "licence": "CC BY 4.0",
             "attribution": "Siddique et al. 2023, Zenodo 15476013", "url": ZENODO_HKHPK},
            {"id": "himag", "name": "Hi-MAG glacial lake database", "licence": "CC BY 4.0",
             "attribution": "Chen et al. 2021, Earth Syst. Sci. Data 13:741, Zenodo 4275164", "url": ZENODO_HIMAG},
            {"id": "osm", "name": "OpenStreetMap", "licence": "ODbL 1.0", "attribution": "© OpenStreetMap contributors",
             "url": "https://www.openstreetmap.org/copyright"}],
        "lakes": lakes}


def fill_register(path: Path) -> list[str]:
    """Add district, province and district_source to each lakes_in.json row that lacks them, as a third line of the
    row, keeping the rest of the file byte for byte."""
    text = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    done = []
    for row in json.loads(text):
        if row.get("district"):
            continue
        name, prov, km = districts.locate(row["lon"], row["lat"])
        start = text.index('{"id": ' + json.dumps(row["id"]))
        nxt = text.find(nl + '  {"id": ', start)
        end = (nxt if nxt != -1 else text.rindex("]"))
        close = text.rindex("}", start, end)
        add = {"district": name, "province": prov, "district_source": district_source(km)}
        line = ", ".join(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in add.items())
        text = text[:close] + "," + nl + "   " + line + text[close:]
        done.append(f"{row['id']}: {name} ({prov}{f', {km:.1f} km outside' if km else ''})")
    rows = json.loads(text)
    assert all(r.get("district") for r in rows)
    path.write_bytes(text.encode("utf-8"))
    return done


def district_source(km: float) -> str:
    if km <= 0:
        return districts.DISTRICT_SOURCE
    return (f"{districts.DISTRICT_SOURCE}; the point is {km:.1f} km outside the coarse district polygons but inside "
            "Pakistan's outline, so the nearest district is given")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lakefind", required=True, type=Path)
    ap.add_argument("--hmaglofdb", type=Path, help="HMAGLOFDB zipball (default: <lakefind>/../lakeloc/dl/hma/hma.zip)")
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--outlines", type=Path, default=PROCESSING / "outlines")
    ap.add_argument("--app-data", type=Path, default=REPO / "app" / "public" / "data")
    ap.add_argument("--lakes-in", type=Path, default=PROCESSING / "lakes_in.json")
    ap.add_argument("--fill-register", action="store_true")
    args = ap.parse_args(argv)
    lf, out = args.lakefind.resolve(), args.out.resolve()
    hma = (args.hmaglofdb or lf.parent / "lakeloc" / "dl" / "hma" / "hma.zip").resolve()
    built = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.mkdir(parents=True, exist_ok=True)

    for name in ("lake_candidates.csv", "suparco_match.csv"):
        shutil.copyfile(lf / name, out / name)
    (out / "sources.json").write_text(json.dumps(sources(lf, hma), ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    dpath = out / "districts.geojson"
    dpath.write_text(json.dumps(districts_geojson(lf), ensure_ascii=False, separators=(",", ":")) + "\n",
                     encoding="utf-8")
    districts._load.cache_clear()

    cands = pd.read_csv(lf / "lake_candidates.csv").set_index("cand_id", drop=False)
    geoms = gpd.read_file(lf / "lake_candidates.geojson")[["cand_id", "geometry"]].set_index("cand_id")
    supa = suparco_rows(lf / "suparco_match.csv")
    supa_probable = {int(r["suparco_id"]) for r in csv.DictReader(open(lf / "suparco_match.csv", encoding="utf-8"))
                     if r["confidence"] == "probable"}
    centroids = geoms.to_crs(UTM).centroid.to_crs(4326)

    new_rows, inventory = [], {}
    for batch, cid, rid, name in PICKS:
        c = cands.loc[cid]
        name = name or f"Unnamed lake {cid}"
        if "pdgl" in rid or "PDGL" in name:
            raise SystemExit(f"{rid}: a SUPARCO number in an id or name")
        feature = outline_feature(geoms.loc[cid].geometry, c, name)
        args.outlines.mkdir(parents=True, exist_ok=True)
        (args.outlines / f"{rid}.geojson").write_text(json.dumps(feature, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
        cen = centroids.loc[cid]
        district, province, km = districts.locate(cen.x, cen.y, dpath)
        new_rows.append({"id": rid, "name": name, "lon": round(float(c.lon), 6), "lat": round(float(c.lat), 6),
                         "role": "watch", "coord_source": coord_source(c, rid, supa),
                         "outline": f"outlines/{rid}.geojson", "downstream": None, "downstream_source": None,
                         "district": district, "province": province, "district_source": district_source(km),
                         "batch": batch})
    for rid, cid in [(r, c) for _, c, r, _ in PICKS] + list(SITES.items()):
        c = cands.loc[cid]
        suparco, candidates = suparco_matches(c, supa)
        inventory[rid] = {"cand_id": cid, "outlines": outline_areas(c), "suparco": suparco,
                          "suparco_candidates": candidates}
    (out / "new_lakes.json").write_text(
        "[\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in new_rows) + "\n]\n", encoding="utf-8")
    (out / "watched_inventory.json").write_text(json.dumps(
        {"version": 1, "built": built, "suparco_method": SUPARCO_METHOD,
         "sources": "HKH-PK-2020 (CC BY 4.0), Hi-MAG (CC BY 4.0), OpenStreetMap (ODbL 1.0); see sources.json",
         "lakes": inventory}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    register = json.loads(args.lakes_in.read_text(encoding="utf-8"))
    points = [(r["lon"], r["lat"]) for r in register] + [(r["lon"], r["lat"]) for r in new_rows]
    doc = mapped_lakes(cands, geoms, points, built, supa_probable)
    args.app_data.mkdir(parents=True, exist_ok=True)
    (args.app_data / "mapped_lakes.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n",
                                                     encoding="utf-8")
    if args.fill_register:
        for line in fill_register(args.lakes_in):
            print("register:", line)
    print(f"{len(new_rows)} new lakes, {len(inventory)} inventory entries, {len(doc['lakes'])} mapped lakes "
          f"({len(cands) - len(doc['lakes'])} of {len(cands)} candidates are watched lakes)")
    for r in new_rows:
        print(f"  {r['batch']} {r['id']:16} {r['district']} ({r['province']})"
              + ("" if r["district_source"] == districts.DISTRICT_SOURCE else "  [nearest district]"))


if __name__ == "__main__":
    main()
