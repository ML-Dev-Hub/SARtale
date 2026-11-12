"""Builds the SARtale guide: wraps each page in pages/ in the shared layout and writes docs/guide/<page>.html.

    python docs/guide/build.py

Standard library only. Edit the page bodies in pages/ and the navigation below, then run this again.
"""
import json
import re
from html import escape
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAKES_JSON = ROOT / "app" / "public" / "data" / "lakes.json"
README = ROOT / "README.md"
# README.md holds the worked example between these markers; main() rewrites it from lakes.json.
EX_START, EX_END = "<!-- worked-example:start -->", "<!-- worked-example:end -->"
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
REPO = "https://github.com/saeedahmadicp/SARtale"
# The live site. Page bodies write {{SITE}} where they need it; the README and the code keep their own copy
# (README.md, processing/sartale/lake_issues.py, .github/scripts/data_artifact.py), pinned equal by processing/tests/test_docs.py.
SITE = "https://saeedahmad.me/SARtale/"

# (file, title in the menu, group)
PAGES = [
    ("index", "Overview", "Start here"),
    ("getting-started", "Getting started", "Start here"),
    ("user-guide", "Using the website", "Start here"),
    ("method", "The method", "How it works"),
    ("pipeline", "Pipeline", "How it works"),
    ("data", "Data files", "How it works"),
    ("app", "Web app", "Build and run"),
    ("lake-requests", "Lake requests", "Build and run"),
    ("deploy", "Deploying", "Build and run"),
    ("contributing", "Contributing", "Project"),
    ("faq", "Questions and limits", "Project"),
]

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Inter+Tight:wght@600;650;700&amp;display=swap">'
)


def nav(current: str) -> str:
    out, group = [], None
    for file, title, g in PAGES:
        if g != group:
            if group is not None:
                out.append("</ul>")
            out.append(f"<h2>{escape(g)}</h2><ul>")
            group = g
        cur = ' aria-current="page"' if file == current else ""
        out.append(f'<li><a href="{file}.html"{cur}>{escape(title)}</a></li>')
    out.append("</ul>")
    return "".join(out)


def anchors(body: str) -> str:
    """Give every h2/h3 an id from its text and a visible link, so sections can be linked."""
    seen: set[str] = set()

    def sub(m: re.Match) -> str:
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if "id=" in attrs:
            return m.group(0)
        slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", inner).lower()).strip("-") or tag
        base, n = slug, 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        return f'<{tag} id="{slug}"{attrs}>{inner}<a class="anchor" href="#{slug}" aria-label="Link to this section">#</a></{tag}>'

    return re.sub(r"<(h[23])([^>]*)>(.*?)</\1>", sub, body, flags=re.S)


def _day(iso: str, short: bool = False) -> str:
    y, m, d = (int(v) for v in iso[:10].split("-"))
    return f"{d} {_MONTHS[m - 1][:3] if short else _MONTHS[m - 1]} {y}"


class WorkedExampleError(ValueError):
    """The lake data cannot give the Attabad worked example."""


