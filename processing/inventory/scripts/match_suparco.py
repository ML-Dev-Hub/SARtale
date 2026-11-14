import sys, json, warnings; warnings.filterwarnings("ignore")
import geopandas as gpd, pandas as pd
from shapely.geometry import Point
S = sys.argv[1]
dots = json.load(open(f"{S}/dots_geo.json")); labels = json.load(open(f"{S}/suparco_labels.json"))
areas = {int(k): v for k, v in json.load(open(f"{S}/suparco_areas.json")).items()}
h = gpd.read_file(f"{S}/himag_pak.gpkg"); h = h[h.year == 2017][["GL_ID", "GL_Area", "GL_Type", "GL_Elev", "geometry"]]
h["src"] = "Hi-MAG2017"; h["key"] = h.GL_ID; h["akm"] = h.GL_Area / 1e6; h["name"] = None
o = gpd.read_file(f"{S}/osm_water_pak.gpkg"); o["src"] = "OSM"; o["key"] = o.osm; o["akm"] = o.area_km2
L = pd.concat([h[["src", "key", "akm", "name", "geometry"]], o[["src", "key", "akm", "name", "geometry"]]]).to_crs(32643)
L = gpd.GeoDataFrame(L, geometry="geometry", crs=32643)
rows = []
for k, ids in labels.items():
    d = dots[int(k)]
    p = gpd.GeoSeries([Point(d["lon"], d["lat"])], crs=4326).to_crs(32643).iloc[0]
    near = L[L.distance(p) < 2500].copy(); near["dkm"] = near.distance(p) / 1000
    for sid in ids:
        a = areas.get(sid, {})
        ref = max([a.get(x, 0) for x in ("area_aug", "max2025", "area_jun", "max2025_b", "max2025_c")] or [0])
        best = None
        if ref > 0:
            c = near[(near.akm > ref / 2) & (near.akm < ref * 2)].sort_values("dkm")
            if len(c):
                b = c.iloc[0]; best = (b.src, b.key, round(b.akm, 3), round(b.dkm, 2), b["name"], len(c))
        rows.append(dict(suparco_id=sid, dot=int(k), colour=d["colour"], dot_lon=d["lon"], dot_lat=d["lat"], n_label_cands=len(ids),
                         suparco_area_aug=a.get("area_aug"), suparco_max2025=a.get("max2025") or a.get("max2025_c") or a.get("max2025_b"), ref_area=ref,
                         match_src=best[0] if best else None, match_key=best[1] if best else None, match_area=best[2] if best else None,
                         match_dkm=best[3] if best else None, match_name=best[4] if best else None, n_area_ok=best[5] if best else 0))
r = pd.DataFrame(rows).sort_values("suparco_id")
r.to_csv(f"{S}/suparco_match_raw.csv", index=False)
pd.set_option("display.width", 250)
print(r[r.ref_area >= 0.05].to_string(index=False))
