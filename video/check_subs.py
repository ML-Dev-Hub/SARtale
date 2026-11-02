import io, re, subprocess
from PIL import Image, ImageChops

src = open("out/SARtale-explainer.srt", encoding="utf8").read().strip().split("\n\n")


def sec(s):
    h, m, r = s.split(":")
    a, b = r.split(",")
    return int(h) * 3600 + int(m) * 60 + int(a) + int(b) / 1000


def frame(path, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


missing = 0
idx = list(range(0, len(src), 7)) + [len(src) - 1]
for i in idx:
    a, b = [sec(x.strip()) for x in src[i].split("\n")[1].split("-->")]
    t = (a + b) / 2
    box = (360, 900, 1560, 1080)
    d = ImageChops.difference(frame("out/SARtale-explainer.mp4", t).crop(box), frame("out/joined.mp4", t).crop(box)).convert("L")
    share = sum(1 for p in d.getdata() if p > 40) / (d.width * d.height)
    ok = share > 0.01
    missing += not ok
    print(i + 1, round(t, 1), "subtitle" if ok else "MISSING", round(share, 3))
print("checked", len(idx), "missing", missing)
frame("out/SARtale-explainer.mp4", 303).resize((960, 540)).save("out/peek/end.jpg", quality=85)
frame("out/SARtale-explainer.mp4", 62).resize((960, 540)).save("out/peek/s03.jpg", quality=85)
