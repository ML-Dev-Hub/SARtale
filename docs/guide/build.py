"""Builds the SARtale guide: wraps each page in pages/ in the shared layout and writes docs/guide/<page>.html.

    python docs/guide/build.py

Standard library only. Edit the page bodies in pages/ and the navigation below, then run this again.
"""
import re
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "https://github.com/saeedahmadicp/SARtale"

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


def page(i: int) -> str:
    file, title, _ = PAGES[i]
    body = anchors((HERE / "pages" / f"{file}.html").read_text(encoding="utf8"))
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
    for i, (file, _, _) in enumerate(PAGES):
        (HERE / f"{file}.html").write_text(page(i), encoding="utf8")
    print(f"built {len(PAGES)} pages in {HERE}")


if __name__ == "__main__":
    main()
