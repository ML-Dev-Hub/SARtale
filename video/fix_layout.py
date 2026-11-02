p = "scenes.py"
t = open(p, encoding="utf8").read()
R = [
    # room for subtitles under the season charts
    ('x_length=10.8, y_length=4.9, tips=False,', 'x_length=10.8, y_length=4.5, tips=False,'),
    ('"include_ticks": False}).shift(DOWN * 0.45)', '"include_ticks": False}).shift(UP * 0.05)'),
    # HV wave clear of its label
    ('recv2 = wave(False, AMBER).rotate(PI / 2).scale(0.7).move_to([3.5, -1.0, 0])', 'recv2 = wave(False, AMBER).rotate(PI / 2).scale(0.5).move_to([3.5, -1.2, 0])'),
    # shuffle bars apart, caution clear of subtitles
    ('r1, l1, n1 = bar(0.6, 1.39', 'r1, l1, n1 = bar(0.0, 1.39'),
    ('r2, l2, n2 = bar(2.6, 0.25', 'r2, l2, n2 = bar(2.6, 0.25'),
    ('r3, l3, n3 = bar(4.6, 1.26', 'r3, l3, n3 = bar(5.2, 1.26'),
    ('cau = txt("Rule set with known sites in view: not a blind test", 26, AMBER).to_edge(DOWN, buff=0.12)', 'cau = txt("Rule set with known sites in view: not a blind test", 26, AMBER).next_to(head, DOWN, buff=0.14)'),
    ('self.play(FadeOut(VGroup(l1, l2, l3), run_time=0.3), FadeIn(cau), run_time=0.8)', 'self.play(FadeIn(cau), run_time=0.8)'),
    ('ax_h = 3.8\n        base = -2.1', 'ax_h = 3.3\n        base = -1.9'),
    # interference note under the line, flow label below the title
    ('note.next_to(line.n2p(183), UP, buff=0.6).align_to(line, LEFT)', 'note.next_to(line.n2p(183), DOWN, buff=0.6).align_to(line, LEFT)'),
    ('peak = Arrow(line.n2p(204) + UP * 2.6, line.n2p(204) + UP * 0.12, color=AMBER, buff=0)', 'peak = Arrow(line.n2p(204) + UP * 2.0, line.n2p(204) + UP * 0.12, color=AMBER, buff=0)'),
    ('pk.next_to(peak, UP, buff=0.1).shift(RIGHT * 1.2)', 'pk.next_to(peak, UP, buff=0.1).shift(RIGHT * 1.0)'),
    ('gl = txt("no data", 22, AMBER).next_to(gap, DOWN, buff=0.5)', 'gl = txt("no data", 24, AMBER).next_to(gap, UP, buff=0.12)'),
    ('Rectangle(width=w, height=0.5, fill_color=AMBER, fill_opacity=0.25', 'Rectangle(width=w, height=0.5, fill_color=AMBER, fill_opacity=0.35'),
    ('line = NumberLine(x_range=[180, 295, 30], length=12.2, include_numbers=False, color=MUTED).shift(DOWN * 0.4)', 'line = NumberLine(x_range=[180, 295, 30], length=12.2, include_numbers=False, include_ticks=False, color=MUTED).shift(DOWN * 0.1)'),
]
for a, b in R:
    assert a in t, a
    t = t.replace(a, b)
open(p, "w", encoding="utf8").write(t)
print("ok")
