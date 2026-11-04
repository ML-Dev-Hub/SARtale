"""Render the SARtale Lake Watch story video (1920x1080, 30 fps) from real imagery, app stills, the eleven_v4
narration, the music bed and two sound effects. Run in the sartale-video env after fetch_imagery.py,
fetch_wide.py, shots.py, voice.py and music.py:

    python video/story/build.py            # full render
    python video/story/build.py --sheet    # contact sheet of key frames only

Timeline values are seconds of the narration take (out/audio/nathaniel.mp3, word times from speech-to-text);
the voice is lifted 4% in tempo, so video time = take time / TEMPO.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
IMG, APP, AUD = OUT / "img", OUT / "app", OUT / "audio"
ROOT = HERE.parents[1]
W, H, FPS = 1920, 1080, 30
TEMPO = 1.04
TOTAL = 35.4  # video seconds
TEAM_AT = 31.9  # team card starts (video seconds)
FINAL = OUT / "SARtale-lake-watch-story.mp4"

BG = (8, 15, 20)
INK = (240, 245, 247)
DIM = (160, 176, 186)
TEAL = (64, 214, 200)
AMBER = (255, 170, 60)
F = r"C:\Windows\Fonts"


def font(name, size):
    return ImageFont.truetype(f"{F}\\{name}", size)


BOLD, SEMI, REG, LIGHT = (lambda s: font("segoeuib.ttf", s)), (lambda s: font("seguisb.ttf", s)), \
    (lambda s: font("segoeui.ttf", s)), (lambda s: font("segoeuil.ttf", s))


def T(take_s):
    """Take time to video time."""
    return take_s / TEMPO


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ramp(t, a, b):
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def window(t, a, b, fade=0.35):
    """1 inside [a, b], fading in and out over `fade` seconds."""
    return min(ramp(t, a, a + fade), 1 - ramp(t, b - fade, b))


# ---------- assets ----------
def load(p, mode="RGB"):
    return Image.open(p).convert(mode)


WIDE = load(next(IMG.glob("hunza_wide_*.png")))
WIDE_META = json.load(open(IMG / "hunza_wide.json"))
S2_CLOUD = load(IMG / "attabad_s2_2026-07-03.png")
NISAR = load(IMG / "attabad_nisar_2026-06-30.png")
SHOTS = {k: load(APP / f"{k}.png") for k in ("watch", "detail", "chart", "brief")}
LOGO = load(ROOT / "app" / "public" / "brand" / "logo-256.png", "RGBA")
WORDS = json.load(open(AUD / "nathaniel_words.json"))


def crop_zoom(img, box0, box1, k, size=(W, H)):
    """Crop interpolated between two (cx, cy, width) boxes in image pixels at progress k, filled to `size`."""
    cx = box0[0] + (box1[0] - box0[0]) * k
    cy = box0[1] + (box1[1] - box0[1]) * k
    cw = box0[2] + (box1[2] - box0[2]) * k
    ch = cw * size[1] / size[0]
    return img.transform(size, Image.Transform.EXTENT, (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2),
                         Image.Resampling.BICUBIC)


def blend(a, b, k):
    return b if k >= 1 else a if k <= 0 else Image.blend(a, b, k)


def darken(img, k):
    return Image.blend(img, Image.new("RGB", img.size, BG), k)


# ---------- drawing ----------
class Canvas:
    """Draws on an RGB image: ImageDraw blends RGBA colours into RGB images (on RGBA images it would
    replace pixels, alpha included), and overlays go in through masks."""

    def __init__(self, base):
        self.im = base.convert("RGB")
        self.d = ImageDraw.Draw(self.im, "RGBA")

    def text(self, xy, s, f, fill=INK, a=1.0, anchor="la", shadow=True):
        if a <= 0:
            return
        if shadow:
            m = Image.new("L", self.im.size, 0)
            ImageDraw.Draw(m).text((xy[0] + 2, xy[1] + 3), s, font=f, fill=int(190 * a), anchor=anchor)
            self.im.paste((0, 0, 0), (0, 0), m.filter(ImageFilter.GaussianBlur(6)))
        self.d.text(xy, s, font=f, fill=(*fill[:3], int(255 * a)), anchor=anchor)

    def panel(self, box, a=1.0, r=18, fill=(6, 12, 16), alpha=200):
        if a > 0:
            self.d.rounded_rectangle(box, r, fill=(*fill, int(alpha * a)))

    def pill(self, xy, s, a=1.0, color=TEAL, size=26, anchor="ra"):
        if a <= 0:
            return
        f = SEMI(size)
        x0, y0, x1, y1 = self.d.textbbox(xy, s, font=f, anchor=anchor)
        self.d.rounded_rectangle((x0 - 18, y0 - 10, x1 + 18, y1 + 12), 22, fill=(6, 12, 16, int(190 * a)),
                                 outline=(*color, int(255 * a)), width=2)
        self.d.text(xy, s, font=f, fill=(*color, int(255 * a)), anchor=anchor)

    def paste(self, img, xy, a=1.0, radius=0):
        if a <= 0:
            return
        img = img.convert("RGBA")
        m = img.getchannel("A")
        if radius:
            r = Image.new("L", img.size, 0)
            ImageDraw.Draw(r).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
            m = ImageChops.darker(m, r)
        if a < 1:
            m = m.point(lambda v: int(v * a))
        self.im.paste(img.convert("RGB"), (int(xy[0]), int(xy[1])), m)

    def rgb(self):
        return self.im


def caption(c, s, a, y=900):
    """The one big caption per beat, bottom-left."""
    c.text((120, y), s, BOLD(66), a=a, anchor="ls")


def badge(c, a):
    c.pill((W - 60, 48), "Indicative screening · NISAR provisional data", a=a, color=TEAL, size=24)


def browser(img, box, k_zoom, size=(1440, 820)):
    """An app still in a simple browser frame, slowly pushing from box[0] to box[1]."""
    frame = Image.new("RGBA", (size[0], size[1] + 44), (22, 30, 36, 255))
    d = ImageDraw.Draw(frame)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((20 + i * 26, 15, 34 + i * 26, 29), fill=col)
    d.rounded_rectangle((120, 9, size[0] - 120, 35), 13, fill=(10, 16, 20))
    d.text((size[0] / 2, 22), "SARtale · Lake Watch", font=REG(18), fill=DIM, anchor="mm")
    frame.paste(crop_zoom(img, box[0], box[1], k_zoom, size), (0, 44))
    m = Image.new("L", frame.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), 16, fill=255)
    frame.putalpha(m)
    return frame


# ---------- scenes ----------
def bg_wide(t):
    """The Hunza valley, pushing in on Shisper lake and the Hassanabad bridge below it during the hook,
    easing back out for the problem."""
    (lx, ly), (bx, by) = WIDE_META["pins"]["shisper"], WIDE_META["pins"]["kkh_bridge"]
    full = (WIDE.width / 2, WIDE.height / 2, WIDE.width)
    near = ((lx + bx) / 2 + 330, (ly + by) / 2 - 20, 1000)
    if t < T(6.2):
        k = ramp(t, 0, T(6.2))
        return crop_zoom(WIDE, full, near, k), near, full, k
    k = ramp(t, T(6.2), T(11.0))
    return crop_zoom(WIDE, near, full, k), near, full, None


def to_screen(px, py, box):
    cw = box[2]
    ch = cw * H / W
    return (px - (box[0] - cw / 2)) / cw * W, (py - (box[1] - ch / 2)) / ch * H


def scene_valley(t):
    img, near, full, k = bg_wide(t)
    hook = t < T(6.2)
    if not hook:
        img = darken(img, 0.55 * ramp(t, T(6.2), T(7.0)))
    c = Canvas(img)
    if hook:
        cx = near[0] * 0 + full[0] + (near[0] - full[0]) * k
        cy = full[1] + (near[1] - full[1]) * k
        cw = full[2] + (near[2] - full[2]) * k
        x, y = to_screen(*WIDE_META["pins"]["shisper"], (cx, cy, cw))
        bx, by = to_screen(*WIDE_META["pins"]["kkh_bridge"], (cx, cy, cw))
        # the lake, then a dotted drop to the bridge 6.4 km below it, then the bridge
        pulse = (t * 1.6) % 1
        la = ramp(t, 0.8, 1.4)
        for r, al in ((26 + 90 * pulse, 1 - pulse), (20, 1)):
            c.d.ellipse((x - r, y - r, x + r, y + r), outline=(*AMBER, int(255 * al * la)), width=5)
        c.d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(*AMBER, int(255 * la)))
        c.panel((x + 40, y - 34, x + 410, y + 30), a=ramp(t, 1.0, 1.6), alpha=170)
        c.text((x + 60, y - 2), "Shisper glacier lake", SEMI(34), a=ramp(t, 1.0, 1.6), anchor="lm")
        drop = ramp(t, T(2.0), T(3.4))
        n = 14
        for i in range(int(n * drop)):
            f0, f1 = (i + 0.2) / n, (i + 0.7) / n
            if f0 * (by - y) < 24 or f1 * (by - y) > (by - y) - 24:
                continue
            c.d.line((x + (bx - x) * f0, y + (by - y) * f0, x + (bx - x) * f1, y + (by - y) * f1), fill=(*AMBER, 230), width=5)
        ba = ramp(t, T(3.3), T(3.8))
        RED = (255, 84, 72)
        for r, al in ((22 + 70 * ((t * 1.6 + 0.5) % 1), 1 - (t * 1.6 + 0.5) % 1), (18, 1)):
            c.d.ellipse((bx - r, by - r, bx + r, by + r), outline=(*RED, int(255 * al * ba)), width=5)
        c.d.line((bx - 9, by - 9, bx + 9, by + 9), fill=(*RED, int(255 * ba)), width=5)
        c.d.line((bx - 9, by + 9, bx + 9, by - 9), fill=(*RED, int(255 * ba)), width=5)
        c.panel((bx + 40, by - 50, bx + 560, by + 48), a=ba, alpha=170)
        c.text((bx + 60, by - 22), "Karakoram Highway bridge", SEMI(34), a=ba, anchor="lm")
        c.text((bx + 60, by + 20), "Hassanabad · 6.4 km below the lake", REG(26), fill=DIM, a=ba, anchor="lm")
        c.panel((80, 70, 1010, 330), a=ramp(t, 0.4, 0.9))
        c.text((120, 110), "7 MAY 2022", BOLD(40), fill=AMBER, a=ramp(t, 0.3, 0.9))
        c.text((120, 170), "Shisper lake outburst, Hassanabad, Hunza", SEMI(38), a=ramp(t, 0.9, 1.5))
        c.text((120, 228), "The Karakoram Highway bridge is destroyed.", REG(36), a=ramp(t, T(3.3), T(3.9)))
        c.panel((W - 1110, H - 76, W - 30, H - 22), a=ramp(t, 0.5, 1.2), r=12, alpha=170)
        c.text((W - 50, H - 36), "Image: Sentinel-2, 20 Jul 2026 · Bridge: OpenStreetMap · Event: Radio Pakistan, 7 May 2022", REG(22),
               fill=DIM, a=ramp(t, 0.5, 1.2), anchor="rs")
    else:
        a = window(t, T(6.3), T(11.25), 0.4)
        n = int(round(131 * ease((t - T(7.3)) / 0.9)))
        c.text((120, 470), f"{max(n, 0)}", LIGHT(230), fill=INK, a=a, anchor="ls")
        c.text((128, 545), "potentially dangerous glacial lakes", SEMI(52), a=a * ramp(t, T(7.9), T(8.6)), anchor="ls")
        c.text((128, 610), "tracked by SUPARCO, Pakistan's space agency · update of 2 July 2026", REG(32),
               fill=DIM, a=a * ramp(t, T(8.6), T(9.3)), anchor="ls")
    return c.rgb()


SQ = 860  # side of the cloud / radar panel
SQX, SQY = W - SQ - 120, (H - SQ) // 2 - 10


def scene_cloud_radar(t):
    bg = darken(crop_zoom(WIDE, (WIDE_META["pins"]["attabad"][0], WIDE_META["pins"]["attabad"][1], 1300),
                          (WIDE_META["pins"]["attabad"][0], WIDE_META["pins"]["attabad"][1], 1100), ramp(t, T(11), T(17))), 0.82)
    bg = bg.filter(ImageFilter.GaussianBlur(10))
    c = Canvas(bg)
    a_in = ramp(t, T(11.0), T(11.6))
    zoom = 1 + 0.05 * ramp(t, T(11), T(17.2))
    side = int(SQ * zoom)
    cloud = S2_CLOUD.resize((side, side), Image.Resampling.BICUBIC).crop(((side - SQ) // 2,) * 2 + ((side + SQ) // 2,) * 2)
    radar = NISAR.resize((side, side), Image.Resampling.BICUBIC).crop(((side - SQ) // 2,) * 2 + ((side + SQ) // 2,) * 2)
    k = ramp(t, T(14.1), T(15.6))  # the radar sweep
    edge = int(SQ * k)
    panel = cloud.copy()
    if edge > 0:
        panel.paste(radar.crop((0, 0, edge, SQ)), (0, 0))
    c.paste(panel, (SQX, SQY), a=a_in, radius=14)
    if 0 < k < 1:
        glow = Image.new("RGBA", (60, SQ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for i in range(60):
            gd.line((i, 0, i, SQ), fill=(*TEAL, int(220 * (1 - abs(i - 30) / 30) ** 2)))
        c.paste(glow, (SQX + edge - 30, SQY))
    c.d.rounded_rectangle((SQX, SQY, SQX + SQ, SQY + SQ), 14, outline=(255, 255, 255, int(60 * a_in)), width=2)
    lab_cloud = "Sentinel-2 optical · 3 Jul 2026 · 70% cloud over this window"
    lab_radar = "NISAR L-band radar · 30 Jun 2026 · same 6 km window"
    c.text((SQX, SQY + SQ + 44), lab_cloud, REG(26), fill=DIM, a=a_in * (1 - ramp(t, T(14.3), T(14.8))))
    c.text((SQX, SQY + SQ + 44), lab_radar, REG(26), fill=TEAL, a=ramp(t, T(14.6), T(15.2)))
    c.panel((SQX + 14, SQY + 14, SQX + 360, SQY + 74), a=a_in, alpha=180, r=12)
    c.text((SQX + 32, SQY + 26), "Attabad Lake, Hunza", SEMI(32), a=a_in)
    t1 = window(t, T(11.1), T(14.15), 0.4)
    c.text((120, 430), "On many summer days,", SEMI(56), a=t1)
    c.text((120, 505), "cloud hides the lakes.", BOLD(72), fill=INK, a=t1)
    t2 = ramp(t, T(14.4), T(15.0))
    c.text((120, 430), "Radar sees", SEMI(64), a=t2)
    c.text((120, 515), "straight through.", BOLD(80), fill=TEAL, a=t2)
    c.text((122, 640), "NASA–ISRO NISAR · images work in day, night and cloud", REG(28), fill=DIM, a=t2)
    badge(c, ramp(t, T(14.8), T(15.4)))
    return c.rgb()


APP_BEATS = [  # (take start, still, crop from, crop to, verb, line)
    (17.0, "watch", (720, 330, 1440), (430, 300, 900), "FIND", "every lake, on one map and list"),
    (19.25, "chart", (1010, 380, 980), (1010, 400, 900), "MEASURE", "its water, pass after pass"),
    (21.7, "brief", (640, 330, 1280), (600, 300, 1100), "BRIEF", "one printable page, limits included"),
]


def scene_app(t):
    c = Canvas(Image.new("RGB", (W, H), BG))
    c.d.rectangle((0, 0, W, H), fill=(10, 20, 26, 255))
    beat = max(i for i, b in enumerate(APP_BEATS) if t >= T(b[0]) - 0.3 or i == 0)
    start, still, b0, b1, verb, line = APP_BEATS[beat]
    end = T(APP_BEATS[beat + 1][0]) if beat + 1 < len(APP_BEATS) else T(23.6)
    def still_at(i):
        st, name, c0, c1 = APP_BEATS[i][:4]
        e = T(APP_BEATS[i + 1][0]) if i + 1 < len(APP_BEATS) else T(23.6)
        return browser(SHOTS[name], (c0, c1), ramp(t, T(st) - 0.3, e + 0.3), size=(1180, 700))
    fr = still_at(beat)
    if beat and t < T(start) + 0.1:  # cross-fade from the previous still
        prev, k = still_at(beat - 1), ramp(t, T(start) - 0.3, T(start) + 0.1)
        fr = Image.blend(prev, fr, k)
    c.paste(fr, (640, 170), a=ramp(t, T(16.6), T(17.1)))
    # verbs column, the current one lit
    for i, b in enumerate(APP_BEATS):
        on = i == beat
        lit = ramp(t, T(b[0]) - 0.2, T(b[0]) + 0.2)
        col = TEAL if on else (90, 110, 120)
        c.text((120, 360 + i * 170), b[4], BOLD(76 if on else 60), fill=col, a=ramp(t, T(16.6), T(17.1)) * (0.45 + 0.55 * lit))
        if on:
            c.text((124, 460 + i * 170), b[5], REG(28), fill=INK, a=lit)
    c.text((120, 250), "SARtale Lake Watch", SEMI(40), fill=INK, a=ramp(t, T(16.6), T(17.1)))
    badge(c, 1)
    return c.rgb()


def scene_proof(t):
    bg = darken(crop_zoom(WIDE, (WIDE.width / 2, WIDE.height / 2, WIDE.width * 0.9),
                          (WIDE.width / 2, WIDE.height / 2, WIDE.width * 0.8), ramp(t, T(23.5), T(27.5))), 0.78)
    c = Canvas(bg.filter(ImageFilter.GaussianBlur(4)))
    a = ramp(t, T(23.6), T(24.0))
    c.text((120, 300), "17 June – 4 August 2026, while cloud limited optical checks", SEMI(38), fill=DIM, a=a)
    n60 = int(round(60 * ease((t - T(24.6)) / 0.7)))
    c.text((120, 590), f"{max(n60, 0)}", LIGHT(260), fill=TEAL, a=ramp(t, T(24.5), T(24.8)), anchor="ls")
    c.text((128, 660), "valid NISAR looks", SEMI(48), a=ramp(t, T(24.9), T(25.4)), anchor="ls")
    n11 = int(round(11 * ease((t - T(26.1)) / 0.5)))
    c.text((820, 590), f"{max(n11, 0)}", LIGHT(260), fill=TEAL, a=ramp(t, T(26.0), T(26.3)), anchor="ls")
    c.text((828, 660), "lakes, Gilgit-Baltistan and KP", SEMI(48), a=ramp(t, T(26.2), T(26.7)), anchor="ls")
    c.text((120, 790), "All eleven currently read Stable. Indicative screening, not a flood warning.", REG(30),
           fill=DIM, a=ramp(t, T(26.4), T(26.9)))
    badge(c, 1)
    return c.rgb()


def scene_close(t):
    c = Canvas(Image.new("RGB", (W, H), BG))
    a = ramp(t, T(27.4), T(27.9))
    tile = Image.new("RGBA", (200, 200), (236, 242, 244, 255))
    tile.alpha_composite(LOGO.resize((180, 180), Image.Resampling.LANCZOS), (10, 10))
    c.paste(tile, (W // 2 - 100, 220), a=a, radius=28)
    c.text((W // 2, 520), "SARtale", BOLD(110), a=a, anchor="ms")
    c.text((W // 2, 580), "Lake Watch · glacial lakes of Gilgit-Baltistan and KP", REG(34), fill=DIM, a=a, anchor="ms")
    s = ramp(t, T(28.6), T(29.2))
    c.text((W // 2, 700), "When clouds close in,", SEMI(54), a=s, anchor="ms")
    c.text((W // 2, 770), "the lakes stay in view.", BOLD(64), fill=TEAL, a=ramp(t, T(30.1), T(30.6)), anchor="ms")
    f = ramp(t, T(29.0), T(29.6))
    c.text((W // 2, H - 110), "Indicative screening on NISAR provisional data (P05023) · Official warnings come from PMD and NDMA",
           REG(26), fill=DIM, a=f, anchor="ms")
    return c.rgb()


def scene_team(t):
    c = Canvas(Image.new("RGB", (W, H), BG))
    a = ramp(t, TEAM_AT, TEAM_AT + 0.5)
    c.text((W // 2, 300), "NASA SPACE APPS CHALLENGE 2026 · ISLAMABAD", SEMI(30), fill=TEAL, a=a, anchor="ms")
    c.text((W // 2, 420), "Team SARcastic Scientists", BOLD(92), a=a, anchor="ms")
    m = ramp(t, TEAM_AT + 0.4, TEAM_AT + 0.9)
    c.text((W // 2, 560), "Saeed Ahmad", SEMI(56), a=m, anchor="ms")
    c.text((W // 2, 640), "Shaharyar Sajid", SEMI(56), a=m, anchor="ms")
    c.text((W // 2, 740), "Challenge: Dancing with the SARs", REG(34), fill=DIM, a=m, anchor="ms")
    f = ramp(t, TEAM_AT + 0.8, TEAM_AT + 1.3)
    c.text((W // 2, H - 110), "Data: NISAR GCOV (NASA, via ASF) · Sentinel-2 (Copernicus, via Earth Search) · SUPARCO GLOF updates",
           REG(26), fill=DIM, a=f, anchor="ms")
    c.text((W // 2, H - 66), "Narration and music generated with ElevenLabs", REG(26), fill=DIM, a=f, anchor="ms")
    return c.rgb()


SCENES = [  # (video start, renderer); cross-fade 0.35 s at each cut
    (0.0, scene_valley),
    (T(11.0), scene_cloud_radar),
    (T(16.6), scene_app),
    (T(23.4), scene_proof),
    (T(27.3), scene_close),
    (TEAM_AT, scene_team),
]
XF = 0.35


def frame(t):
    i = max(k for k, (s, _) in enumerate(SCENES) if t >= s)
    img = SCENES[i][1](t)
    if i + 1 < len(SCENES) and t > SCENES[i + 1][0] - XF:
        img = blend(img, SCENES[i + 1][1](t), (t - (SCENES[i + 1][0] - XF)) / XF)
    fade = min(ramp(t, 0, 0.5), 1 - ramp(t, TOTAL - 0.6, TOTAL))
    return darken(img, 1 - fade) if fade < 1 else img


def sheet():
    ts = [1.5, 3.5, 7.5, 9.5, 12, 14.4, 15.3, 17.5, 20, 21.5, 24.5, 25.6, 28.8, 30.5, 32.0, 34.0]
    thumbs = [frame(t).resize((480, 270)) for t in ts]
    s = Image.new("RGB", (480 * 4, 270 * 4))
    for i, im in enumerate(thumbs):
        ImageDraw.Draw(im).text((8, 6), f"{ts[i]:.1f}s", fill=(255, 255, 0), font=REG(22))
        s.paste(im, ((i % 4) * 480, (i // 4) * 270))
    s.save(OUT / "story_sheet.jpg", quality=88)
    print(OUT / "story_sheet.jpg")


def srt():
    """Subtitles from the word timings, cut into short lines at sentence ends."""
    cues, cur = [], []
    for w, s, e in WORDS:
        cur.append((w.replace("Nisar's", "NISAR's").replace("SARtail", "SARtale"), s, e))
        if w.endswith((".", ",")) and len(" ".join(x[0] for x in cur)) > 22 or w.endswith("."):
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)

    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out = [f"{i + 1}\n{ts(T(c[0][1]))} --> {ts(T(c[-1][2]) + 0.2)}\n{' '.join(x[0] for x in c)}\n" for i, c in enumerate(cues)]
    (OUT / "SARtale-lake-watch-story.srt").write_text("\n".join(out), encoding="utf8")


def render():
    video = OUT / "story_video.mp4"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                           "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                           str(video)], stdin=subprocess.PIPE)
    n = int(TOTAL * FPS)
    for i in range(n):
        ff.stdin.write(frame(i / FPS).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    # audio: voice lifted 4%, music ducked under it, rumble under the hook, radar sweep at the turn
    radar_at = int(T(14.05) * 1000)
    fc = (f"[0:a]atempo={TEMPO},adelay=150|150,apad,atrim=0:{TOTAL},asplit=2[v][vk];"
          f"[1:a]volume=0.55,afade=t=out:st={TOTAL - 1.6}:d=1.6,apad,atrim=0:{TOTAL}[m];"
          "[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[md];"
          "[2:a]volume=0.45,afade=t=in:d=0.6,afade=t=out:st=4.5:d=1.5[r];"
          f"[3:a]volume=0.6,adelay={radar_at}|{radar_at}[s];"
          f"[v][md][r][s]amix=inputs=4:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,atrim=0:{TOTAL}[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(AUD / "nathaniel.mp3"), "-i", str(AUD / "music.mp3"),
                    "-i", str(AUD / "sfx_rumble.mp3"), "-i", str(AUD / "sfx_radar.mp3"), "-i", str(video),
                    "-filter_complex", fc, "-map", "4:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-movflags", "+faststart", "-t", str(TOTAL), str(FINAL)], check=True)
    srt()
    print(FINAL)


if __name__ == "__main__":
    sheet() if "--sheet" in sys.argv else render()
