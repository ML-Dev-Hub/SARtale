import sys, json, warnings; warnings.filterwarnings("ignore")
import pandas as pd, geopandas as gpd, numpy as np
S = sys.argv[1]
L = pd.read_csv(f"{S}/lakes_all.csv")
g = gpd.read_file(f"{S}/lakes_all.gpkg")[["cl", "geometry"]]
reg = json.load(open(r"I:\SARtale\processing\lakes_in.json", encoding="utf-8"))
L["elev_best"] = L.elev_m.fillna(L.dem_m)
L["elev_src"] = np.where(L.elev_m.notna(), "Hi-MAG GL_Elev", "Copernicus GLO-30 at point")
L = L[(L.elev_best >= 2500) | L.suparco_id.notna()]
tier = np.select([L.suparco_conf == "probable", L.suparco_conf == "possible", L.glof_events.notna()], [1, 2, 3], 4)
L["tier"] = tier
L = L.sort_values(["tier", "area_best"], ascending=[True, False]).reset_index(drop=True)
L["rank"] = np.arange(1, len(L) + 1)
L["cand_id"] = ["C%03d" % i for i in L["rank"]]
def near_reg(r):
    for x in reg:
        if np.hypot((x["lon"] - r.lon) * 90.2, (x["lat"] - r.lat) * 111.3) < 1.0: return x["id"]
    return None
L["in_register"] = L.apply(near_reg, axis=1)
def areatxt(r):
    p = []
    if pd.notna(r.area_2020_hkhpk): p.append(f"{r.area_2020_hkhpk:.3f} (2020, HKH-PK)")
    if pd.notna(r.area_2017_himag): p.append(f"{r.area_2017_himag:.3f} (2017, Hi-MAG)")
    if pd.notna(r.area_osm): p.append(f"{r.area_osm:.3f} (OSM, undated)")
    return "; ".join(p)
L["area_text"] = L.apply(areatxt, axis=1)
def srcl(r):
    s = []
    if pd.notna(r.area_2020_hkhpk): s.append("HKH-PK-2020 CC BY 4.0")
    if pd.notna(r.area_2017_himag) or pd.notna(r.himag_id): s.append("Hi-MAG CC BY 4.0")
    if pd.notna(r.osm_id): s.append("OSM ODbL")
    if pd.notna(r.glof_events): s.append("HMAGLOFDB CC0")
    if pd.notna(r.suparco_id): s.append("SUPARCO space4climate (no licence stated)")
    return "; ".join(s)
L["sources"] = L.apply(srcl, axis=1)
L["dam_type"] = np.where(L.glof_lake_type.notna(), "HMAGLOFDB: " + L.glof_lake_type.astype(str),
                         np.where(L.himag_type.notna(), "not given; Hi-MAG class: " + L.himag_type.astype(str), "not given"))
L["pdgl_list"] = np.where(L.suparco_id.notna(), "SUPARCO PDGL " + L.suparco_id.astype(str) + " (" + L.suparco_conf.astype(str) + " match)", "")
L["downstream"] = ""  # no source in these datasets gives a settlement per lake
cols = ["cand_id", "rank", "tier", "name", "lon", "lat", "point_kind", "area_best", "area_text", "himag_max_2008_2017", "himag_max_year",
        "elev_best", "elev_src", "dam_type", "himag_id", "osm_id", "hkhpk_ids", "outline_source", "pdgl_list", "suparco_id", "suparco_conf",
        "suparco_area_aug2026", "suparco_max2025", "suparco_note", "glof_events", "glof_last", "glof_glacier", "glof_gfids", "in_register", "downstream", "sources", "cl"]
L[cols].to_csv(f"{S}/candidates_ranked.csv", index=False, encoding="utf-8")
G = g.merge(L[cols], on="cl").sort_values("rank")
G.to_file(f"{S}/candidates_ranked.geojson", driver="GeoJSON")
print(len(L), L.tier.value_counts().sort_index().to_dict())
pd.set_option("display.width", 250)
print(L[cols[:6] + ["area_best", "elev_best", "suparco_id", "suparco_conf", "glof_glacier", "in_register"]].head(45).to_string(index=False))
