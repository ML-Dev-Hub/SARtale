"""Sentinel-2 L2A (Earth Search, public) open-water check for candidate lakes, summer 2026.
For each lake: rank Jul-Sep 2026 scenes by SCL cloud/snow/no-data over a window around the outline, take the
clearest scene, compute water (MNDWI>0.1 & NDWI>0, not snow/cloud) inside the outline and inside outline+100 m,
and save a chip PNG with the outline drawn."""
import sys, json, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[4])  # lakeloc/scripts (s2lib)
import numpy as np, geopandas as gpd
from rasterio.features import rasterize
from rasterio.transform import Affine
from rasterio.enums import Resampling
from PIL import Image, ImageDraw
import s2lib
from s2lib import grid_around, scenes, read_band, full_read, s2_water

S = sys.argv[1]; ids = sys.argv[2].split(","); out = sys.argv[3]
G = gpd.read_file(f"{S}/candidates_ranked.geojson").set_index("cand_id")
res = []
for cid in ids:
    r = G.loc[cid]
    from shapely import force_2d
    geom = gpd.GeoSeries([force_2d(r.geometry)], crs=4326).to_crs(32643).iloc[0]
    minx, miny, maxx, maxy = geom.bounds
    half = max(maxx - minx, maxy - miny) / 2000 + 0.6
    x, y, epsg = grid_around(r.lon, r.lat, half, 10.0)
    tf = Affine(10, 0, x[0] - 5, 0, -10, y[0] + 5)
    inside = rasterize([(geom, 1)], out_shape=(len(y), len(x)), transform=tf).astype(bool)
    buf = rasterize([(geom.buffer(100), 1)], out_shape=(len(y), len(x)), transform=tf).astype(bool)
    try:
        sc = scenes(r.lon, r.lat, "2026-07-01", "2026-09-30", half_km=half, max_tile_cloud=70)
    except Exception as e:
        res.append(dict(cand_id=cid, error=str(e))); print(cid, "ERR", e); continue
    best = []
    seen = set()
    sc = sorted([s for s in sc if s["cloud"] <= 25], key=lambda s: s["cloud"])[:8] or sorted(sc, key=lambda s: s["cloud"])[:4]
    for s in sc:
        key = s["date"]
        if key in seen: continue
        try:
            scl = read_band(s, "scl", x[::2], y[::2], epsg, how=Resampling.nearest, reflect=False)
        except Exception:
            continue
        ins = inside[::2, ::2]
        bad = np.isin(scl, (0, 1, 3, 8, 9, 10))
        snow = scl == 11
        badl = (bad | snow)[ins].mean() if ins.any() else 1
        seen.add(key)
        best.append((badl, bad.mean(), s))
        if badl < 0.02 and len(best) >= 2: break
    if not best:
        res.append(dict(cand_id=cid, error="no scenes")); print(cid, "no scenes"); continue
    best.sort(key=lambda t: (round(t[0], 2), t[1]))
    rows = []
    for badl, badw, s in best[:2]:
        d = full_read(s, x, y, epsg)
        w0, valid = s2_water(d)
        # Deep clear or weedy lakes are very dark in every band and fail MNDWI/NDWI (Karambar edges, Shandur, the
        # black lake of SUPARCO 84). Add SCL water and a dark-water rule (NIR < 0.04 and SWIR1 < 0.03, valid pixel).
        dark = (d["nir"] < 0.04) & (d["swir"] < 0.03) & valid & ~np.isin(d["scl"], (11,))
        w = (w0 | ((d["scl"] == 6) & valid) | dark) & (d["green"] < 0.25)  # green >= 0.25 is snow/ice, not open water
        icy = (w0 & (d["green"] >= 0.25))
        v_in = valid[inside].mean()
        wa_in = w[inside].sum() * 1e-4; wa_buf = w[buf].sum() * 1e-4
        rows.append(dict(date=s["date"], scene=s["id"], lake_bad_frac=round(float(badl), 3), valid_in=round(float(v_in), 3),
                         water_in_km2=round(float(wa_in), 4), water_buf100_km2=round(float(wa_buf), 4),
                         outline_km2=round(float(inside.sum() * 1e-4), 4), water_frac=round(float(w[inside].mean()), 3), bright_rule_km2=round(float(w0[buf].sum() * 1e-4), 4), icy_in_km2=round(float(icy[inside].sum() * 1e-4), 4)))
        if len(rows) == 1:
            rgb = np.nan_to_num(d["rgb"]).transpose(1, 2, 0)
            rgb = np.clip(rgb * 1.4, 0, 255).astype(np.uint8)
            im = Image.fromarray(rgb).convert("RGB")
            ov = np.zeros((len(y), len(x), 4), np.uint8); ov[w] = (0, 255, 255, 110)
            im = Image.alpha_composite(im.convert("RGBA"), Image.fromarray(ov)).convert("RGB")
            dr = ImageDraw.Draw(im)
            for poly in getattr(geom, "geoms", [geom]):
                cs = [((px - (x[0] - 5)) / 10, ((y[0] + 5) - py) / 10) for px, py in poly.exterior.coords]
                dr.line(cs, fill=(255, 0, 0), width=1)
            im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
            ImageDraw.Draw(im).text((4, 4), f"{cid} {r['name'] if isinstance(r['name'], str) else ''} {s['date']}", fill=(255, 255, 0))
            im.save(f"{S}/chips3/{cid}.png")
    b = rows[0]
    res.append(dict(cand_id=cid, n_scenes=len(best), **b, second=rows[1] if len(rows) > 1 else None))
    print(json.dumps(res[-1]), flush=True)
json.dump(res, open(out, "w"), indent=0)  # out is per-lake when one id is given
