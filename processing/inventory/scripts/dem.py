"""Sample Copernicus GLO-30 DEM (public AWS bucket, no credentials) at each lake point."""
import sys, math, warnings; warnings.filterwarnings("ignore")
import pandas as pd, rasterio
S = sys.argv[1]
L = pd.read_csv(f"{S}/lakes_all.csv")
ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", AWS_NO_SIGN_REQUEST="YES")
out = []
cache = {}
with rasterio.Env(**ENV):
    for r in L.itertuples():
        la, lo = math.floor(r.lat), math.floor(r.lon)
        name = f"Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM"
        url = f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
        try:
            if url not in cache: cache[url] = rasterio.open(url)
            v = next(cache[url].sample([(r.lon, r.lat)]))[0]
            out.append(int(round(float(v))))
        except Exception as e:
            out.append(None); print("ERR", name, e)
L["dem_m"] = out
L.to_csv(f"{S}/lakes_all.csv", index=False)
print(L.dem_m.describe())
print((L.dem_m < 2500).sum(), "below 2500 m")
