import sys, json, warnings; warnings.filterwarnings("ignore")
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import polygonize, unary_union
from shapely.geometry import LineString
S = sys.argv[1]
d = json.load(open(f"{S}/dl/osm/osm_water.json", encoding="utf-8"))
rows = []
for e in d["elements"]:
    t = e.get("tags", {})
    try:
        if e["type"] == "way":
            c = [(p["lon"], p["lat"]) for p in e["geometry"]]
            if len(c) < 4 or c[0] != c[-1]: continue
            g = Polygon(c)
        else:
            outers = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in e["members"] if m.get("role") == "outer" and m.get("geometry")]
            inners = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in e["members"] if m.get("role") == "inner" and m.get("geometry")]
            o = unary_union(list(polygonize(unary_union(outers))))
            if inners:
                o = o.difference(unary_union(list(polygonize(unary_union(inners)))))
            g = o
        if g.is_empty: continue
        if not g.is_valid: g = g.buffer(0)
    except Exception as ex:
        continue
    rows.append(dict(osm=f"{e['type']}/{e['id']}", name=t.get("name:en") or t.get("name"), name_local=t.get("name"), water=t.get("water"), geometry=g))
g = gpd.GeoDataFrame(rows, crs=4326)
g["area_km2"] = g.to_crs(6933).area / 1e6
c = g.to_crs(32643).centroid.to_crs(4326); g["lon"] = c.x; g["lat"] = c.y
g = g[g.area_km2 >= 0.01]
g.to_file(f"{S}/osm_water_region.gpkg", driver="GPKG")
print(len(g), g.water.value_counts(dropna=False).head(8).to_dict()); print(g.sort_values("area_km2", ascending=False).head(15)[["osm","name","water","area_km2","lon","lat"]].to_string())
