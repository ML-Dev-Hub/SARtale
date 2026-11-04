"""Still screenshots of the running app (http://localhost:5173/) for the story video, at 1600x1000.

Writes out/app/{watch,detail,chart,brief}.png. Run in the sartale-video env with the dev server up.
"""
import base64
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from capture import Page  # noqa: E402

OUT = HERE / "out" / "app"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1600, 1000


def shot(p, name):
    d = p.send("Page.captureScreenshot", format="png")["data"]
    (OUT / f"{name}.png").write_bytes(base64.b64decode(d))
    print("saved", name)


def click_row(p, name):
    ok = p.js("(()=>{const b=[...document.querySelectorAll('button')].filter(e=>e.offsetParent!==null&&e.textContent.includes(%s))[0];"
              "if(b){b.scrollIntoView({block:'center'});b.click();return true}return false})()" % json.dumps(name))
    if not ok:
        raise RuntimeError("no row: " + name)


def scroll_to(p, text, by=-100):
    p.js("(()=>{const e=[...document.querySelectorAll('h2,h3,h4,p,figure')].find(e=>e.offsetParent!==null&&e.textContent.includes(%s));"
         "if(e)e.scrollIntoView({block:'start'})})()" % json.dumps(text))
    p.js(f"window.scrollBy(0,{by})")


def main():
    p = Page()
    try:
        p.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
        p.send("Page.navigate", url="http://localhost:5173/")
        time.sleep(7)
        p.js("window.print=()=>{}")
        p.click("Lake Watch")
        time.sleep(4)
        shot(p, "watch")
        click_row(p, "Attabad")
        time.sleep(2.5)
        p.js("window.scrollTo(0,0);document.querySelectorAll('*').forEach(e=>{if(e.scrollTop)e.scrollTop=0})")
        scroll_to(p, "Attabad Lake (landslide")
        time.sleep(1.2)
        shot(p, "detail")
        scroll_to(p, "Area by track", -60)
        time.sleep(1.2)
        shot(p, "chart")
        p.click("Print lake brief")
        time.sleep(1)
        p.send("Emulation.setEmulatedMedia", media="print")
        p.js("(()=>{const b=document.querySelector('.lake-brief');if(b){b.style.zoom='1.3';b.style.padding='24px 56px'};window.scrollTo(0,0)})()")
        time.sleep(1.5)
        shot(p, "brief")
    finally:
        print("errors", p.errors)
        p.ws.close()
        p.proc.terminate()


if __name__ == "__main__":
    main()
