import sys, json; import numpy as np
from scipy import ndimage
S = sys.argv[1]
m = np.load(f"{S}/mapmasks.npz")
out = []
for col in ("red", "cy"):
    M = ndimage.binary_opening(m[col], iterations=2)
    lab, n = ndimage.label(M)
    sizes = ndimage.sum(M, lab, range(1, n + 1))
    cents = ndimage.center_of_mass(M, lab, range(1, n + 1))
    sl = ndimage.find_objects(lab)
    for i, (s, cxy, ob) in enumerate(zip(sizes, cents, sl)):
        h = ob[0].stop - ob[0].start; w = ob[1].stop - ob[1].start
        if s < 150: continue
        y, x = cxy
        if 4380 < x < 5000 and 1080 < y < 1400: continue  # legend
        out.append(dict(colour="cyan" if col == "cy" else "red", x=round(x, 1), y=round(y, 1), px=int(s), h=h, w=w))
print(len(out))
import collections; print(collections.Counter(o["colour"] for o in out))
print(sorted(o["px"] for o in out))
json.dump(out, open(f"{S}/dots.json", "w"), indent=0)
