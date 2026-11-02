"""Manim scenes for the SARtale explainer. Timing follows each segment's narration."""
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from manim import *

ROOT = Path(__file__).resolve().parent
APP = ROOT.parent / "app" / "public"
OUT = ROOT / "out"
EQ_DIR = OUT / "eq"
EQ_DIR.mkdir(parents=True, exist_ok=True)

BG = "#0B1016"
TEAL = "#3DD6C6"
AMBER = "#F2A73B"
INK = "#E8EEF0"
MUTED = "#8FA3AD"
BLUE = "#58C4DD"
RED = "#E8665A"
FONT = "Segoe UI"

config.background_color = BG

NARR = {s["id"]: s["text"] for s in json.load(open(ROOT / "narration.json", encoding="utf8"))["segments"]}
DUR = json.load(open(OUT / "durations.json", encoding="utf8")) if (OUT / "durations.json").exists() else {}

DATES = ["14 Jul", "26 Jul", "19 Aug", "31 Aug", "12 Sep", "24 Sep", "6 Oct", "18 Oct"]
HH = [-6.07, -7.64, -16.60, -16.79, -15.62, -14.06, -12.98, -12.77]
HV = [-16.26, -17.39, -22.35, -22.86, -22.47, -21.88, -21.22, -20.42]
DAYS = [195, 207, 231, 243, 255, 267, 279, 291]


