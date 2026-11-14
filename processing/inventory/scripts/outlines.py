"""Write one GeoJSON Feature per chosen lake in SARtale's outline format (processing/outlines/*.geojson)."""
import sys, json, warnings; warnings.filterwarnings("ignore")
import geopandas as gpd
S = sys.argv[1]; picks = json.loads(sys.argv[2])  # {"cand_id": "register_id"}
g = gpd.read_file(f"{S}/lake_candidates.geojson").set_index("cand_id")
import os; os.makedirs(f"{S}/outlines", exist_ok=True)
for cid, rid in picks.items():
    r = g.loc[cid]
    src = r.outline_source
    lic = "CC BY 4.0" if "CC BY" in src else ("ODbL 1.0" if "OpenStreetMap" in src else "")
    geom = r.geometry.simplify(0.00002)
    f = {"type": "Feature", "properties": {"name": r["name"] if isinstance(r["name"], str) else rid,
         "source": src + f"; candidate {cid}, fetched 11 Nov 2026", "licence": lic},
         "geometry": json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]}
    json.dump(f, open(f"{S}/outlines/{rid}.geojson", "w", encoding="utf-8"), ensure_ascii=False)
    print(rid, cid, round(r.area_best, 3), src[:40])