def worked_example(doc: dict) -> dict[str, str]:
    """The Attabad worked example, computed from lakes.json the way the level is (lakestatus.assess): the latest
    compared pass, its baseline (the median of up to 6 earlier valid passes on its own track, checked against the one
    the build recorded), the change, the noise and z the build recorded, and the level. Every number in the guide's
    and the README's example comes from here, with the build it was taken from.

    Raises WorkedExampleError, with what is missing, when the build has no measured Attabad status to quote (no
    Attabad entry, a status without a change, noise, track or latest date, or fewer than two valid passes)."""
    lake = next((lk for lk in doc.get("lakes", []) if lk.get("id") == "attabad"), None)
    if lake is None:
        raise WorkedExampleError("the lake data have no Attabad entry")
    st, c = lake["status"], doc["constants"]
    frozen_note = ""
    if is_frozen_now(lake):
        # A frozen lake's newest pass is no water measurement: quote its last open-water pass (lakes-freeze's
        # `last_open`, with the assessment it had then) and say so.
        lo = lake.get("last_open")
        if not lo:
            raise WorkedExampleError("Attabad is frozen and the lake data give no last open-water pass to quote")
        f = lake.get("freeze") or {}
        since = f.get("freeze_up") or f.get("since")
        frozen_note = (f" Attabad Lake is frozen now{f' (since {_day(since)})' if since else ''}; this was its last "
                       "open-water pass.")
        st = {**st, "status": lo["status"], "track": lo["track"], "latest_date": lo["date"],
              "change_km2": lo["change_km2"], "noise_km2": lo["noise_km2"], "z": lo.get("z"),
              "baseline_km2": lo.get("ref_km2")}
    missing = [k for k in ("track", "latest_date", "change_km2", "noise_km2") if st.get(k) is None]
    if missing:
        raise WorkedExampleError(f"Attabad's status is {st.get('status')!r} with no {', '.join(missing)}, so there is "
                                 "no measured change to quote")
    track = st["track"]
    pts = sorted((p for p in lake["series"] if p["track"] == track and p["excluded"] is None and not p.get("frozen")
                  and p["area_km2"] is not None and (p["observable_share"] or 0) >= c["min_observable"]),
                 key=lambda p: p["date"])
    pts = [p for p in pts if p["date"] <= st["latest_date"]]
    if len(pts) < 2:
        raise WorkedExampleError(f"Attabad has {len(pts)} valid pass(es) on track {track}; the example needs a latest "
                                 "pass and earlier ones")
    # The baseline is the median of up to BASELINE_PASSES earlier valid passes on the track (all of them in builds
    # made before the levels, which recorded no baseline).
    window = int(c.get("baseline_passes") or 0) or len(pts) - 1
    latest, earlier = pts[-1], [p["area_km2"] for p in pts[:-1]][-window:]
    ref = median(earlier)
    if st.get("baseline_km2") is not None and abs(ref - st["baseline_km2"]) > 1e-6:
        raise WorkedExampleError(f"Attabad's recorded baseline {st['baseline_km2']} km2 is not the median of its "
                                 f"{len(earlier)} earlier passes ({ref:.6f} km2)")
    z = st.get("z")
    if z is None:
        z = st["change_km2"] / st["noise_km2"]
    share = next((m.group(1) for t in lake["limits"] for m in [re.search(r"(\d+)% of it is inside", t)] if m), None)
    return {
        "EX_DATE": _day(st["latest_date"]), "EX_TRACK": track, "EX_AREA": f"{latest['area_km2']:.3f}",
        "EX_AREA2": f"{latest['area_km2']:.2f}", "EX_REF": f"{ref:.3f}", "EX_EARLIER": str(len(earlier)),
        "EX_CHANGE": _signed(st["change_km2"], 3), "EX_CHANGE2": _signed(st["change_km2"], 2),
        "EX_NOISE": f"{st['noise_km2']:.3f}", "EX_NOISE2": f"{st['noise_km2']:.2f}", "EX_Z": _signed(z, 1),
        "EX_FACTOR": f"{c['change_factor']:g}", "EX_THRESHOLD": f"{c['change_factor'] * st['noise_km2']:.3f}",
        "EX_STATUS": st["status"], "EX_BUILT": _day(doc["built"], short=True),
        "EX_SHARE": (f"Only {share}% of Attabad's outline falls inside the 6 km window, so its area is the part "
                     "inside the window.") if share else "All of Attabad's outline falls inside the 6 km window.",
        "EX_FROZEN": frozen_note,
    }


def _signed(v: float, digits: int) -> str:
    """"+0.012" / "−0.012" (a true minus sign); a value that rounds to zero has no sign."""
    t = f"{abs(v):.{digits}f}"
    return t if float(t) == 0 else ("+" if v > 0 else "−") + t


FROZEN_STATUSES = ("Frozen (likely)", "Frozen (seen by Sentinel-2)", "Break-up likely")


def is_frozen_now(lake: dict) -> bool:
    """True when the lake is frozen or breaking up, or its pictured pass was taken while it was (as
    sartale.freeze.needs_last_open): its newest pass is then no water measurement."""
    if lake["status"].get("status") in FROZEN_STATUSES:
        return True
    im = lake.get("images") or {}
    return any(p.get("frozen") and p["date"] == im.get("date") and p["track"] == im.get("track")
               for p in lake.get("series", []))


