"""NISAR GCOV coverage per candidate lake: public CMR point search (no credentials) of both GCOV collections,
mode 4005, polarisation DHDH, passes from 2026-06-17. Uses SARtale's own search code read-only."""
import sys, json, csv
from types import SimpleNamespace
import requests
sys.path.insert(0, r"I:\SARtale\processing")
from sartale.lake_catalog import search_lake_passes, CALIBRATED_FROM, MODE  # noqa: E402
from sartale.catalog import parse_granule  # noqa: E402

S = sys.argv[1]; src = sys.argv[2]; out = sys.argv[3]
rows = list(csv.DictReader(open(src, encoding="utf-8")))
sess = requests.Session()
res = []
for r in rows:
    lake = SimpleNamespace(id=r["cand_id"], lon=float(r["lon"]), lat=float(r["lat"]))
    ps = search_lake_passes(lake, sess)
    keep = [p for p in ps if p.mode == MODE and p.date >= CALIBRATED_FROM and parse_granule(p.granule).pole == "DHDH"]
    tracks = {}
    for p in keep:
        tracks.setdefault(p.key, []).append(p.date)
    res.append(dict(cand_id=r["cand_id"], n_all=len(ps), n_4005_dhdh=len(keep),
                    tracks={k: len(v) for k, v in sorted(tracks.items())},
                    latest=max((p.date for p in keep), default=None)))
    print(res[-1], flush=True)
json.dump(res, open(out, "w"), indent=0)
