"""Record the 30-second Lake Watch demo from the running app (http://localhost:5173/), one clip per narrated segment.

Frames go to out/app/<id>/00000.jpg at 12 fps of video time. Run after prepare_short.py.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from capture import FPS, Page  # noqa: E402

OUT = HERE / "out" / "app"
DUR = json.load(open(HERE / "out" / "durations.json", encoding="utf8"))


class Rec:
    def __init__(self, page, seg):
        self.p, self.dir, self.n = page, OUT / seg, 0
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in self.dir.glob("*.jpg"):
            f.unlink()
        self.total = int(DUR[seg] * FPS) + 2

    def hold(self, seconds):
        for _ in range(int(seconds * FPS)):
            if self.n >= self.total:
                return
            self.p.shot(self.dir / f"{self.n:05d}.jpg")
            self.n += 1

    def rest(self):
        self.hold((self.total - self.n) / FPS)


def click_row(p, name):
    ok = p.js("(()=>{const b=[...document.querySelectorAll('button')].filter(e=>e.offsetParent!==null&&e.textContent.includes(%s))[0];"
              "if(b){b.scrollIntoView({block:'center'});b.click();return true}return false})()" % json.dumps(name))
    if not ok:
        raise RuntimeError("no row: " + name)


def scroll_to(p, text):
    p.js("(()=>{const e=[...document.querySelectorAll('h2,h3,h4,p,figure')].find(e=>e.offsetParent!==null&&e.textContent.includes(%s));"
         "if(e)e.scrollIntoView({block:'start'})})()" % json.dumps(text))


def run(p):
    p.send("Page.navigate", url="http://localhost:5173/")
    time.sleep(7)
    p.js("window.print=()=>{}")

    r = Rec(p, "01_gap")
    r.hold(DUR["01_gap"] * 0.45)          # start screen: audience, Attabad radar picture
    p.click("Start the story")
    time.sleep(2.5)
    r.rest()                               # beat 1: SUPARCO's own words

    r = Rec(p, "02_watch")
    p.click("Lake Watch")
    time.sleep(3)
    r.hold(DUR["02_watch"] * 0.35)        # headline count, locator, status list
    click_row(p, "Attabad")
    time.sleep(2.0)
    p.js("window.scrollTo(0,0);document.querySelectorAll('*').forEach(e=>{if(e.scrollTop)e.scrollTop=0})")
    scroll_to(p, "Attabad Lake (landslide")
    p.js("window.scrollBy(0,-120)")
    time.sleep(1.0)
    r.hold(DUR["02_watch"] * 0.35)        # status sentence and radar picture
    scroll_to(p, "Area by track")
    time.sleep(1.2)
    r.rest()                               # per-track chart

    r = Rec(p, "03_brief")
    p.click("Print lake brief")
    time.sleep(1)
    p.send("Emulation.setEmulatedMedia", media="print")
    p.js("(()=>{const b=document.querySelector('.lake-brief');if(b){b.style.zoom='1.55';b.style.padding='24px 48px'};window.scrollTo(0,0)})()")
    time.sleep(1.5)
    r.hold(DUR["03_brief"] * 0.62)        # the one-page brief, limits and PMD/NDMA line
    p.send("Emulation.setEmulatedMedia", media="screen")
    p.click("Lake Watch")
    p.js("(()=>{const h=document.querySelector('[data-role=home]');if(h)h.click()})()")
    time.sleep(2.5)
    r.rest()                               # back to the start screen for "built on NISAR, open source"


def main():
    p = Page()
    try:
        run(p)
    finally:
        print("errors", p.errors)
        p.ws.close()
        p.proc.terminate()


if __name__ == "__main__":
    main()
