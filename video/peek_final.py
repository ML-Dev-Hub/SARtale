import subprocess
from PIL import Image

ts = [12, 45, 85, 110, 150, 170, 200, 222, 255, 292]
W, H = 640, 360
s = Image.new("RGB", (W * 3, H * 4))
for k, t in enumerate(ts):
    s.paste(Image.open(f"out/peek/f{t}.jpg").resize((W, H)), ((k % 3) * W, (k // 3) * H))
s.save("out/peek/final.jpg", quality=86)
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", "out/SARtale-explainer.mp4", "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True)
print([l.split("] ")[1] for l in r.stderr.splitlines() if "mean_volume" in l or "max_volume" in l])