def eq(latex: str, name: str, height: float = 0.8, color=INK) -> SVGMobject:
    path = EQ_DIR / f"{name}.svg"
    fig = plt.figure(figsize=(0.01, 0.01))
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["svg.fonttype"] = "path"
    fig.text(0, 0, f"${latex}$", fontsize=40, color="white")
    fig.savefig(path, format="svg", bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    return SVGMobject(str(path), height=height).set_color(color)


def txt(s: str, size: int = 30, color=INK, weight=NORMAL) -> Text:
    return Text(s, font=FONT, font_size=size, color=color, weight=weight)


def picture(path: Path, height: float) -> ImageMobject:
    from PIL import Image

    png = EQ_DIR / (path.stem + ".png")
    if not png.exists():
        Image.open(path).convert("RGBA").save(png)
    return ImageMobject(str(png)).set_height(height)


class Narrated(Scene):
    seg = ""

    def setup(self):
        self.total = DUR.get(self.seg, 20.0)
        self.text = NARR[self.seg]

    def at(self, phrase: str):
        """Wait until the narration reaches phrase."""
        i = self.text.find(phrase)
        if i < 0:
            raise ValueError(phrase)
        target = self.total * i / len(self.text)
        now = self.renderer.time
        if target > now + 0.02:
            self.wait(target - now)

    def finish(self):
        left = self.total - self.renderer.time
        if left > 0.02:
            self.wait(left)


class S01(Narrated):
    seg = "01_hook"

    def construct(self):
        img = picture(APP / "brand" / "hero-radar.webp", 8.0).set_opacity(0.0)
        self.add(img)
        clouds = VGroup()
        rng = np.random.default_rng(4)
        for _ in range(46):
            c = Circle(radius=rng.uniform(0.6, 1.5), fill_color=WHITE, fill_opacity=0.16, stroke_width=0)
            c.move_to([rng.uniform(-7.5, 7.5), rng.uniform(-3.6, 3.6), 0])
            clouds.add(c)
        river = VMobject(stroke_color=BLUE, stroke_width=6).set_points_smoothly(
            [[-6.5, -1.5, 0], [-3, -0.6, 0], [0, -1.3, 0], [3, -0.5, 0], [6.5, -1.2, 0]]
        )
        self.play(Create(river), run_time=1.5)
        self.play(FadeIn(clouds, lag_ratio=0.02), run_time=1.5)
        self.at("Radar sees")
        beams = VGroup(*[
            Line([x + 1.2, 4.2, 0], [x, -4.2, 0], color=TEAL, stroke_width=3) for x in np.linspace(-5, 5, 7)
        ])
        self.play(LaggedStart(*[Create(b) for b in beams], lag_ratio=0.1), run_time=1.2)
        self.play(clouds.animate.set_opacity(0.04), img.animate.set_opacity(0.9), FadeOut(river), FadeOut(beams), run_time=1.2)
        self.at("This is SARtale")
        panel = RoundedRectangle(width=7.2, height=2.3, corner_radius=0.15, fill_color=BG, fill_opacity=0.82, stroke_width=0)
        title = txt("SARtale", 76, TEAL, BOLD)
        sub = txt("9 passes of NISAR, July to October 2026", 28)
        g = VGroup(title, sub).arrange(DOWN, buff=0.25)
        panel.move_to(g)
        self.play(FadeIn(panel), Write(title), FadeIn(sub, shift=UP * 0.2), run_time=1.5)
        self.at("What changed")
        q = VGroup(txt("What changed?", 34, AMBER), txt("When?", 34, AMBER), txt("How far can we trust it?", 34, AMBER)).arrange(RIGHT, buff=0.6)
        q.next_to(panel, DOWN, buff=0.35)
        bar = BackgroundRectangle(q, color=BG, fill_opacity=0.82, buff=0.15)
        self.play(FadeIn(bar), LaggedStart(*[FadeIn(m, shift=UP * 0.2) for m in q], lag_ratio=0.6), run_time=2.2)
        self.finish()


class S02(Narrated):
    seg = "02_radar"

    def construct(self):
        sat = VGroup(Rectangle(width=0.6, height=0.35, fill_color=INK, fill_opacity=1, stroke_width=0),
                     Rectangle(width=0.9, height=0.18, fill_color=TEAL, fill_opacity=1, stroke_width=0).shift(LEFT * 0.75),
                     Rectangle(width=0.9, height=0.18, fill_color=TEAL, fill_opacity=1, stroke_width=0).shift(RIGHT * 0.75)).move_to([0, 3.1, 0])
        water = Line([-6.3, -1.2, 0], [-0.8, -1.2, 0], color=BLUE, stroke_width=6)
        pts = [[0.8 + i * 0.55, -1.2 + (0.35 if i % 2 else -0.15), 0] for i in range(11)]
        rough = VMobject(stroke_color=AMBER, stroke_width=6).set_points_as_corners(pts)
        lab1 = txt("calm water", 26, BLUE).next_to(water, DOWN, buff=0.25)
        lab2 = txt("rough ground, buildings", 26, AMBER).next_to(rough, DOWN, buff=0.3)
        self.play(FadeIn(sat, shift=DOWN * 0.3), run_time=1)
        down1, down2 = Arrow(sat.get_center(), [-3.5, -1.15, 0], color=TEAL, buff=0.1), Arrow(sat.get_center(), [3.5, -0.95, 0], color=TEAL, buff=0.1)
        self.play(GrowArrow(down1), GrowArrow(down2), run_time=1.2)
        self.at("Calm water")
        away = Arrow([-3.5, -1.15, 0], [-6.8, 2.2, 0], color=BLUE, buff=0)
        self.play(FadeIn(water), FadeIn(lab1), GrowArrow(away), run_time=1.5)
        self.at("Rough ground")
        back = VGroup(*[Arrow([3.5, -0.95, 0], [3.5 + dx, 1.4, 0], color=AMBER, buff=0, stroke_width=4) for dx in (-2.3, -1.2, -0.3, 0.8, 2)])
        self.play(Create(rough), FadeIn(lab2), LaggedStart(*[GrowArrow(a) for a in back], lag_ratio=0.1), run_time=1.6)
        self.at("We express")
        scene = VGroup(sat, water, rough, lab1, lab2, down1, down2, away, back)
        self.play(FadeOut(scene), run_time=0.7)
        e = eq(r"\gamma^0_{\mathrm{dB}} = 10\,\log_{10}(\gamma^0)", "db", 1.0).shift(UP * 1.6)
        self.play(Write(e), run_time=1.5)
        self.at("A rise of ten")
        line = NumberLine(x_range=[-30, 10, 10], length=10, include_numbers=False, color=MUTED).shift(DOWN * 0.1)
        ticks = VGroup(*[txt(f"{v} dB", 22, MUTED).next_to(line.n2p(v), DOWN, buff=0.2) for v in range(-30, 11, 10)])
        self.play(Create(line), FadeIn(ticks), run_time=1)
        a1 = CurvedArrow(line.n2p(-20) + UP * 0.2, line.n2p(-10) + UP * 0.2, angle=-1.0, color=AMBER)
        x10 = txt("x 10 power", 26, AMBER).next_to(a1, UP, buff=0.1)
        self.play(Create(a1), FadeIn(x10), run_time=1)
        self.at("NISAR also")
        self.play(FadeOut(VGroup(e, line, ticks, a1, x10)), run_time=0.6)

        def wave(vertical: bool, col):
            xs = np.linspace(0, 3.4, 60)
            pts = [[x, 0.32 * np.sin(x * 5), 0] for x in xs]
            m = VMobject(stroke_color=col, stroke_width=5).set_points_smoothly(pts)
            return m.rotate(PI / 2, axis=RIGHT).set_opacity(1) if False else m

        title_hh, title_hv = txt("HH", 56, TEAL, BOLD).move_to([-3.5, 2.0, 0]), txt("HV", 56, AMBER, BOLD).move_to([3.5, 2.0, 0])
        self.play(FadeIn(title_hh), run_time=0.5)
        send = wave(False, TEAL).move_to([-3.5, 0.5, 0])
        recv = wave(False, TEAL).move_to([-3.5, -1.0, 0])
        l1, l2 = txt("send horizontal", 24, MUTED).next_to(send, DOWN, buff=0.15), txt("receive horizontal", 24, MUTED).next_to(recv, DOWN, buff=0.15)
        self.play(Create(send), FadeIn(l1), Create(recv), FadeIn(l2), run_time=1.2)
        self.at("HV sends")
        self.play(FadeIn(title_hv), run_time=0.4)
        send2 = wave(False, AMBER).move_to([3.5, 0.5, 0])
        recv2 = wave(False, AMBER).rotate(PI / 2).scale(0.5).move_to([3.5, -1.2, 0])
        l3, l4 = txt("send horizontal", 24, MUTED).next_to(send2, DOWN, buff=0.15), txt("receive vertical", 24, MUTED).next_to(recv2, DOWN, buff=0.1)
        self.play(Create(send2), FadeIn(l3), Create(recv2), FadeIn(l4), run_time=1.2)
        self.finish()


def season_axes():
    ax = Axes(x_range=[190, 296, 20], y_range=[-20, -3, 5], x_length=10.8, y_length=4.5, tips=False,
              axis_config={"color": MUTED, "include_ticks": False}).shift(UP * 0.05)
    ylab = VGroup(*[txt(str(v), 20, MUTED).next_to(ax.c2p(190, v), LEFT, buff=0.15) for v in (-20, -15, -10, -5)])
    unit = txt("HH (dB)", 22, TEAL).next_to(ax.c2p(190, -3), UP, buff=0.1)
    labs = VGroup(*[txt(d, 18, MUTED).next_to(ax.c2p(x, -20), DOWN, buff=0.14) for d, x in zip(DATES, DAYS)])
    return ax, VGroup(ylab, unit, labs)


class S03(Narrated):
    seg = "03_curve"

    def construct(self):
        head = txt("Tarbela Reservoir, south-east shore", 32, INK).to_edge(UP, buff=0.3)
        ax, deco = season_axes()
        self.play(FadeIn(head), Create(ax), FadeIn(deco), run_time=1.2)
        self.at("Each dot")
        dots = VGroup(*[Dot(ax.c2p(x, v), color=TEAL, radius=0.1) for x, v in zip(DAYS, HH)])
        self.play(LaggedStart(*[GrowFromCenter(d) for d in dots], lag_ratio=0.2), run_time=2)
        self.at("In July")
        self.play(Indicate(VGroup(dots[0], dots[1]), color=AMBER, scale_factor=1.6), run_time=1.2)
        self.at("By the nineteenth")
        self.play(Indicate(dots[2], color=AMBER, scale_factor=1.8), run_time=1.2)
        self.at("The obvious")
        med = float(np.median(HH))
        line = DashedLine(ax.c2p(190, med), ax.c2p(296, med), color=AMBER)
        lab = txt("median of the other dates", 24, AMBER).next_to(line, DOWN, buff=0.1).align_to(line, LEFT).shift(RIGHT * 0.15)
        self.play(Create(line), FadeIn(lab), run_time=1.2)
        self.at("Here, that fails")
        rule = eq(r"\mathrm{score}\ \ 1.17\ <\ 3.5", "z", 0.5, AMBER).move_to(ax.c2p(250, -7))
        arrow = Arrow(rule.get_bottom(), dots[2].get_center(), color=AMBER, buff=0.15)
        self.play(FadeIn(rule), GrowArrow(arrow), run_time=1.2)
        self.at("Most of the season")
        band = Rectangle(width=ax.c2p(296, 0)[0] - ax.c2p(226, 0)[0], height=ax.c2p(0, -11.5)[1] - ax.c2p(0, -18)[1],
                         fill_color=TEAL, fill_opacity=0.12, stroke_width=0).move_to(ax.c2p(261, -14.75))
        self.play(FadeIn(band), run_time=1)
        self.finish()


class S04(Narrated):
    seg = "04_step"

    def construct(self):
        ax, deco = season_axes()
        ax.shift(LEFT * 1.2).scale(0.82)
        deco.shift(LEFT * 1.2).scale(0.82)
        ax, deco = season_axes()
        dots = VGroup(*[Dot(ax.c2p(x, v), color=TEAL, radius=0.09) for x, v in zip(DAYS, HH)])
        self.add(ax, deco, dots)
        k = ValueTracker(4)

        def mid(i):
            return (DAYS[i - 1] + DAYS[i]) / 2

        split = always_redraw(lambda: DashedLine(ax.c2p(mid(int(round(k.get_value()))), -20), ax.c2p(mid(int(round(k.get_value()))), -3), color=INK))

        def means():
            i = int(round(k.get_value()))
            return float(np.mean(HH[:i])), float(np.mean(HH[i:])), i

        before = always_redraw(lambda: Line(ax.c2p(190, means()[0]), ax.c2p(mid(means()[2]), means()[0]), color=AMBER, stroke_width=6))
        after = always_redraw(lambda: Line(ax.c2p(mid(means()[2]), means()[1]), ax.c2p(296, means()[1]), color=BLUE, stroke_width=6))
        gap = always_redraw(lambda: DoubleArrow(ax.c2p(mid(means()[2]) + 3, means()[0]), ax.c2p(mid(means()[2]) + 3, means()[1]), color=RED, buff=0, stroke_width=4, tip_length=0.16))
        self.at("Suppose")
        self.play(Create(split), run_time=0.9)
        self.at("Split the season")
        self.play(Create(before), Create(after), run_time=1.2)
        self.at("The gap between")
        self.play(GrowFromCenter(gap), run_time=0.6)
        de = eq(r"\Delta = \bar{x}_{\mathrm{after}} - \bar{x}_{\mathrm{before}}", "step", 0.62, RED).to_corner(UR, buff=0.35)
        self.play(Write(de), run_time=1)
        self.at("Now slide")
        for target in (5, 6, 5, 4, 3, 2):
            self.play(k.animate.set_value(target), run_time=0.55, rate_func=linear)
        self.at("A big gap")
        scatter = VGroup(*[Line(d.get_center(), ax.c2p(x, np.mean(HH[:2]) if j < 2 else np.mean(HH[2:])), color=MUTED, stroke_width=3)
                           for j, (d, x) in enumerate(zip(dots, DAYS))])
        self.play(Create(scatter), run_time=1)
        self.at("That gives")
        te = eq(r"t = \frac{|\Delta|}{s\,\sqrt{1/n_1 + 1/n_2}}", "t", 1.15, AMBER).next_to(de, DOWN, buff=0.25, aligned_edge=RIGHT)
        bg = BackgroundRectangle(te, color=BG, fill_opacity=0.9, buff=0.1)
        self.play(FadeIn(bg), Write(te), run_time=1.5)
        self.at("For this shore")
        res = VGroup(txt("best split: 26 Jul to 19 Aug", 28, INK), txt("HH about -8 dB, HV about -5 dB", 26, TEAL), txt("stability about 6", 26, AMBER)).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        res.move_to(ax.c2p(255, -7.2))
        rb = BackgroundRectangle(res, color=BG, fill_opacity=0.9, buff=0.14)
        self.play(FadeIn(rb), LaggedStart(*[FadeIn(r, shift=UP * 0.15) for r in res], lag_ratio=0.5), run_time=2)
        self.finish()


class S05(Narrated):
    seg = "05_rule"

    def construct(self):
        head = txt("A pixel is flagged only if", 38, INK, BOLD).to_edge(UP, buff=0.5)
        self.play(FadeIn(head), run_time=0.8)
        a = eq(r"\mathrm{sign}(\Delta_{HH}) = \mathrm{sign}(\Delta_{HV})", "r1", 0.5)
        b = eq(r"\frac{|\Delta_{HH}| + |\Delta_{HV}|}{2} \geq 3\ \mathrm{dB}", "r2", 0.95)
        c = eq(r"\sqrt{(t_{HH}^2 + t_{HV}^2)/2} \geq 3", "r3", 0.72)
        rows = VGroup(a, b, c).arrange(DOWN, buff=0.45).shift(DOWN * 0.1)
        self.at("HH and HV must")
        self.play(Write(a), run_time=1.1)
        self.at("Their average")
        self.play(Write(b), run_time=1.1)
        self.at("And their combined")
        self.play(Write(c), run_time=1.1)
        self.at("The map groups")
        self.play(FadeOut(VGroup(head, rows)), run_time=0.6)
        base = picture(APP / "data" / "frames" / "2026-10-18_HH.webp", 6.0).set_opacity(0.75)
        over = picture(APP / "data" / "frames" / "step_date.webp", 6.0)
        over.match_height(base).move_to(base)
        self.play(FadeIn(base), run_time=0.8)
        self.play(FadeIn(over), run_time=1.2)
        self.finish()


class S06(Narrated):
    seg = "06_shuffle"

    def construct(self):
        head = txt("Is it just noise?", 40, INK, BOLD).to_edge(UP, buff=0.4)
        self.play(FadeIn(head), run_time=0.7)
        self.at("Shuffle the dates")
        rows = VGroup()
        rng = np.random.default_rng(2)
        cells = VGroup()
        for r in range(5):
            for c in range(8):
                v = float(np.clip(0.5 + rng.normal(0, 0.25), 0, 1))
                cells.add(Square(0.34, fill_color=interpolate_color(ManimColor("#123"), ManimColor(TEAL), v), fill_opacity=1, stroke_width=0).move_to([-5.0 + c * 0.38, 1.0 - r * 0.38, 0]))
        self.play(FadeIn(cells), run_time=0.7)
        for _ in range(3):
            order = rng.permutation(len(cells))
            self.play(*[cells[i].animate.move_to(cells[int(order[i])].get_center()) for i in range(len(cells))], run_time=0.5)
        ax_h = 3.3
        base = -1.9

        def bar(x, value, col, label, val):
            h = ax_h * value / 1.5
            r = Rectangle(width=1.45, height=h, fill_color=col, fill_opacity=0.95, stroke_width=0).move_to([x, base + h / 2, 0])
            l = txt(label, 22, MUTED).next_to([x, base, 0], DOWN, buff=0.15)
            n = txt(val, 28, col, BOLD).next_to(r, UP, buff=0.1)
            return r, l, n

        self.at("The real order")
        r1, l1, n1 = bar(0.0, 1.39, TEAL, "real order", "1.39%")
        self.play(GrowFromEdge(r1, DOWN), FadeIn(l1), FadeIn(n1), run_time=1)
        self.at("The shuffled version")
        r2, l2, n2 = bar(2.6, 0.25, MUTED, "shuffled pixels", "0.25%")
        self.play(GrowFromEdge(r2, DOWN), FadeIn(l2), FadeIn(n2), run_time=1)
        self.at("Shuffling the whole")
        r3, l3, n3 = bar(5.2, 1.26, AMBER, "highest of 200\nwhole-scene shuffles", "1.26%")
        self.play(GrowFromEdge(r3, DOWN), FadeIn(l3), FadeIn(n3), run_time=1)
        self.at("Stable ground")
        ctl = VGroup(txt("Peshawar city: 0%", 26, TEAL), txt("Tarbela main pool: 0%", 26, TEAL)).arrange(DOWN, aligned_edge=LEFT, buff=0.15).move_to([-3.6, -1.6, 0])
        self.play(FadeIn(ctl, shift=UP * 0.2), run_time=1)
        self.at("One caution")
        cau = txt("Rule set with known sites in view: not a blind test", 26, AMBER).next_to(head, DOWN, buff=0.14)
        self.play(FadeIn(cau), run_time=0.8)
        self.finish()


class S07(Narrated):
    seg = "07_missed"

    def construct(self):
        head = txt("What the radar could not see", 38, INK, BOLD).to_edge(UP, buff=0.45)
        line = NumberLine(x_range=[180, 295, 30], length=12.2, include_numbers=False, include_ticks=False, color=MUTED).shift(DOWN * 0.1)
        self.play(FadeIn(head), Create(line), run_time=1)
        passes = [(183, "2 Jul"), (195, "14 Jul"), (207, "26 Jul"), (231, "19 Aug"), (243, "31 Aug"), (255, "12 Sep"), (267, "24 Sep"), (279, "6 Oct"), (291, "18 Oct")]
        dots = VGroup(*[Dot(line.n2p(d), color=TEAL, radius=0.11) for d, _ in passes])
        labs = VGroup(*[txt(n, 18, MUTED).next_to(line.n2p(d), DOWN, buff=0.22) for d, n in passes])
        self.play(LaggedStart(*[GrowFromCenter(d) for d in dots], lag_ratio=0.1), FadeIn(labs), run_time=1.4)
        self.at("On the second")
        cross = Cross(dots[0], stroke_color=RED, scale_factor=1.8)
        note = VGroup(txt("HV up about 14 dB", 26, RED), txt("likely radio interference", 24, MUTED)).arrange(DOWN, buff=0.08, aligned_edge=LEFT)
        note.next_to(line.n2p(183), DOWN, buff=0.6).align_to(line, LEFT)
        self.play(Create(cross), FadeIn(note, shift=DOWN * 0.15), run_time=1.1)
        self.at("The highest listed")
        peak = Arrow(line.n2p(204) + UP * 2.0, line.n2p(204) + UP * 0.12, color=AMBER, buff=0)
        pk = VGroup(txt("23 Jul: highest listed flow, Nowshera", 26, AMBER), txt("78,500 cusecs", 24, MUTED)).arrange(DOWN, buff=0.06)
        pk.next_to(peak, UP, buff=0.1).shift(RIGHT * 1.0)
        self.play(GrowArrow(peak), FadeIn(pk), run_time=1.2)
        self.at("And NISAR has")
        w = line.n2p(222)[0] - line.n2p(208)[0]
        gap = Rectangle(width=w, height=0.5, fill_color=AMBER, fill_opacity=0.35, stroke_color=AMBER, stroke_width=2).move_to(line.n2p(215))
        gl = txt("no data", 24, AMBER).next_to(gap, UP, buff=0.12)
        self.play(FadeIn(gap), FadeIn(gl), run_time=1)
        self.finish()


class S09(Narrated):
    seg = "09_close"

    def construct(self):
        a = txt("A step is not a cause.", 52, INK, BOLD).shift(UP * 0.6)
        b = txt("Plain ground flags too, cause unknown.", 32, MUTED).next_to(a, DOWN, buff=0.35)
        self.play(Write(a), run_time=1.4)
        self.play(FadeIn(b), run_time=0.8)
        self.at("The data is")
        c = txt("Provisional data. Not a warning service.", 30, AMBER).next_to(b, DOWN, buff=0.35)
        self.play(FadeIn(c), run_time=0.8)
        self.at("But in one")
        self.play(FadeOut(VGroup(a, b, c)), run_time=0.6)
        q = VGroup(txt("What radar saw", 40, TEAL), txt("When it changed", 40, TEAL), txt("How much to trust it", 40, TEAL)).arrange(DOWN, buff=0.3)
        self.play(LaggedStart(*[FadeIn(x, shift=UP * 0.2) for x in q], lag_ratio=0.7), run_time=2.4)
        self.at("This is SARtale")
        self.play(FadeOut(q), run_time=0.5)
        logo = picture(APP / "brand" / "logo-256.png", 3.0)
        card = RoundedRectangle(width=3.5, height=3.5, corner_radius=0.2, fill_color="#F2F6F5", fill_opacity=1, stroke_width=0)
        name = txt("Team SARcastic Scientists", 30, INK).next_to(card, DOWN, buff=0.3)
        self.play(FadeIn(card), FadeIn(logo), FadeIn(name), run_time=0.9)
        self.finish()
