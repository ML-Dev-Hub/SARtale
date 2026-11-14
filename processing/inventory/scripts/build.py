import sys, warnings, glob; warnings.filterwarnings("ignore")
import geopandas as gpd, pandas as pd, numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
S = sys.argv[1]; HMA = sys.argv[2]
reg = gpd.read_file(f"{S}/region_pak.gpkg").to_crs(32643).geometry.iloc[0]
k = gpd.read_file(glob.glob(f"{S}/dl/hkhpk/HKH-PK/HKH-PK.shp")[0]).to_crs(32643)
k = k[k.representative_point().within(reg)]; k["src"] = "HKHPK2020"; k["sid"] = "HKHPK:" + k.OBJECTID_1.astype(str); k["a"] = k.area / 1e6
h = gpd.read_file(f"{S}/himag_pak.gpkg").to_crs(32643); h["a"] = h.GL_Area / 1e6
h17 = h[h.year == 2017].copy(); h17["src"] = "HiMAG2017"; h17["sid"] = "HiMAG:" + h17.GL_ID
o = gpd.read_file(f"{S}/osm_water_pak.gpkg").to_crs(32643); o["src"] = "OSM"; o["sid"] = o.osm; o["a"] = o.area_km2
cols = ["src", "sid", "a", "geometry"]
base = pd.concat([k[cols][k.a >= 0.02], h17[cols][h17.a >= 0.02], o[cols][o.a >= 0.02]], ignore_index=True)
base = gpd.GeoDataFrame(base, geometry="geometry", crs=32643)
base["geometry"] = base.geometry.buffer(0)
j = gpd.sjoin(base, gpd.GeoDataFrame(geometry=base.geometry.buffer(30), crs=32643), predicate="intersects")
n = len(base)
m = coo_matrix((np.ones(len(j)), (j.index.values, j.index_right.values)), shape=(n, n))
_, lab = connected_components(m, directed=False); base["cl"] = lab
hy = gpd.sjoin(h[["year", "a", "GL_ID", "GL_Type", "GL_Elev", "geometry"]], base[["cl", "geometry"]], predicate="intersects")
hy = hy.drop_duplicates(["cl", "year", "GL_ID"])
ys = hy.groupby(["cl", "year"]).a.sum().reset_index()
hmax = {cl: (g.a.max(), int(g.loc[g.a.idxmax(), "year"]), len(g)) for cl, g in ys.groupby("cl")}
rows = []
for cl, g in base.groupby("cl"):
    kk, hh, oo = g[g.src == "HKHPK2020"], g[g.src == "HiMAG2017"], g[g.src == "OSM"]
    r = dict(cl=cl, area_2020_hkhpk=round(kk.a.sum(), 4) if len(kk) else None,
             area_2017_himag=round(hh.a.sum(), 4) if len(hh) else None,
             area_osm=round(oo.a.max(), 4) if len(oo) else None)
    if cl in hmax:
        r.update(himag_max_2008_2017=round(hmax[cl][0], 4), himag_max_year=hmax[cl][1], himag_years_present=hmax[cl][2])
    hsub = hy[hy.cl == cl]
    if len(hsub):
        top = hsub.sort_values(["year", "a"], ascending=False).iloc[0]
        r.update(himag_id=top.GL_ID, himag_type=top.GL_Type, elev_m=int(top.GL_Elev), elev_source="Hi-MAG GL_Elev")
    ob = None
    if len(oo):
        ob = o[o.osm.isin(oo.sid)].sort_values("area_km2", ascending=False).iloc[0]
        r.update(osm_id=ob.osm, name=ob["name"], osm_water=ob.water)
    r["hkhpk_ids"] = ";".join(kk.sid) if len(kk) else None
    if len(kk):
        geom, osrc = kk.union_all(), "HKH-PK-2020 (Zenodo 15476013, CC BY 4.0), PlanetScope Sep 2020"
    elif len(oo):
        geom, osrc = oo.sort_values("a").geometry.iloc[-1], f"OpenStreetMap {ob.osm} (ODbL 1.0)"
    else:
        geom, osrc = hh.union_all(), "Hi-MAG 2017 (Zenodo 4275164, CC BY 4.0)"
    r.update(outline_source=osrc, geometry=geom)
    rows.append(r)
