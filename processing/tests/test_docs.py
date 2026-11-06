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
            assert (guide / href).exists(), f"{page.name}: {href}"
