import glob
from PIL import Image

ids = ["08a_app_open", "08b_app_dance", "08c_app_change", "08d_app_sites", "08e_app_evidence"]
pick = []
for i in ids:
    f = sorted(glob.glob(f"out/app/{i}/*.jpg"))
    pick += [f[len(f) // 6], f[len(f) * 5 // 6]]
W, H = 640, 360
s = Image.new("RGB", (W * 4, H * 3))
for k, p in enumerate(pick):
    s.paste(Image.open(p).resize((W, H)), ((k % 4) * W, (k // 4) * H))
s.save("out/peek/app.jpg", quality=85)
print("ok")
