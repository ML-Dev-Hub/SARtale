import pandas as pd, json, sys
S = sys.argv[1]
c = pd.read_csv(f"{S}/lake_candidates.csv").set_index("cand_id")
picks = [("C001", "karambar_lake", "Karambar (Qurumbar) Lake, Karambar Pass"), ("C002", "khukush", "Khukush Lake (Ghizer)"),
         ("C003", "shandur", "Shandur Lake"), ("C004", "bashkar_gol", "Bashkar Gol lake (Upper Chitral)"),
         ("C005", "atro_sar", "Atro Sar (Ishkoman, Ghizer)"), ("C006", "ghizer_pdgl98", "Unnamed lake, Ghizer (SUPARCO PDGL 98)"),
         ("C007", "diamer_pdgl84", "Unnamed lake, Diamer-Ghizer divide (SUPARCO PDGL 84)"), ("C008", "zhagi_chhat", "Zhagi Chhat (Upper Chitral)"),
         ("C009", "andrab", "Andrab Lake (Swat)"), ("C010", "ghizer_pdgl60", "Unnamed lake, Ghizer (SUPARCO PDGL 60)"),
         ("C011", "kohistan_pdgl20", "Unnamed lake, Kohistan (SUPARCO PDGL 20)"), ("C012", "astore_pdgl78", "Unnamed lake, Astore (SUPARCO PDGL 78)"),
         ("C013", "ghizer_pdgl62", "Unnamed lake, Ghizer (SUPARCO PDGL 62)"), ("C014", "rama", "Rama Lake (Astore)"),
         ("C015", "kharmang_pdgl71", "Unnamed lake, Kharmang (SUPARCO PDGL 71)"), ("C022", "katora", "Katora Lake (Kumrat, Upper Dir)")]
out = []
for cid, rid, name in picks:
    r = c.loc[cid]
    hm = f"Hi-MAG {r.himag_id} (Zenodo 4275164, CC BY 4.0), {r.area_2017_himag:.3f} km² in 2017" if pd.notna(r.area_2017_himag) else f"Hi-MAG {r.himag_id}"
    osm = f" and OSM {r.osm_id} (ODbL)" if isinstance(r.osm_id, str) else ""
    sup = (f"SUPARCO PDGL ID {r.suparco_id} ({r.suparco_conf} match by map position and area; SUPARCO gives "
           f"{r.suparco_area_aug2026} km² in Jul-Aug 2026 and {r.suparco_max2025} km² as the 2025 maximum)")
    cs = (f"Centroid of the HKH-PK-2020 outline (Zenodo 15476013, CC BY 4.0; PlanetScope, Sep 2020; {r.area_2020_hkhpk:.3f} km²); "
          f"the same lake as {hm}{osm}; open water in Sentinel-2 on {r.s2_date} ({r.s2_water_buf100_km2:.2f} km²); {sup}")
    out.append({"id": rid, "name": name, "lon": round(float(r.lon), 6), "lat": round(float(r.lat), 6), "role": "watch", "coord_source": cs,
                "outline": f"outlines/{rid}.geojson", "downstream": None, "downstream_source": None})
open(f"{S}/register_batch.json", "w", encoding="utf-8").write("[\n" + ",\n".join("  " + json.dumps(o, ensure_ascii=False) for o in out) + "\n]\n")
for cid, rid, name in picks:
    r = c.loc[cid]
    print(f"| {rid} | {name} | {r.lon:.6f} | {r.lat:.6f} | {r.area_2020_hkhpk:.3f} (2020) | {r.suparco_id} ({r.suparco_conf}) | {r.s2_date}: {r.s2_water_buf100_km2:.2f} | {r.nisar_tracks} |")
