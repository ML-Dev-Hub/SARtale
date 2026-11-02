"""Record the app in headless Chrome over CDP, one clip per narrated segment.

Each segment runs its actions, then frames are stepped at a fixed rate into out/app/<id>/.
Usage: capture.py [segment ids]
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket  # websocket-client

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out" / "app"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = "http://localhost:5173/"
W, H, FPS = 1920, 1080, 12
PORT = 9333
DUR = json.load(open(ROOT / "out" / "durations.json", encoding="utf8"))


class Page:
    def __init__(self):
        prof = ROOT / "out" / "chrome-profile"
        self.proc = subprocess.Popen([
            CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--window-size={W},{H}",
            f"--user-data-dir={prof}", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist", "--hide-scrollbars", "--mute-audio", "about:blank"])
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                ws = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.5)
        self.ws = websocket.create_connection(ws, max_size=None, timeout=120)
        self.id = 0
        self.errors = []
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)

    def send(self, method, **params):
        self.id += 1
        self.ws.send(json.dumps({"id": self.id, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("method") == "Runtime.exceptionThrown":
                self.errors.append(str(m["params"])[:200])
            if m.get("id") == self.id:
                return m.get("result", {})

    def js(self, code):
        r = self.send("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(str(r["exceptionDetails"])[:300])
        return r.get("result", {}).get("value")

    def shot(self, path):
        d = self.send("Page.captureScreenshot", format="jpeg", quality=92)["data"]
        path.write_bytes(base64.b64decode(d))

    def click(self, text, scope="button, a, label"):
        ok = self.js(
            "(()=>{const b=[...document.querySelectorAll(%s)].filter(e=>e.offsetParent!==null&&e.textContent.trim().startsWith(%s))[0];"
            "if(b){b.scrollIntoView({block:'nearest'});b.click();return true}return false})()" % (json.dumps(scope), json.dumps(text)))
        if not ok:
            raise RuntimeError("no control: " + text)


class Rec:
    def __init__(self, page, seg):
        self.p, self.dir, self.n = page, OUT / seg, 0
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in self.dir.glob("*.jpg"):
            f.unlink()
        self.total = int(DUR[seg] * FPS) + 2
        self.next = time.time()

    def hold(self, seconds):
        for _ in range(int(seconds * FPS)):
            if self.n >= self.total:
                return
            self.p.shot(self.dir / f"{self.n:05d}.jpg")
            self.n += 1

    def rest(self):
        self.hold((self.total - self.n) / FPS)


def set_range(p, label, value):
    p.js("(()=>{const r=document.querySelector('input[type=range]');const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
         "s.call(r,%s);r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}));return r.max})()" % json.dumps(str(value)))


def main():
    p = Page()
    try:
        run(p)
    finally:
        print("errors", p.errors)
        p.ws.close()
        p.proc.terminate()


def run(p):
    p.send("Page.navigate", url=URL)
    time.sleep(6)

    r = Rec(p, "08a_app_open")
    r.hold(max(4, DUR["08a_app_open"] * 0.42))
    p.click("Start the story")
    time.sleep(2.5)
    r.hold(DUR["08a_app_open"] * 0.2)
    p.click("Next")
    time.sleep(2.5)
    r.hold(DUR["08a_app_open"] * 0.2)
    p.click("Next")
    time.sleep(2.5)
    r.rest()

    r = Rec(p, "08b_app_dance")
    p.click("Explore freely")
    time.sleep(2.5)
    p.click("Start the story") if False else None
    r.hold(DUR["08b_app_dance"] * 0.2)
    for v in (2, 3, 4):
        set_range(p, "date", v)
        time.sleep(1.2)
        r.hold(DUR["08b_app_dance"] * 0.12)
    p.click("HV")
    time.sleep(1.2)
    r.hold(DUR["08b_app_dance"] * 0.18)
    p.click("HH")
    p.click("Before and after")
    time.sleep(1.5)
    r.rest()

    r = Rec(p, "08c_app_change")
    p.click("Before and after")
    p.click("Change")
    time.sleep(2.5)
    r.rest()

    r = Rec(p, "08d_app_sites")
    p.click("Site Stories")
    time.sleep(2)
    p.click("Tarbela Reservoir, south-east")
    time.sleep(2)
    r.hold(DUR["08d_app_sites"] * 0.55)
    p.js("(()=>{for(const e of document.querySelectorAll('*')){if(e.scrollHeight>e.clientHeight+80&&getComputedStyle(e).overflowY!='visible'&&e.textContent.includes('Hypothesis')){e.scrollTop=360}}})()")
    time.sleep(0.8)
    r.rest()

    r = Rec(p, "08e_app_evidence")
    p.click("What NISAR Missed")
    time.sleep(2)
    r.hold(DUR["08e_app_evidence"] * 0.5)
    p.click("How we know")
    time.sleep(2)
    r.rest()



if __name__ == "__main__":
    main()
