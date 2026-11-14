import sys, pandas as pd
S = sys.argv[1]
r = pd.read_csv(f"{S}/suparco_match_raw.csv")
def conf(x):
    if pd.isna(x.match_key): return "no match"
    ratio = x.match_area / x.ref_area if x.ref_area else 0
    if x.n_label_cands == 1 and 0.6 <= ratio <= 1.5 and x.match_dkm <= 1.5: return "probable"
    return "possible"
r["confidence"] = r.apply(conf, axis=1)
# for multi-label dots keep the label alternatives in a note
alts = r.groupby("dot").suparco_id.apply(lambda s: "/".join(str(v) for v in s)).to_dict()
r["label_note"] = r.apply(lambda x: f"dot labels unclear: {alts[x["dot"]]}" if x.n_label_cands > 1 else "", axis=1)
# SUPARCO's 5 June 2026 post gives each unfrozen lake's district. Where the map dot falls in another district, the
# label reading is wrong: ID 4 is "Chitral" there, but the dot read as 4 is in Hunza next to Passu Lake.
m4 = r.suparco_id == 4
r.loc[m4, "confidence"] = "rejected"; r.loc[m4, "label_note"] = "SUPARCO 5 Jun 2026 lists ID 4 in Chitral; this Hunza dot's label was misread"
m124 = r.suparco_id == 124
r.loc[m124, "label_note"] = (r.loc[m124, "label_note"] + "; SUPARCO 5 Jun lists ID 124 in Swat, dot falls in Chitral (district boundary data is coarse)").str.strip("; ")
r.to_csv(f"{S}/suparco_match.csv", index=False)
print(r.confidence.value_counts().to_dict())
p = r[(r.confidence == "probable")]
print(p[["suparco_id", "dot_lon", "dot_lat", "ref_area", "match_src", "match_key", "match_area", "match_dkm", "match_name"]].to_string(index=False))
