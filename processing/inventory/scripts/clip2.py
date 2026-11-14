import sys, warnings; warnings.filterwarnings("ignore")
import geopandas as gpd
from shapely.geometry import box
S = sys.argv[1]
a0 = gpd.read_file(f"{S}/dl/gb/ADM0.geojson"); print("ADM0 bounds", a0.total_bounds)
a1 = gpd.read_file(f"{S}/dl/gb/ADM1.geojson")
ajk = a1[a1.shapeName == "Azad Kashmir"].to_crs(32643).buffer(-1000).to_crs(4326).union_all()
reg = a0.to_crs(32643).buffer(1000).to_crs(4326).union_all().intersection(box(70.8, 34.4, 76.6, 37.6)).difference(ajk)
gpd.GeoSeries([reg], crs=4326).to_file(f"{S}/region_pak.gpkg", driver="GPKG")
for src, dst in (("osm_water_region", "osm_water_pak"), ("himag_region", "himag_pak")):
    g = gpd.read_file(f"{S}/{src}.gpkg"); g = g[g.representative_point().within(reg)]
    g.to_file(f"{S}/{dst}.gpkg", driver="GPKG")
    if src.startswith("osm"): g.drop(columns="geometry").to_csv(f"{S}/{dst}.csv", index=False)
    print(dst, len(g))
