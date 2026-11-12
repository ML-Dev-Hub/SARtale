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


def test_the_worked_example_never_quotes_a_frozen_pass_as_water():
    """Review N1: when Attabad is frozen the README and guide quote its last open-water pass and say so."""
    import copy
    import json

    import pytest
    build = _load(ROOT / "docs" / "guide" / "build.py", "guide_build")
    doc = json.loads(build.LAKES_JSON.read_text(encoding="utf-8"))
    d = copy.deepcopy(doc)
    a = next(lk for lk in d["lakes"] if lk["id"] == "attabad")
    track = a["status"]["track"]
    on_track = sorted((p for p in a["series"] if p["track"] == track and p["excluded"] is None
                       and p["area_km2"] is not None), key=lambda p: p["date"])
    newest, before = on_track[-1], on_track[-2]
    newest["frozen"] = True
    a["status"] = {**a["status"], "status": "Frozen (likely)", "change_km2": None, "noise_km2": None}
    a["freeze"] = {"state": "frozen_likely", "since": "2027-01-08", "freeze_up": "2027-01-08", "reason": "r"}
    a["last_open"] = {"date": before["date"], "track": track, "area_km2": before["area_km2"], "status": "Stable",
                      "change_km2": 0.012, "noise_km2": 0.1, "looks": len(on_track) - 1, "images": None}
    ex = build.worked_example(d)
    assert ex["EX_DATE"] == build._day(before["date"]) and ex["EX_AREA"] == f"{before['area_km2']:.3f}"
    assert ex["EX_EARLIER"] == str(len(on_track) - 2) and ex["EX_STATUS"] == "Stable"
    assert ex["EX_FROZEN"] == " Attabad Lake is frozen now (since 8 January 2027); this was its last open-water pass."
    assert ex["EX_FROZEN"] in build.readme_example(ex)
    i = [p[0] for p in build.PAGES].index("method")
    assert ex["EX_FROZEN"] in build.page(i, ex)
    # without a last open-water pass the example refuses, rather than quote the frozen one
    a["last_open"] = None
    with pytest.raises(build.WorkedExampleError, match="frozen"):
        build.worked_example(d)
    # an open Attabad has no note
    assert build.worked_example(doc)["EX_FROZEN"] == ""


def test_m9_worked_example_fails_clearly_without_a_measured_attabad_status():
    import copy
    import json

    import pytest
    build = _load(ROOT / "docs" / "guide" / "build.py", "guide_build")
    doc = json.loads(build.LAKES_JSON.read_text(encoding="utf-8"))
    attabad = next(lk for lk in doc["lakes"] if lk["id"] == "attabad")

    def with_status(**changes):
        d = copy.deepcopy(doc)
        next(lk for lk in d["lakes"] if lk["id"] == "attabad")["status"].update(changes)
        return d

    for broken, words in [
        (with_status(status="Not enough NISAR looks yet", change_km2=None, noise_km2=None), "change_km2, noise_km2"),
        (with_status(status="Not observable", track=None, latest_date=None, change_km2=None, noise_km2=None), "track"),
        ({**doc, "lakes": [lk for lk in doc["lakes"] if lk["id"] != "attabad"]}, "no Attabad entry"),
        (with_status(latest_date="1999-01-01"), "0 valid pass"),
    ]:
        with pytest.raises(build.WorkedExampleError, match=words):
            build.worked_example(broken)
    assert build.worked_example(doc)["EX_TRACK"] == attabad["status"]["track"]
