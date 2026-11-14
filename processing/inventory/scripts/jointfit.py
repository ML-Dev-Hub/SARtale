import sys, json, csv
import numpy as np
from scipy import ndimage, optimize
S = sys.argv[1]; pairs = json.loads(sys.argv[2]); w = float(sys.argv[3])
m = np.load(f"{S}/mapmasks.npz"); Y = m["y"]; H, W = Y.shape
dt = ndimage.distance_transform_edt(~Y)
P = np.load(f"{S}/bpts.npy")
dots = json.load(open(f"{S}/dots.json"))
Hm = {}
for r in csv.DictReader(open(f"{S}/himag_region_cent.csv")):
    if r["year"] == "2017": Hm.setdefault(r["GL_ID"], (float(r["lon"]), float(r["lat"])))
for r in csv.DictReader(open(f"{S}/osm_water_pak.csv", encoding="utf-8")):
    Hm[r["osm"]] = (float(r["lon"]), float(r["lat"]))
DX = np.array([[dots[int(k)]["x"], dots[int(k)]["y"]] for k in pairs]); LL = np.array([Hm[v] for v in pairs.values()])
def merc(lat): return np.degrees(np.log(np.tan(np.pi/4 + np.radians(lat)/2)))
def imerc(m): return np.degrees(2*np.arctan(np.exp(np.radians(m))) - np.pi/2)
# model: (x,y) pixel -> (lon, Y) with Y=lat or merc(lat): lon = p0 + p1 x + p2 y ; Y = p3 + p4 x + p5 y
def fwd(p, x, y, mode):
    lon = p[0] + p[1]*x + p[2]*y; Yv = p[3] + p[4]*x + p[5]*y
    return lon, (imerc(Yv) if mode == "merc" else Yv)
def inv(p, lon, lat, mode):
    Yv = merc(lat) if mode == "merc" else lat
    a, b, c, d = p[1], p[2], p[4], p[5]; det = a*d - b*c
    u, v = lon - p[0], Yv - p[3]
    return (d*u - b*v)/det, (-c*u + a*v)/det
def cost(p, mode, trunc=15, report=False):
    x, y = inv(p, P[:, 0], P[:, 1], mode)
    ok = (x >= 0) & (x < W-1) & (y >= 0) & (y < H-1)
    v = ndimage.map_coordinates(dt, [y[ok], x[ok]], order=1)
    cb = np.minimum(v, trunc).mean() + (1-ok.mean())*trunc
    lon, lat = fwd(p, DX[:, 0], DX[:, 1], mode)
    km = np.hypot((lon-LL[:, 0])*111.32*np.cos(np.radians(LL[:, 1])), (lat-LL[:, 1])*111.32)
    if report: return cb, km, np.median(v)
    return cb + w*np.mean(km**2)
out = {}
g = json.load(open(f"{S}/georef.json"))["geo"]["params"]  # a,c,d,f geo
for mode in ("geo", "merc"):
    a, c, d, f = g
    p0 = np.array([c, a, 0, f, 0, d]) if mode == "geo" else np.array([c, a, 0, merc(f), 0, d*1.23])
    best = None
    for s in ([1, 1], [1, 1.05], [1, 0.95], [1, 1.1], [1, 1.2], [1, 1.25]):
        q = p0.copy(); q[5] = p0[5]*s[1] if mode == "merc" else p0[5]
        if mode == "merc": q[3] = merc(37.18) 
        r = optimize.minimize(lambda p: cost(p, mode, 40), q, method="Nelder-Mead", options=dict(maxiter=20000, maxfev=20000, xatol=1e-9, fatol=1e-6))
        r = optimize.minimize(lambda p: cost(p, mode, 15), r.x, method="Nelder-Mead", options=dict(maxiter=20000, maxfev=20000, xatol=1e-10, fatol=1e-7))
        if best is None or r.fun < best.fun: best = r
    cb, km, med = cost(best.x, mode, report=True)
    print(mode, "cost", round(best.fun, 3), "chamfer", round(cb, 2), "median px", round(med, 1), "pair km", np.round(km, 2).tolist())
    out[mode] = dict(p=best.x.tolist(), fun=float(best.fun), chamfer=float(cb), pair_km=km.tolist())
json.dump(out, open(f"{S}/georef3.json", "w"), indent=1)