def readme_example(ex: dict[str, str]) -> str:
    return (f"{EX_START}\nFor example, Attabad on {ex['EX_DATE']} held {ex['EX_AREA2']} km² on track {ex['EX_TRACK']}, "
            f"a change of {ex['EX_CHANGE2']} km² against the median of its earlier passes on that track and a noise of "
            f"{ex['EX_NOISE2']} km² (z = {ex['EX_Z']}), so it reads **{ex['EX_STATUS']}** (from the lake data built "
            f"{ex['EX_BUILT']}; the app shows the current numbers)."
            f"{ex.get('EX_FROZEN', '')}\n"
            f"{EX_END}")


def fill(text: str, ex: dict[str, str]) -> str:
    text = text.replace("{{SITE}}", SITE)
    return re.sub(r"\{\{(EX_[A-Z0-9]+)\}\}", lambda m: ex[m.group(1)], text)


def page(i: int, ex: dict[str, str] | None = None) -> str:
    file, title, _ = PAGES[i]
    ex = ex if ex is not None else worked_example(json.loads(LAKES_JSON.read_text(encoding="utf8")))
    body = anchors(fill((HERE / "pages" / f"{file}.html").read_text(encoding="utf8"), ex))
    prev = PAGES[i - 1] if i > 0 else None
    nxt = PAGES[i + 1] if i + 1 < len(PAGES) else None
    pager = '<nav class="pager" aria-label="Next and previous page">'
    pager += f'<a href="{prev[0]}.html"><small>Previous</small>{escape(prev[1])}</a>' if prev else "<span></span>"
    pager += f'<a href="{nxt[0]}.html" style="text-align:right"><small>Next</small>{escape(nxt[1])}</a>' if nxt else "<span></span>"
    pager += "</nav>"
    head_title = "SARtale guide" if file == "index" else f"{title} · SARtale guide"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(head_title)}</title>
<meta name="description" content="SARtale guide: watching glacial lakes in northern Pakistan through cloud with NISAR radar.">
<link rel="icon" href="assets/logo.png">
{FONTS}
<link rel="stylesheet" href="assets/guide.css">
</head>
<body>
<a class="skip" href="#content">Skip to the content</a>
<header class="bar">
  <a class="brand" href="index.html"><img src="assets/logo.png" alt=""> SARtale <small>Guide</small></a>
  <nav class="bar-links" aria-label="Project links">
    <a href="getting-started.html">Get started</a>
    <a href="lake-requests.html">Lake requests</a>
    <a href="{REPO}">GitHub</a>
  </nav>
</header>
<div class="frame">
  <aside class="rail" aria-label="Guide contents">{nav(file)}</aside>
  <main id="content">
    <details class="menu"><summary>Guide contents</summary><nav aria-label="Guide contents">{nav(file)}</nav></details>
    <article class="doc{' wide' if file == 'index' else ''}">
{body}
    </article>
    {pager}
    <footer class="foot">SARtale, by team SARcastic Scientists for NASA Space Apps Challenge 2026. Code under the Apache License 2.0. Indicative screening on provisional NISAR data, not a warning service.</footer>
  </main>
</div>
</body>
</html>
"""


def main() -> None:
    try:
        ex = worked_example(json.loads(LAKES_JSON.read_text(encoding="utf8")))
    except WorkedExampleError as e:
        raise SystemExit(f"build.py: cannot write the Attabad worked example from {LAKES_JSON.name}: {e}. "
                         "Nothing was written.") from None
    for i, (file, _, _) in enumerate(PAGES):
        (HERE / f"{file}.html").write_text(page(i, ex), encoding="utf8", newline="\n")
    text = README.read_text(encoding="utf8")
    block = re.compile(re.escape(EX_START) + ".*?" + re.escape(EX_END), re.S)
    if block.search(text):
        README.write_bytes(block.sub(lambda _: readme_example(ex), text).encode("utf8"))
    print(f"built {len(PAGES)} pages in {HERE}; worked example from the lake data built {ex['EX_BUILT']}")


if __name__ == "__main__":
    main()
