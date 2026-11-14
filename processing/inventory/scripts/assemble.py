import sys, json, glob, warnings; warnings.filterwarnings("ignore")
import pandas as pd, geopandas as gpd
S = sys.argv[1]
C = pd.read_csv(f"{S}/candidates_ranked.csv")
v1 = pd.read_csv(f"{S}/candidates_ranked_v1.csv")[["cand_id", "cl"]].rename(columns={"cand_id": "old"})
N = pd.DataFrame(json.load(open(f"{S}/nisar.json"))).rename(columns={"cand_id": "old"}).merge(v1, on="old")
N["nisar_tracks"] = N.tracks.apply(lambda t: " ".join(f"{k}x{v}" for k, v in t.items()))
N["nisar_n_tracks"] = N.tracks.apply(len)
N = N[["cl", "n_4005_dhdh", "nisar_n_tracks", "nisar_tracks", "latest"]].rename(columns={"n_4005_dhdh": "nisar_passes_4005_dhdh", "latest": "nisar_latest"})
V = []
for f in glob.glob(f"{S}/vres3/C*.json"):
    for r in json.load(open(f)):
        sec = r.get("second") or {}
        V.append(dict(cand_id=r["cand_id"], s2_date=r.get("date"), s2_scene=r.get("scene"), s2_lake_cloud_snow=r.get("lake_bad_frac"),
                      s2_valid_in=r.get("valid_in"), s2_water_in_km2=r.get("water_in_km2"), s2_water_buf100_km2=r.get("water_buf100_km2"),
                      s2_outline_km2=r.get("outline_km2"), s2_water_frac=r.get("water_frac"),
                      s2_icy_in_km2=r.get("icy_in_km2"), s2_date2=sec.get("date"), s2_water_buf100_km2_2=sec.get("water_buf100_km2"), s2_error=r.get("error")))
V = pd.DataFrame(V)
def verdict(r):
    if pd.isna(r.s2_water_buf100_km2): return "not checked"
    w = max(r.s2_water_buf100_km2, r.s2_water_buf100_km2_2 if pd.notna(r.s2_water_buf100_km2_2) else 0)
    if r.s2_valid_in < 0.7 and w < 0.05: return "inconclusive (cloud/snow)"
    if w >= 0.05 and (r.s2_water_frac or 0) >= 0.3: return "open water"
    if w >= 0.02: return "partly water"
    return "little or no water"
if len(V):
    V["s2_verdict"] = V.apply(verdict, axis=1)
    C = C.merge(V, on="cand_id", how="left")
C = C.merge(N, on="cl", how="left")
C.to_csv(f"{S}/lake_candidates.csv", index=False, encoding="utf-8")
g = gpd.read_file(f"{S}/candidates_ranked.geojson")[["cand_id", "geometry"]].merge(C, on="cand_id")
g.to_file(f"{S}/lake_candidates.geojson", driver="GeoJSON")
if len(V):
    print(C[C.s2_verdict.notna()].s2_verdict.value_counts().to_dict())
    pd.set_option("display.width", 260)
    print(C[C.s2_verdict.notna()][["cand_id", "name", "area_best", "suparco_id", "s2_date", "s2_valid_in", "s2_water_in_km2", "s2_water_buf100_km2", "s2_water_frac", "s2_water_buf100_km2_2", "s2_verdict", "nisar_tracks"]].to_string(index=False))
