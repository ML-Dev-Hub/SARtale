import subprocess, io
from PIL import Image

for name, path in [("final", "out/SARtale-explainer.mp4"), ("joined", "out/joined.mp4")]:
    for t in (250, 284, 286, 288, 290, 292, 294, 296, 300, 304):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
        if not r.stdout:
            print(name, t, "no frame")
            continue
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        print(name, t, im.getpixel((30, 30)), im.getpixel((960, 60)))
