import sys, warnings, json; warnings.filterwarnings("ignore")
import numpy as np, geopandas as gpd
from scipy import ndimage, optimize
S = sys.argv[1]
m = np.load(f"{S}/mapmasks.npz"); Y = m["y"]
H, W = Y.shape
dt = ndimage.distance_transform_edt(~Y)
g = gpd.read_file(f"{S}/dl/gb/ADM2.geojson").cx[70.5:77.5, 34.0:37.6]
pts = []
for geom in g.boundary.geometry:
    geoms = getattr(geom, "geoms", [geom])
    for ln in geoms:
        L = ln.segmentize(0.005)
        pts.append(np.asarray(L.coords))
P = np.vstack(pts)
P = P[(P[:, 0] > 70.8) & (P[:, 1] > 34.2)]
def merc(lat): return np.degrees(np.log(np.tan(np.pi/4 + np.radians(lat)/2)))
def cost(p, mode, P=P, trunc=40):
    a, c, d, f = p[:4]
    lon, lat = P[:, 0], P[:, 1]
    yy = merc(lat) if mode == "merc" else lat
    x = (lon - c) / a; y = (yy - f) / d
    ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
    if ok.sum() < 0.3 * len(P): return 1e3
    v = ndimage.map_coordinates(dt, [y[ok], x[ok]], order=1)
    return np.minimum(v, trunc).mean() + (1 - ok.mean()) * trunc
best = {}
for mode in ("geo", "merc"):
    res = []
    lat0 = 37.4 if mode == "geo" else merc(37.4)
    for a in np.linspace(0.00085, 0.00115, 13):
        for c in np.linspace(70.6, 71.3, 15):
            for f in np.linspace(lat0 - 0.4, lat0 + 0.4, 17):
                d = -a if mode == "geo" else -a * 1.0
                if mode == "geo": d = -a * 1.0  # pixel aspect unknown; refined later
                res.append((cost([a, c, d, f], mode, P[::7], 60), a, c, d, f))
    res.sort()
    p0 = np.array(res[0][1:])
    r = optimize.minimize(lambda p: cost(p, mode, P, 30), p0, method="Nelder-Mead",
                          options=dict(xatol=1e-7, fatol=1e-4, maxiter=4000))
    r = optimize.minimize(lambda p: cost(p, mode, P, 10), r.x, method="Nelder-Mead",
                          options=dict(xatol=1e-8, fatol=1e-5, maxiter=4000))
    v = r.x; a, c, d, f = v
    lon, lat = P[:, 0], P[:, 1]; yy = merc(lat) if mode == "merc" else lat
    x = (lon - c) / a; y = (yy - f) / d
    ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
    dd = ndimage.map_coordinates(dt, [y[ok], x[ok]], order=1)
    print(mode, "coarse", res[0][0], "final", r.fun, "params", v.tolist(), "median px", np.median(dd), "p80", np.percentile(dd, 80), "frac<5px", (dd < 5).mean(), flush=True)
    best[mode] = dict(params=v.tolist(), cost=float(r.fun), median=float(np.median(dd)))
json.dump(best, open(f"{S}/georef.json", "w"), indent=1)
