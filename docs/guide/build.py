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
    """The Attabad worked example, computed from lakes.json the way the status is (lakestatus.lake_status): the
    status track's valid passes, the median of the earlier ones, the change and the noise the build recorded.
    Every number in the guide's and the README's example comes from here, with the build it was taken from.

    Raises WorkedExampleError, with what is missing, when the build has no measured Attabad status to quote (no
    Attabad entry, a status without a change, noise, track or latest date, or fewer than two valid passes)."""
    lake = next((lk for lk in doc.get("lakes", []) if lk.get("id") == "attabad"), None)
    if lake is None:
        raise WorkedExampleError("the lake data have no Attabad entry")
    st, c = lake["status"], doc["constants"]
    missing = [k for k in ("track", "latest_date", "change_km2", "noise_km2") if st.get(k) is None]
    if missing:
        raise WorkedExampleError(f"Attabad's status is {st.get('status')!r} with no {', '.join(missing)}, so there is "
                                 "no measured change to quote")
    track = st["track"]
    pts = sorted((p for p in lake["series"] if p["track"] == track and p["excluded"] is None
                  and p["area_km2"] is not None and (p["observable_share"] or 0) >= c["min_observable"]),
                 key=lambda p: p["date"])
    pts = [p for p in pts if p["date"] <= st["latest_date"]]
    if len(pts) < 2:
        raise WorkedExampleError(f"Attabad has {len(pts)} valid pass(es) on track {track}; the example needs a latest "
                                 "pass and earlier ones")
    latest, earlier = pts[-1], [p["area_km2"] for p in pts[:-1]]
    share = next((m.group(1) for t in lake["limits"] for m in [re.search(r"(\d+)% of it is inside", t)] if m), None)
    return {
        "EX_DATE": _day(st["latest_date"]), "EX_TRACK": track, "EX_AREA": f"{latest['area_km2']:.3f}",
        "EX_AREA2": f"{latest['area_km2']:.2f}", "EX_REF": f"{median(earlier):.3f}", "EX_EARLIER": str(len(earlier)),
        "EX_CHANGE": f"{st['change_km2']:+.3f}", "EX_CHANGE2": f"{st['change_km2']:+.2f}",
        "EX_NOISE": f"{st['noise_km2']:.3f}", "EX_NOISE2": f"{st['noise_km2']:.2f}",
        "EX_FACTOR": f"{c['change_factor']:g}", "EX_THRESHOLD": f"{c['change_factor'] * st['noise_km2']:.3f}",
        "EX_STATUS": st["status"], "EX_BUILT": _day(doc["built"], short=True),
        "EX_SHARE": (f"Only {share}% of Attabad's outline falls inside the 6 km window, so its area is the part "
                     "inside the window.") if share else "All of Attabad's outline falls inside the 6 km window.",
    }


def readme_example(ex: dict[str, str]) -> str:
    return (f"{EX_START}\nFor example, Attabad on {ex['EX_DATE']} held {ex['EX_AREA2']} km² on track {ex['EX_TRACK']}, "
            f"a change of {ex['EX_CHANGE2']} km² against a noise of {ex['EX_NOISE2']} km², so it reads "
            f"**{ex['EX_STATUS']}** (from the lake data built {ex['EX_BUILT']}; the app shows the current numbers).\n"
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
