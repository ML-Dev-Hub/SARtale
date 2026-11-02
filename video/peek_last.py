import io, subprocess
from PIL import Image

sheet = Image.new("RGB", (800 * 2, 450 * 2))
for k, t in enumerate((302, 304, 305, 305.9)):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", "out/SARtale-explainer.mp4", "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"], capture_output=True)
    sheet.paste(Image.open(io.BytesIO(r.stdout)).convert("RGB").resize((800, 450)), ((k % 2) * 800, (k // 2) * 450))
sheet.save("out/peek/last2.jpg", quality=86)
