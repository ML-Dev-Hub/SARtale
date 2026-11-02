"""Spike: list NISAR GCOV granules over a lake point and their download URLs (metadata only)."""
import json
import sys
import requests

URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
lat, lon = float(sys.argv[1]), float(sys.argv[2])
items, page = [], 1
while True:
    r = requests.get(URL, params={"short_name": "NISAR_L2_GCOV_PROVISIONAL_V1", "point": f"{lon},{lat}",
                                  "page_size": 2000, "page_num": page, "sort_key": "start_date"}, timeout=120)
    r.raise_for_status()
    got = r.json().get("items", [])
    items += got
    if len(got) < 2000:
        break
    page += 1
out = []
for it in items:
    u = it["umm"]
    urls = [x["URL"] for x in u.get("RelatedUrls", []) if x.get("URL", "").endswith(".h5")]
    out.append({"id": u["GranuleUR"], "start": u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"], "urls": urls})
for o in out:
    p = o["id"].split("_")
    print(o["start"][:10], "track", p[4], p[5], "frame", p[6], "mode", p[7], p[8], "|", (o["urls"][:1] or ["no h5 url"])[0][:110])
json.dump(out, open(sys.argv[3], "w"), indent=1)
print(len(out), "granules")
