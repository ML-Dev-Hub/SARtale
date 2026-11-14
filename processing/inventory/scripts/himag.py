import sys, warnings; warnings.filterwarnings("ignore")
import geopandas as gpd, pandas as pd
D = sys.argv[1]; OUT = sys.argv[2]
B = (70.8, 34.4, 76.6, 37.6)
frames = []
for yr in range(2008, 2018):
    g = gpd.read_file(f"{D}/Hi_MAG_database_{yr}.shp")
    g = g.to_crs(4326)
    g = g.cx[B[0]:B[2], B[1]:B[3]]
    g["year"] = yr
    frames.append(g)
    print(yr, len(g), round(g.GL_Area.sum(), 2) if len(g) else 0, flush=True)
a = pd.concat(frames)
a.to_file(OUT, driver="GPKG")
print(a.drop(columns="geometry").head().to_string()); print(a.GL_Type.value_counts())
