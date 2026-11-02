import glob, io, json, subprocess
from PIL import Image

for f in sorted(glob.glob("out/segments/*.mp4")):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,pix_fmt,color_range,color_space,color_primaries,color_transfer,sample_aspect_ratio,r_frame_rate,time_base",
                        "-of", "json", f], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    print(f[13:28], s.get("pix_fmt"), s.get("color_range"), s.get("color_space"), s.get("color_primaries"), s.get("color_transfer"), s.get("sample_aspect_ratio"), s.get("r_frame_rate"), s.get("time_base"))


def frame(path, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


sheet = Image.new("RGB", (640 * 3, 360))
for k, t in enumerate((12, 17, 20)):
    sheet.paste(frame("out/media/videos/scenes/1080p30/S09.mp4", t).resize((640, 360)), (k * 640, 0))
sheet.save("out/peek/s09.jpg", quality=85)
