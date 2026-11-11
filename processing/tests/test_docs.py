"""The documents and the code agree on the site address."""
import importlib.util
import re
from pathlib import Path

from sartale.lake_issues import SITE_LAKE

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://saeedahmad.me/SARtale/"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_address_is_the_same_everywhere():
    assert SITE_LAKE == SITE + "#lakes/"
    assert _load(ROOT / ".github" / "scripts" / "data_artifact.py", "data_artifact").SITE == SITE + "#lakes/"
    assert _load(ROOT / "docs" / "guide" / "build.py", "guide_build").SITE == SITE


def test_readme_links_the_live_site_and_guide():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f'href="{SITE}"' in readme and f'href="{SITE}guide/"' in readme
    assert "saeedahmadicp.github.io" not in readme


def test_guide_relative_links_resolve():
    guide = ROOT / "docs" / "guide"
    for page in guide.glob("*.html"):
        for href in re.findall(r'(?:href|src)="([^"#:]+)(?:#[^"]*)?"', page.read_text(encoding="utf-8")):
            if href.startswith("../media/"):
                # On the site the guide sits next to media/, which the app build copies from the repository's
                # media/ folder, writing each .vtt from its .srt.
                target = ROOT / "media" / re.sub(r"\.vtt$", ".srt", href[len("../media/"):])
            else:
                target = guide / href
            assert target.exists(), f"{page.name}: {href}"


def test_d03_worked_example_is_reproducible_from_the_lake_data_it_names():
    """The README and guide state which build their Attabad example comes from. When that is the shipped
    lakes.json, every number must be what build.py computes from it now; after a later data refresh the example is
    a dated snapshot of an older build and must say so (its date is older than the shipped build)."""
    import json
    from datetime import datetime
    build = _load(ROOT / "docs" / "guide" / "build.py", "guide_build")
    doc = json.loads(build.LAKES_JSON.read_text(encoding="utf-8"))
    ex = build.worked_example(doc)
    method = (ROOT / "docs" / "guide" / "method.html").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    stated = set(re.findall(r"lake data built (\d{1,2} \w{3} \d{4})", method + readme))
    assert len(stated) == 1, stated
    (when,) = stated
    if when == ex["EX_BUILT"]:
        assert build.readme_example(ex) in readme
        i = [p[0] for p in build.PAGES].index("method")
        assert method.replace("\r\n", "\n") == build.page(i, ex).replace("\r\n", "\n")
        assert "{{EX_" not in method
    else:
        assert datetime.strptime(when, "%d %b %Y") < datetime.strptime(ex["EX_BUILT"], "%d %b %Y")