L = gpd.GeoDataFrame(rows, geometry="geometry", crs=32643)
L["area_best"] = L[["area_2020_hkhpk", "area_2017_himag", "area_osm"]].max(axis=1)
L = L[L.area_best >= 0.05].copy().reset_index(drop=True)
cen = L.geometry.centroid; rp = L.geometry.representative_point()
inside = np.array([c.within(g) for c, g in zip(cen, L.geometry)])
pts = gpd.GeoSeries([c if i else p for c, p, i in zip(cen, rp, inside)], crs=32643).to_crs(4326)
L["lon"] = pts.x.round(6).values; L["lat"] = pts.y.round(6).values
L["point_kind"] = np.where(inside, "centroid", "inside point (centroid falls outside outline)")
d = pd.read_csv(HMA, encoding="latin1")
d = d[d.Country.astype(str).str.contains("Pakistan")].dropna(subset=["Lat_lake", "Lon_lake"])
E = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.Lon_lake, d.Lat_lake), crs=4326).to_crs(32643)
ej = gpd.sjoin_nearest(E, L[["cl", "geometry"]], max_distance=1000, distance_col="dist")
agg = ej.groupby("cl").agg(glof_events=("GF_ID", "count"), glof_last=("Year_approx", lambda s: max(str(v) for v in s)),
                           glof_lake_type=("Lake_type", "first"), glof_glacier=("Glacier_name", "first"),
                           glof_gfids=("GF_ID", lambda s: ",".join(str(int(v)) for v in s)))
L = L.merge(agg, left_on="cl", right_index=True, how="left")
sm = pd.read_csv(f"{S}/suparco_match.csv"); sm = sm[~sm.confidence.isin(["no match", "rejected"])]
for c in ("suparco_id", "suparco_conf", "suparco_area_aug2026", "suparco_max2025", "suparco_note"):
    L[c] = None
key2cl = {}
for cl, g in base.groupby("cl"):
    for s in g.sid: key2cl[s.replace("HiMAG:", "")] = cl
clset = set(L.cl)
for x in sm.sort_values("confidence", ascending=False).itertuples():  # probable first
    cl = key2cl.get(x.match_key)
    if cl is None or cl not in clset: continue
    i = L.index[L.cl == cl][0]
    note = (x.label_note if isinstance(x.label_note, str) else "") + f" map dot {x.dot_lon:.4f},{x.dot_lat:.4f}, {x.match_dkm} km from outline"
    if L.at[i, "suparco_id"] is None:
        L.at[i, "suparco_id"] = str(int(x.suparco_id)); L.at[i, "suparco_conf"] = x.confidence
        L.at[i, "suparco_area_aug2026"] = x.suparco_area_aug; L.at[i, "suparco_max2025"] = x.suparco_max2025
        L.at[i, "suparco_note"] = note.strip()
    elif L.at[i, "suparco_conf"] == "possible" and x.confidence == "possible" and str(int(x.suparco_id)) not in L.at[i, "suparco_id"].split("/"):
        L.at[i, "suparco_id"] += f"/{int(x.suparco_id)}"
L.to_crs(4326).to_file(f"{S}/lakes_all.gpkg", driver="GPKG")
L.drop(columns="geometry").to_csv(f"{S}/lakes_all.csv", index=False)
print(len(L), "lakes >= 0.05 km2;", L.suparco_id.notna().sum(), "SUPARCO;", L.glof_events.notna().sum(), "HMAGLOFDB;", L.elev_m.isna().sum(), "no elev")
