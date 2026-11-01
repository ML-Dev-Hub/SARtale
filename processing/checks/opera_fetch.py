"""Fetch OPERA DSWx-S1 WTR tiles over the window into data/opera/<day>/, listed in data/opera/opera_index.json.

Uses a plain requests session, as sartale/download.py does. It prints no headers or credentials, and
certificate checks stay on. Run from the repository root:
    conda run -n sartale python processing/checks/opera_fetch.py 2026-06-28 2026-09-15 2026-09-16 2026-09-23 2026-10-05 2026-10-17
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "processing"))
from sartale import config

OUT = ROOT / "data" / "opera"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
session = requests.Session()
index_path = OUT / "opera_index.json"
index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
for day in sys.argv[1:]:
    query = {"short_name": "OPERA_L3_DSWX-S1_V1", "bounding_box": ",".join(str(v) for v in config.WINDOW),
             "temporal": f"{day}T00:00:00Z,{day}T23:59:59Z", "page_size": 100}
    with urllib.request.urlopen(f"{CMR}?{urllib.parse.urlencode(query)}", timeout=60) as r:
        items = json.load(r)["items"]
    folder = OUT / day
    folder.mkdir(parents=True, exist_ok=True)
    index[day] = []
    for item in items:
        urls = [u["URL"] for u in item["umm"].get("RelatedUrls", [])
                if u.get("Type") == "GET DATA" and u["URL"].endswith("_B01_WTR.tif")]
        if not urls:
            continue
        target = folder / Path(urls[0]).name
        index[day].append({"granule": item["umm"]["GranuleUR"], "url": urls[0], "file": target.name})
        if target.exists() and target.stat().st_size:
            continue
        with session.get(urls[0], timeout=(60, 180)) as resp:
            if resp.status_code != 200 or resp.content[:2] not in (b"II", b"MM"):
                raise ValueError(f"HTTP {resp.status_code} or not a TIFF: {target.name}")
            target.write_bytes(resp.content)
index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
print({d: len(v) for d, v in index.items()})
