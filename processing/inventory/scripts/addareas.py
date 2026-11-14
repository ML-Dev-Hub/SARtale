import sys, pandas as pd
S = sys.argv[1]
c = pd.read_csv(f"{S}/lake_candidates.csv")
a = pd.read_csv(f"{S}/lakes_all.csv")[["cl", "area_2020_hkhpk", "area_2017_himag", "area_osm"]]
c = c.drop(columns=[x for x in ("area_2020_hkhpk", "area_2017_himag", "area_osm") if x in c]).merge(a, on="cl", how="left")
c.sort_values("rank").to_csv(f"{S}/lake_candidates.csv", index=False, encoding="utf-8")
print(len(c))
